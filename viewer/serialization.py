"""グラフJSONとスタイルテンプレートの保存。ファイルの保存形式を1か所で定義する。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from PySide6 import QtCore

from .models import ReaderOptions

VERSION = 1


def write_json(path: str | Path, data: dict):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)


def read_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_graph(path: str, graph_dict: dict, reader_options: dict[str, ReaderOptions]):
    base = Path(path).resolve().parent
    payload = {"file_version": VERSION, **graph_dict}
    for curve in payload["curves"]:
        source = str(Path(curve["path"]).resolve())
        curve["absolute_path"] = source
        try:
            curve["path"] = os.path.relpath(source, base)
        except ValueError:  # Windowsで元データとJSONの保存先が別ドライブの場合
            curve["path"] = source
        curve["reader_options"] = vars(reader_options.get(source, ReaderOptions()))
    write_json(path, payload)


def load_graph(path: str) -> dict:
    data = read_json(path)
    if data.get("file_version") != VERSION:
        raise ValueError("未対応のグラフ保存形式です")
    base = Path(path).resolve().parent
    for curve in data["curves"]:
        relative_path = (base / curve["path"]).resolve()
        absolute_path = Path(curve.get("absolute_path", "")).resolve()
        curve["path"] = str(relative_path if relative_path.is_file() else absolute_path)
    return data


class TemplateStore:
    """アプリケーション状態ではなく、名前付きスタイルだけを永続化。"""

    def __init__(self):
        path = Path(QtCore.QStandardPaths.writableLocation(
            QtCore.QStandardPaths.StandardLocation.AppDataLocation))
        self.path = path / "templates.json"
        self.templates: dict[str, dict] = {}
        if self.path.is_file():
            try:
                self.templates = read_json(self.path)
            except (OSError, ValueError, TypeError):
                self.templates = {}

    def names(self) -> list[str]:
        return sorted(self.templates)

    def put(self, name: str, template: dict):
        self.templates[name] = template
        write_json(self.path, self.templates)

    def delete(self, name: str):
        del self.templates[name]
        write_json(self.path, self.templates)
