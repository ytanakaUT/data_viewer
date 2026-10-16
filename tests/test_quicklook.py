"""クイックルックの長いヘッダー対応テスト。"""
from pathlib import Path
import os

import pytest

from viewer.models import ReaderOptions
from viewer.reader import QUICKLOOK_RAW_LINES, preview_lines, preview_table


def make_sample(path: Path, header_lines: int = 55) -> Path:
    header = [f"Header {i}" for i in range(1, header_lines)]
    header.append("Field Resistance")
    data = [f"{i} {i*2}" for i in range(25)]
    path.write_text("\n".join(header + data) + "\n", encoding="utf-8")
    return path


def test_long_header_can_be_previewed(tmp_path):
    path = make_sample(tmp_path / "long_header.dat")
    assert QUICKLOOK_RAW_LINES == 50
    lines = preview_lines(str(path), max(QUICKLOOK_RAW_LINES, 55 + 12 + 10))
    assert lines[49] == "Header 50"
    headers, rows = preview_table(lines, ReaderOptions(header_lines=55))
    assert headers == ["Field", "Resistance"]
    assert len(rows) == 12
    assert rows[0] == ["0", "0"]


def test_quicklook_dialog_with_long_header(tmp_path):
    """GUIのある環境でのみ実行するテスト（CIではoffscreen）。"""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    from viewer.dialogs import ReaderDialog

    path = make_sample(tmp_path / "long_header.dat")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = ReaderDialog(str(path), ReaderOptions())
    # 生テキスト欄は常に先頭50行表示。数値プレビューはヘッダー数に追随。
    assert len(dialog.raw.toPlainText().splitlines()) == 50
    dialog.header.setValue(55)
    assert dialog.table.rowCount() == 12
    assert dialog.table.columnCount() == 2
    assert dialog.table.item(0, 0).text() == "0"
    assert dialog.table.item(0, 1).text() == "0"
    dialog.close()
