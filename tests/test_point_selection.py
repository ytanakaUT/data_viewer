"""部分消去の純粋データ処理と保存互換性に関するテスト。"""

import numpy as np

from viewer.point_selection import visible_mask, masked_y, rectangle_indices, hide_indices, visible_bounds
from viewer.models import CurveSpec
from viewer.graph_clone import clone_graph_definition


def test_missing_points_preserve_index_and_do_not_modify_input():
    y = np.array([1., 2., 3., 4.])
    masked = masked_y(y, [1, 3])
    np.testing.assert_array_equal(y, [1., 2., 3., 4.])
    assert np.isnan(masked[1]) and np.isnan(masked[3])
    assert masked[0] == 1 and masked[2] == 3


def test_rectangle_includes_only_finite_and_visible_values():
    x = np.array([0., 1., 2., 3., 4.])
    y = np.array([0., 3., 4., np.nan, 2.])
    selection = rectangle_indices(x, y, (0.5, 4, 1, 5),
                                  available=visible_mask(5, [2]))
    np.testing.assert_array_equal(selection, [1, 4])


def test_hide_indices_combine_without_duplicate_or_invalid():
    assert hide_indices([2, 2, 15], [1, 2, -1], 5) == [1, 2]
    np.testing.assert_array_equal(visible_mask(4, [1, 9]), [True, False, True, True])


def test_autoscale_excludes_hidden_points_on_both_axes():
    x = np.array([0., 1., 2., 1000.])
    y = np.array([0., 5., 6., 9000.])
    bounds = visible_bounds([(x, masked_y(y, [3]))])
    assert bounds == (0., 2., 0., 6.)


def test_autoscale_log_and_no_valid_points():
    x = np.array([-1., 1., 10.])
    y = np.array([3., 10., 100.])
    assert visible_bounds([(x, y)], x_log=True, y_log=True) == (0., 1., 1., 2.)
    assert visible_bounds([(x, masked_y(y, [0, 1, 2]))]) is None


def test_old_graph_defaults_and_json_clone_independence():
    old = CurveSpec.from_dict({"path": "a.dat", "name": "A"})
    assert old.hidden_indices == []
    old.hidden_indices = [1, 4]
    original = {"id": "old", "settings": {"title": "G"}, "curves": [old.to_dict()]}
    copied = clone_graph_definition(original, [])
    assert copied["curves"][0]["hidden_indices"] == [1, 4]
    copied["curves"][0]["hidden_indices"].append(6)
    assert original["curves"][0]["hidden_indices"] == [1, 4]


def test_new_curve_from_previous_does_not_inherit_hidden_points():
    from viewer.curve_defaults import initial_curve_spec
    from viewer.models import DataRecord, ReaderOptions
    first = DataRecord("old.dat", ["Field", "R"], np.array([[1., 2.]]), ReaderOptions())
    second = DataRecord("new.dat", ["Field", "R"], np.array([[3., 4.]]), ReaderOptions())
    previous = CurveSpec(path="old.dat", hidden_indices=[0])
    new_spec = initial_curve_spec(second, graph_colors=[], previous_spec=previous, previous_record=first)
    assert new_spec.hidden_indices == []
    assert previous.hidden_indices == [0]
