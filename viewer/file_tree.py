"""フォルダ階層を表示するサイドバー。Qtのファイルシステムモデルを使って遅延列挙する。"""
from pathlib import Path
from PySide6 import QtCore, QtWidgets


class FileTree(QtWidgets.QTreeView):
    fileActivated = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model_ = QtWidgets.QFileSystemModel(self)
        self.model_.setRootPath("")
        self.setModel(self.model_)
        self.setHeaderHidden(True)
        for i in (1, 2, 3):
            self.hideColumn(i)
        self.setDragEnabled(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragOnly)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.doubleClicked.connect(self._activated)

    def select_folder(self, folder: str):
        index = self.model_.setRootPath(folder)
        self.setRootIndex(index)

    def current_file(self) -> str | None:
        index = self.currentIndex()
        if not index.isValid() or self.model_.isDir(index):
            return None
        return self.model_.filePath(index)

    def _activated(self, index):
        if index.isValid() and not self.model_.isDir(index):
            self.fileActivated.emit(self.model_.filePath(index))
