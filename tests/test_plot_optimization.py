"""上昇・下降・往復スイープと欠損値の表示最適化に関する回帰テスト。"""
import numpy as np
import pytest

from viewer.plot_optimization import prepare_plot_data


def test_ascending_keeps_original_and_fast_path():
    x = np.array([-2., 0., 1., 1., 3.])
    y = np.arange(len(x), dtype=float)
    plan = prepare_plot_data(x, y)
    assert plan.direction == "ascending"
    assert plan.clip_to_view and plan.auto_downsample
    assert np.shares_memory(plan.x, x)
    np.testing.assert_array_equal(plan.x, x)


def test_descending_reverses_only_rendering_order():
    x = np.array([5., 4., 2., 1., -2.])
    y = np.array([10., 9., 8., 7., 6.])
    x_original, y_original = x.copy(), y.copy()
    plan = prepare_plot_data(x, y)
    assert plan.direction == "descending"
    assert plan.clip_to_view and plan.auto_downsample
    np.testing.assert_array_equal(plan.x, [-2., 1., 2., 4., 5.])
    np.testing.assert_array_equal(plan.y, [6., 7., 8., 9., 10.])
    np.testing.assert_array_equal(x, x_original)
    np.testing.assert_array_equal(y, y_original)
    assert np.shares_memory(plan.x, x)
    # 線分として通る点の順序を反転しているだけで、形は変わらない。
    assert list(zip(plan.x[::-1], plan.y[::-1])) == list(zip(x, y))


def test_reversal_or_hysteresis_preserves_original_order_and_disables_fast_path():
    x = np.array([-3., -1., 1., 4., 2., 0., -2.])
    y = np.array([0., 1., 4., 7., 5., 2., -1.])
    plan = prepare_plot_data(x, y)
    assert plan.direction == "nonmonotonic"
    assert not plan.clip_to_view and not plan.auto_downsample
    np.testing.assert_array_equal(plan.x, x)
    np.testing.assert_array_equal(plan.y, y)


@pytest.mark.parametrize("x", [[1., np.nan, 3.], [1., np.inf, 3.], [1., -np.inf, 3.]])
def test_nonfinite_x_disables_clipping(x):
    plan = prepare_plot_data(np.array(x), np.arange(len(x), dtype=float))
    assert not plan.clip_to_view and not plan.auto_downsample


def test_missing_y_keeps_x_fast_path_and_nan_gap():
    x = np.array([0., 1., 2.])
    y = np.array([0., np.nan, 4.])
    plan = prepare_plot_data(x, y)
    assert plan.clip_to_view
    assert np.isnan(plan.y[1])


def test_log_with_nonpositive_x_disables_clipping():
    x = np.array([-1., 1., 2.])
    plan = prepare_plot_data(x, x, x_log=True)
    assert not plan.clip_to_view and not plan.auto_downsample
    assert prepare_plot_data(x, x, x_log=False).clip_to_view


def test_no_change_to_plot_style_settings():
    """同じデータが線/点のいずれで描かれてもPlanは同じ。"""
    x = np.array([4., 2., 0.])
    y = np.array([1., 2., 3.])
    plan = prepare_plot_data(x, y)
    assert list(zip(plan.x, plan.y)) == [(0., 3.), (2., 2.), (4., 1.)]


def test_live_graph_panel_clip_flags():
    """Qtが使える環境では、グラフへの設定が反映されることを確認。"""
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6 import QtWidgets
    from viewer.graph_panel import GraphPanel
    from viewer.models import CurveSpec, DataRecord, ReaderOptions
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = GraphPanel("test")
    try:
        for name, x, should_clip in [
            ("up", [0., 1., 2.], True),
            ("down", [2., 1., 0.], True),
            ("loop", [0., 2., 1.], False),
        ]:
            spec = CurveSpec(path=f"{name}.dat", name=name)
            arr = np.column_stack([x, [10., 20., 30.]])
            panel.add_curve(spec)
            panel.set_curve_data(spec, DataRecord(spec.path, ["x", "y"], arr, ReaderOptions()))
            item = panel.items[spec.id]
            assert item.opts["clipToView"] == should_clip
            assert item.opts["autoDownsample"] == should_clip
            np.testing.assert_array_equal(panel.values[spec.id][0], x)
        panel.apply_template({"palette": ["#123456"]})
        # テンプレートで描き直しても、downの描画用Xは昇順のまま。
        down = next(c for c in panel.curves if c.name == "down")
        np.testing.assert_array_equal(panel.display_values[down.id][0], [0., 1., 2.])
    finally:
        panel.close()
        panel.deleteLater()
