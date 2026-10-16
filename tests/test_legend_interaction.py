"""Qtなしで、凡例上の曲線名から正しい曲線を選べることを検証。"""

from viewer.legend_interaction import curve_id_at_legend_label


class Rect:
    def __init__(self, x, y, width, height):
        self.x, self.y = x, y
        self.width, self.height = width, height

    def contains(self, point):
        x, y = point
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height


class Label:
    def __init__(self, rect, visible=True):
        self.rect = rect
        self.visible = visible

    def isVisible(self):
        return self.visible

    def sceneBoundingRect(self):
        return self.rect


class Sample:
    def __init__(self, item):
        self.item = item


class Legend:
    def __init__(self, *entries):
        self.items = list(entries)


def test_double_click_targets_only_label_not_sample_or_background():
    a, b = object(), object()
    legend = Legend((Sample(a), Label(Rect(20, 10, 60, 20))),
                    (Sample(b), Label(Rect(20, 40, 60, 20))))
    mapping = {"curve-a": a, "curve-b": b}
    assert curve_id_at_legend_label(legend, (30, 15), mapping) == "curve-a"
    assert curve_id_at_legend_label(legend, (30, 45), mapping) == "curve-b"
    assert curve_id_at_legend_label(legend, (5, 15), mapping) is None
    assert curve_id_at_legend_label(legend, (100, 50), mapping) is None
    assert curve_id_at_legend_label(None, (30, 15), mapping) is None


def test_removed_or_hidden_label_is_not_interactive():
    item = object()
    label = Label(Rect(20, 10, 60, 20), visible=False)
    legend = Legend((Sample(item), label))
    assert curve_id_at_legend_label(legend, (30, 15), {'curve': item}) is None
    label.visible = True
    assert curve_id_at_legend_label(legend, (30, 15), {}) is None
    assert curve_id_at_legend_label(legend, (30, 15), {'curve': item}) == 'curve'


def test_legend_rebuilt_for_new_name_does_not_break_mapping():
    item = object()
    legend = Legend((Sample(item), Label(Rect(20, 10, 60, 20))))
    mapping = {'existing-curve-id': item}
    assert curve_id_at_legend_label(legend, (30, 15), mapping) == 'existing-curve-id'
    # 曲線名変更時は内部でlabelが差し替えられる。
    legend.items = [(Sample(item), Label(Rect(20, 50, 90, 20)))]
    assert curve_id_at_legend_label(legend, (30, 15), mapping) is None
    assert curve_id_at_legend_label(legend, (30, 55), mapping) == 'existing-curve-id'
