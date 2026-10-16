"""左サイドバーの表示切替と幅の復元を担当する。

Qtの表示切替はMainWindowのツールバーから呼び出す。隠すときの幅を
記録しておき、再表示時には同じ幅を使う。ファイル一覧・グラフ一覧の
ウィジェットを破棄したり、データを再読み込みしたりはしない。
"""
from __future__ import annotations


class SidebarController:
    """QSplitter内のサイドバーを隠す・再表示する小さな制御クラス。"""

    def __init__(self, splitter, sidebar, default_width: int = 350):
        self.splitter = splitter
        self.sidebar = sidebar
        self._saved_width = default_width

    @property
    def is_visible(self) -> bool:
        # isVisible() は親ウィンドウの表示前だとFalseになる。
        # isHidden() なら「明示的に非表示にしたか」を正しく判定できる。
        return not self.sidebar.isHidden()

    def set_visible(self, visible: bool) -> None:
        """表示・非表示を切り替え、直前のサイドバー幅を保持する。"""
        if visible == self.is_visible:
            return

        if not visible:
            sizes = self.splitter.sizes()
            if sizes and sizes[0] > 0:
                self._saved_width = sizes[0]
            self.sidebar.hide()
            return

        self.sidebar.show()
        sizes = self.splitter.sizes()
        available_width = sum(sizes)
        if available_width > 0:
            self.splitter.setSizes([
                min(self._saved_width, available_width),
                max(1, available_width - self._saved_width),
            ])
        else:
            # ウィンドウをまだ表示していない場合の初期値。
            self.splitter.setSizes([self._saved_width, 1100])
