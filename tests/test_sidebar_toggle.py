"""サイドバー制御のユニットテスト（Qtなしで実行可能）。"""
from viewer.sidebar_toggle import SidebarController


class FakeSidebar:
    def __init__(self, splitter):
        self._hidden = False
        self.splitter = splitter

    def isHidden(self):
        return self._hidden

    def hide(self):
        self._hidden = True
        a, b = self.splitter.current_sizes
        self.splitter.current_sizes = [0, a + b]

    def show(self):
        self._hidden = False


class FakeSplitter:
    def __init__(self, sizes=(350, 1100)):
        self.current_sizes = list(sizes)

    def sizes(self):
        return list(self.current_sizes)

    def setSizes(self, sizes):
        self.current_sizes = list(sizes)


def test_sidebar_hidden_then_restored_to_previous_width():
    splitter = FakeSplitter((410, 1040))
    sidebar = FakeSidebar(splitter)
    controller = SidebarController(splitter, sidebar)
    assert controller.is_visible
    controller.set_visible(False)
    assert not controller.is_visible
    assert splitter.sizes() == [0, 1450]
    controller.set_visible(True)
    assert controller.is_visible
    assert splitter.sizes() == [410, 1040]


def test_sidebar_does_not_change_sizes_for_redundant_toggle():
    splitter = FakeSplitter()
    sidebar = FakeSidebar(splitter)
    controller = SidebarController(splitter, sidebar)
    controller.set_visible(True)
    assert splitter.sizes() == [350, 1100]
    controller.set_visible(False)
    controller.set_visible(False)
    assert splitter.sizes() == [0, 1450]


def test_sidebar_uses_default_width_before_first_window_show():
    splitter = FakeSplitter((0, 0))
    sidebar = FakeSidebar(splitter)
    controller = SidebarController(splitter, sidebar)
    controller.set_visible(False)
    controller.set_visible(True)
    assert splitter.sizes() == [350, 1100]


def test_sidebar_retains_width_on_repeated_toggles():
    splitter = FakeSplitter((275, 1175))
    sidebar = FakeSidebar(splitter)
    controller = SidebarController(splitter, sidebar)
    for _ in range(3):
        controller.set_visible(False)
        controller.set_visible(True)
        assert splitter.sizes() == [275, 1175]
