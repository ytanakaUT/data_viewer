"""現在使われている曲線の色だけが候補になることを確認。"""
from dataclasses import dataclass
from viewer.color_palette import active_curve_colors


@dataclass
class FakeCurve:
    color: str
    visible: bool = True


@dataclass
class FakeGraph:
    curves: list[FakeCurve]
    displayed: bool = True


def test_colors_from_all_existing_graphs_and_curves():
    g1 = FakeGraph([FakeCurve("#123456"), FakeCurve("#ABCDEF", visible=False)])
    g2 = FakeGraph([FakeCurve("#123456"), FakeCurve("#cccccc")], displayed=False)
    assert active_curve_colors([g1, g2]) == ["#cccccc", "#123456", "#ABCDEF"]


def test_deleted_or_changed_colors_disappear():
    graph = FakeGraph([FakeCurve("#111111"), FakeCurve("#222222")])
    assert active_curve_colors([graph]) == ["#222222", "#111111"]
    graph.curves[1].color = "#333333"
    assert active_curve_colors([graph]) == ["#333333", "#111111"]
    graph.curves.pop(0)
    assert active_curve_colors([graph]) == ["#333333"]
    assert active_curve_colors([]) == []


def test_deduplicate_case_insensitively():
    graph = FakeGraph([FakeCurve("#ABCDEF"), FakeCurve("#abcdef"), FakeCurve("")])
    assert active_curve_colors([graph]) == ["#abcdef"]
