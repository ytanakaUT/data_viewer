"""PySide6が導入されている場合のみ、UIで複製操作を確認する。"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
from PySide6 import QtWidgets, QtCore
from viewer.main_window import MainWindow
from viewer.models import CurveSpec, ReaderOptions
from viewer.reader import load_data


def test_duplicate_reuses_cached_data_and_is_independent():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow()
    try:
        origin = next(iter(window.graphs.values()))
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "sample_data" / "demo.dat"
        rec = load_data(str(path), ReaderOptions())
        window.data_manager.cache[window.data_manager.normalize(str(path))] = rec
        spec = CurveSpec(path=str(path), name="Rxx", color="#cc1234", plot_style="markers",
                         marker_size=10, width=3, use_formula=True, y_expr="y*2")
        origin.add_curve(spec)
        origin.set_curve_data(spec, rec)
        origin.apply_settings({"x_min": -2, "x_max": 3, "y_min": 20, "y_max": 80,
                               "xlabel": "H", "ylabel": "2R"}, record_history=False)
        clone = window.duplicate_graph(origin.graph_id)
        assert clone is not None and clone.graph_id != origin.graph_id
        assert len(window.graphs) == 2
        assert clone.curves[0].id != origin.curves[0].id
        assert clone.curves[0].path == spec.path
        assert clone.curves[0].y_expr == "y*2"
        assert clone.curves[0].plot_style == "markers"
        assert clone.curves[0].marker_size == 10
        np.testing.assert_allclose(clone.values[clone.curves[0].id][1], origin.values[spec.id][1])
        for k in ["x_min", "x_max", "y_min", "y_max"]:
            assert clone.settings()[k] == pytest.approx(origin.settings()[k])
        clone.curves[0].color = "#000000"
        assert origin.curves[0].color == "#cc1234"
    finally:
        window.close()
        app.processEvents()
