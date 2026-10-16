"""Qt導入済み環境では、実際の凡例ラベルをダブルクリックして検証する。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("pyqtgraph")
from PySide6 import QtWidgets, QtCore, QtTest
from viewer.graph_panel import GraphPanel
from viewer.models import CurveSpec, ReaderOptions, DataRecord
import numpy as np


def test_double_click_legend_label_opens_correct_curve_properties():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    graph = GraphPanel("凡例テスト")
    graph.resize(800, 500)
    graph.show()
    try:
        rows = np.array([[0.0, 3.0], [1.0, 4.0]])
        record = DataRecord('C:/test/data.dat', ['H', 'R'], rows, ReaderOptions())
        specs = [CurveSpec(path=record.path, name='up'), CurveSpec(path=record.path, name='down')]
        for spec in specs:
            graph.add_curve(spec)
            graph.set_curve_data(spec, record)
        app.processEvents()
        seen = []
        graph.editCurve.connect(lambda gid, cid: seen.append((gid, cid)))
        for index, spec in enumerate(specs):
            label = graph.plot_item.legend.items[index][1]
            position = graph.plot.mapFromScene(label.sceneBoundingRect().center())
            QtTest.QTest.mouseDClick(graph.plot.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=position)
            app.processEvents()
            assert seen[-1] == (graph.graph_id, spec.id)
        assert len(seen) == len(specs)
    finally:
        graph.close()
        app.processEvents()
