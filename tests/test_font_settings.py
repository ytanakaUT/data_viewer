"""フォントサイズの設定値だけを確認するGUI不要のテスト。"""

import pytest

from viewer.font_settings import FONT_SIZE_DEFAULTS, get_font_sizes


def test_old_graphs_and_templates_use_defaults():
    assert get_font_sizes({}) == FONT_SIZE_DEFAULTS


def test_three_independent_settings_and_partial_overrides():
    s = get_font_sizes({"title_font_size": 20, "label_font_size": 13, "tick_font_size": 8})
    assert s == {"title_font_size": 20, "label_font_size": 13, "tick_font_size": 8}
    assert get_font_sizes({"label_font_size": 15}, s) == {
        "title_font_size": 20, "label_font_size": 15, "tick_font_size": 8,
    }


@pytest.mark.parametrize("invalid", [None, 0, 5, 49, -3, 11.5, "oops", float("nan"), float("inf")])
def test_invalid_font_sizes_are_rejected(invalid):
    with pytest.raises(ValueError):
        get_font_sizes({"tick_font_size": invalid})


def test_json_compatible_integer_values():
    assert get_font_sizes({"title_font_size": 22.0, "tick_font_size": "13"}) == {
        "title_font_size": 22, "label_font_size": 11, "tick_font_size": 13,
    }
