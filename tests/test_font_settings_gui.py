"""GUIが使える場合、実際のダイアログとPlotItemへの文字サイズ適用を検証する。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
from PySide6 import QtWidgets
from viewer.graph_panel import GraphPanel
from viewer.dialogs import AxisDialog


def test_fonts_in_axis_dialog_and_saved_settings():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    graph = GraphPanel("Example")
    try:
        dialog = AxisDialog(graph.settings())
        assert set(dialog.font_sizes) == {"title_font_size", "label_font_size", "tick_font_size"}
        dialog.font_sizes["title_font_size"].setValue(21)
        dialog.font_sizes["label_font_size"].setValue(17)
        dialog.font_sizes["tick_font_size"].setValue(13)
        new_settings = dialog.settings()
        graph.apply_settings(new_settings, record_history=False)
        assert all(graph.settings()[key] == new_settings[key] for key in dialog.font_sizes)
        assert graph.axis_x.style["tickFont"].pointSize() == 13
        assert graph.axis_y.style["tickFont"].pointSize() == 13
        assert "17pt" in graph.axis_x.label.toHtml()
        assert "17pt" in graph.axis_y.label.toHtml()
        # フォントサイズもグラフ定義とテンプレートへ保持される。
        saved = graph.to_dict()["settings"]
        tpl = graph.template_data()["settings"]
        assert saved["title_font_size"] == tpl["title_font_size"] == 21
        assert saved["label_font_size"] == tpl["label_font_size"] == 17
        assert saved["tick_font_size"] == tpl["tick_font_size"] == 13
        second = GraphPanel("Copy")
        try:
            second.apply_settings(saved, record_history=False)
            assert second.settings()["title_font_size"] == 21
            assert second.settings()["label_font_size"] == 17
            assert second.settings()["tick_font_size"] == 13
        finally:
            second.close()
    finally:
        graph.close()
        app.processEvents()


def test_old_graph_without_font_keys_is_loadable():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    graph = GraphPanel("Example")
    try:
        graph.apply_settings({"title": "Older", "xlabel": "H", "ylabel": "R"}, record_history=False)
        sizes = graph.settings()
        assert (sizes["title_font_size"], sizes["label_font_size"], sizes["tick_font_size"]) == (12, 11, 10)
    finally:
        graph.close()
        app.processEvents()
