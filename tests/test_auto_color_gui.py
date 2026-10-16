"""GUIが利用できる環境で、自動設定ボタンを検証。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("pyqtgraph")

from viewer.color_picker import CurveColorDialog
from viewer.dialogs import CurveDialog
from viewer.models import CurveSpec, DataRecord, ReaderOptions, COLORS
import numpy as np


def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_auto_button_respects_current_graph_only():
    application = app()
    picker = CurveColorDialog(
        COLORS[1],
        [COLORS[0], COLORS[1], COLORS[2]],  # 全グラフの現在使用中の色
        graph_colors=[COLORS[0], COLORS[1]],  # 編集対象のグラフのみ
    )
    auto = next(b for b in picker.findChildren(QtWidgets.QPushButton)
                if b.text() == "自動設定")
    auto.click()
    assert picker.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert picker.selected_color == COLORS[2]
    picker.close()


def test_curve_dialog_passes_current_graph_colors(monkeypatch):
    application = app()
    data = DataRecord("test.dat", ["B", "R"], np.array([[1., 2.]]), ReaderOptions())
    dialog = CurveDialog(
        CurveSpec(path=data.path, color=COLORS[0]), data,
        active_colors=[COLORS[0], COLORS[1], COLORS[2]],
        graph_colors=[COLORS[0]],
    )
    assert dialog.graph_colors == [COLORS[0]]
    dialog.close()
