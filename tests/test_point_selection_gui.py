"""Qtが導入された環境で、点選択・非表示・復元・保存を試す。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
from PySide6 import QtWidgets
from viewer.graph_panel import GraphPanel
from viewer.models import CurveSpec, DataRecord, ReaderOptions


def test_hide_restore_and_clone_payload():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    graph = GraphPanel("Mask test")
    try:
        graph.set_mode("select")
        assert graph.mask_toolbar.isVisible() or not graph.isVisible()
        spec = CurveSpec(path="demo.dat", name="up")
        graph.add_curve(spec)
        arr = np.column_stack([np.arange(6.), [1., 3., 4., 4., 7., 1000.]])
        graph.set_curve_data(spec, DataRecord("demo.dat", ["X", "Y"], arr, ReaderOptions()))
        graph.select_rectangle(1., 4., 2., 8.)
        assert graph.selected_points[spec.id] == {1, 2, 3, 4}
        graph.selected_points[spec.id].discard(2)
        graph.hide_selected_points()
        assert spec.hidden_indices == [1, 3, 4]
        assert graph.to_dict()["curves"][0]["hidden_indices"] == [1, 3, 4]
        graph.auto_range()
        assert graph.vb.viewRange()[1][1] > 900   # 最後の可視点を使う
        graph.show_all_points()
        assert spec.hidden_indices == []
    finally:
        graph.close()
        app.processEvents()


def test_down_sweep_hidden_points_keep_fast_clipping():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    graph = GraphPanel("Down")
    try:
        spec = CurveSpec(path="down.dat", name="down", hidden_indices=[1])
        graph.add_curve(spec)
        arr = np.column_stack([[3., 2., 1.], [3., 2., 1.]])
        graph.set_curve_data(spec, DataRecord(spec.path, ["x", "y"], arr, ReaderOptions()))
        assert graph.items[spec.id].opts["clipToView"]
        np.testing.assert_array_equal(graph.display_values[spec.id][0], [1., 2., 3.])
        assert np.isnan(graph.display_values[spec.id][1][1])
    finally:
        graph.close()
        app.processEvents()
