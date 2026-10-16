"""グラフで未使用の色が自動選択される（Qt不要のテスト）。"""

from viewer.color_palette import unused_graph_color
from viewer.models import COLORS


def test_choose_first_available_palette_color():
    assert unused_graph_color([]) == COLORS[0]
    assert unused_graph_color([COLORS[0]]) == COLORS[1]
    assert unused_graph_color([COLORS[0], COLORS[1]]) == COLORS[2]


def test_existing_curve_own_color_is_considered_in_use():
    # 編集対象の曲線自身も含むため、別の色が選ばれる。
    assert unused_graph_color([COLORS[0]]) != COLORS[0]


def test_ignore_other_graph_colors():
    # 他グラフの色を渡さなければ、そちらと同じ色でも選択できる。
    assert unused_graph_color([COLORS[1]]) == COLORS[0]


def test_case_insensitive_duplicate_detection():
    assert unused_graph_color([COLORS[0].upper()]) == COLORS[1]


def test_fallback_does_not_reuse_full_palette():
    color = unused_graph_color(COLORS)
    assert color not in {c.casefold() for c in COLORS}
    assert color.startswith("#") and len(color) == 7
    assert unused_graph_color(COLORS) == color
    assert unused_graph_color([*COLORS, color]) != color


def test_no_list_mutation():
    existing = [COLORS[0], COLORS[1]]
    unused_graph_color(existing)
    assert existing == [COLORS[0], COLORS[1]]
