"""データのキャッシュと、GUIを止めないバックグラウンド読み込みを担当。"""
from __future__ import annotations

from pathlib import Path
from PySide6 import QtCore

from .models import ReaderOptions, DataRecord
from .reader import load_data


class _Signals(QtCore.QObject):
    done = QtCore.Signal(str, object, str)  # path, DataRecordまたはNone, error


class _ReadTask(QtCore.QRunnable):
    def __init__(self, path: str, options: ReaderOptions, signals: _Signals):
        super().__init__()
        self.path, self.options, self.signals = path, options, signals

    def run(self):
        try:
            self.signals.done.emit(self.path, load_data(self.path, self.options), "")
        except Exception as exc:
            self.signals.done.emit(self.path, None, str(exc))


class DataManager(QtCore.QObject):
    loaded = QtCore.Signal(str)
    failed = QtCore.Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cache: dict[str, DataRecord] = {}
        self.options: dict[str, ReaderOptions] = {}
        self.pending: dict[str, _Signals] = {}
        self._reload_queued: set[str] = set()
        self.pool = QtCore.QThreadPool(self)
        self.pool.setMaxThreadCount(3)

    @staticmethod
    def normalize(path: str) -> str:
        return str(Path(path).resolve())

    def get(self, path: str) -> DataRecord | None:
        return self.cache.get(self.normalize(path))

    def request(self, path: str, force: bool = False):
        path = self.normalize(path)
        if path in self.pending:
            if force:
                self._reload_queued.add(path)
            return
        if not force and path in self.cache:
            self.loaded.emit(path)
            return
        signals = _Signals()
        signals.done.connect(self._finish)
        self.pending[path] = signals  # 完了するまでQObjectを保持
        self.pool.start(_ReadTask(path, self.options.get(path, ReaderOptions()), signals))

    @QtCore.Slot(str, object, str)
    def _finish(self, path: str, result: object, error: str):
        self.pending.pop(path, None)
        if error:
            self.failed.emit(path, error)
        else:
            self.cache[path] = result
            self.loaded.emit(path)
        if path in self._reload_queued:
            self._reload_queued.discard(path)
            self.request(path, force=True)

    def set_options(self, path: str, options: ReaderOptions):
        path = self.normalize(path)
        self.options[path] = options
        self.request(path, force=True)
