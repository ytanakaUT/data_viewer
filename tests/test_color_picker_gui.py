"""GUI環境で色選択ダイアログを開いて確認するテスト。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("pyqtgraph")

from viewer.color_picker import CurveColorDialog
from viewer.dialogs import CurveDialog
from viewer.models import CurveSpec, DataRecord, ReaderOptions
import numpy as np


def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_swatch_selection_and_cancel():
    application = app()
    picker = CurveColorDialog("#000000", ["#112233", "#445566"])
    buttons = picker.findChildren(QtWidgets.QToolButton)
    assert len(buttons) == 2
    assert buttons[0].toolTip() == "#112233"
    buttons[1].click()
    assert picker.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert picker.selected_color == "#445566"
    picker.close()

    picker2 = CurveColorDialog("#ffffff", ["#112233"])
    picker2.reject()
    assert picker2.selected_color is None
    picker2.close()


def test_curve_dialog_receives_active_colors(monkeypatch):
    application = app()
    record = DataRecord("test.dat", ["B", "R"], np.array([[1., 2.]]), ReaderOptions())
    dialog = CurveDialog(CurveSpec(path="test.dat"), record, active_colors=["#338855"])
    assert dialog.active_colors == ["#338855"]
    dialog.close()
