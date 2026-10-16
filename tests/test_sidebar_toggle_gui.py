"""PySide6がある環境で、実際のメインウィンドウのサイドバー切替を確認する。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
from PySide6 import QtWidgets
from viewer.main_window import MainWindow


def test_toolbar_toggle_hides_and_restores_sidebar():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    app.processEvents()
    try:
        width_before = window.splitter.sizes()[0]
        assert width_before > 0
        assert window.toggle_sidebar_action.isChecked()
        window.toggle_sidebar_action.trigger()
        app.processEvents()
        assert window.sidebar.isHidden()
        assert not window.toggle_sidebar_action.isChecked()
        assert window.splitter.sizes()[0] == 0
        window.toggle_sidebar_action.trigger()
        app.processEvents()
        assert not window.sidebar.isHidden()
        assert window.toggle_sidebar_action.isChecked()
        assert abs(window.splitter.sizes()[0] - width_before) < 20
        assert window.graph_list.count() == 1  # 中身は維持される
    finally:
        window.close()
        app.processEvents()
