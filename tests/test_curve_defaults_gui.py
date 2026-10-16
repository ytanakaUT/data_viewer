"""Windows等のQt環境で、追加ダイアログが前の曲線設定を引き継ぐか確認。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("pyqtgraph")

import numpy as np

from viewer.models import COLORS, DataRecord, ReaderOptions
from viewer.main_window import MainWindow


def test_dialog_defaults_are_per_graph_and_preserve_previous_style(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow()
    graph1 = next(iter(window.graphs.values()))
    graph2 = window.add_graph("Graph 2")
    rows = np.array([[0.0, 10.0, 2.0], [1.0, 20.0, 4.0]])
    original = DataRecord("C:/test/first.dat", ["B", "V", "I"], rows, ReaderOptions())
    following = DataRecord("C:/test/second.dat", ["B", "V", "I"], rows, ReaderOptions())
    seen = []

    class DummyDialog:
        def __init__(self, spec, record, parent, *, active_colors=None, graph_colors=None):
            seen.append(spec)
            self.spec = spec
            if len(seen) == 1:
                # ユーザーが最初の曲線の設定を決めたものとする。
                self.spec.columns = {"x": 0, "y": 1, "z": 2}
                self.spec.use_formula = True
                self.spec.y_expr = "y / z"
                self.spec.plot_style = "markers"
                self.spec.marker_size = 13.0
                self.spec.color = "#bb3366"

        def exec(self):
            return QtWidgets.QDialog.DialogCode.Accepted

    monkeypatch.setattr("viewer.main_window.CurveDialog", DummyDialog)
    window.data_manager.cache[window.data_manager.normalize(original.path)] = original
    window._add_curve_dialog(graph1, original)
    window._add_curve_dialog(graph1, following)
    window._add_curve_dialog(graph2, following)

    assert seen[1].path == following.path
    assert seen[1].name == "second"
    assert seen[1].plot_style == "markers"
    assert seen[1].marker_size == 13.0
    assert seen[1].color == COLORS[0]  # 手動変更により青が空いたので再利用する
    assert seen[1].use_formula and seen[1].y_expr == "y / z"
    assert seen[1].id != seen[0].id
    assert seen[2].plot_style == "lines"  # 別グラフには引き継がない
    assert seen[2].color == COLORS[0]  # 別グラフの使用色は考慮しない
    window.close()
