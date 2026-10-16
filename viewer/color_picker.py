"""現在使われている色の再利用と、自由な色選択を行うダイアログ。"""
from __future__ import annotations

from PySide6 import QtWidgets, QtGui, QtCore

from .color_palette import unused_graph_color


class CurveColorDialog(QtWidgets.QDialog):
    """上部の色見本はクリックで即決定。下部では任意の色を選べる。"""

    def __init__(self, current_color: str, active_colors: list[str], parent=None,
                 graph_colors: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("曲線の色を選択")
        self.selected_color: str | None = None
        self.resize(570, 220)
        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(QtWidgets.QLabel("現在のグラフで使用中の色（クリックで適用）"))
        # グラフが非表示でも、その中に曲線が存在すれば候補に含める。
        valid_colors = [color for color in active_colors if QtGui.QColor(color).isValid()]
        if valid_colors:
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setMaximumHeight(128)
            container = QtWidgets.QWidget()
            grid = QtWidgets.QGridLayout(container)
            grid.setSpacing(6)
            grid.setContentsMargins(4, 4, 4, 4)
            for index, color in enumerate(valid_colors):
                button = QtWidgets.QToolButton()
                button.setFixedSize(42, 34)
                button.setToolTip(color)
                button.setAccessibleName(f"使用中の色 {color}")
                # テキストがないボタンにも細い枠を付けて白色を識別できるようにする。
                button.setStyleSheet(
                    f"QToolButton {{ background-color: {color}; border: 1px solid #888; "
                    "border-radius: 3px; }} "
                    "QToolButton:hover { border: 2px solid #222; }"
                )
                button.clicked.connect(lambda checked=False, c=color: self._select_used_color(c))
                grid.addWidget(button, index // 10, index % 10)
            grid.setColumnStretch(10, 1)
            scroll.setWidget(container)
            layout.addWidget(scroll)
        else:
            layout.addWidget(QtWidgets.QLabel("使用中の色はまだありません"))

        self.graph_colors = list(graph_colors or [])
        row = QtWidgets.QHBoxLayout()
        auto_button = QtWidgets.QPushButton("自動設定")
        auto_button.setToolTip("このグラフ内で使われていない色を自動で選ぶ")
        auto_button.clicked.connect(self._choose_auto_color)
        row.addWidget(auto_button)
        other_button = QtWidgets.QPushButton("その他の色を選択...")
        other_button.clicked.connect(self._choose_other_color)
        row.addWidget(other_button)
        row.addStretch()
        cancel_button = QtWidgets.QPushButton("キャンセル")
        cancel_button.clicked.connect(self.reject)
        row.addWidget(cancel_button)
        layout.addLayout(row)
        self.current_color = current_color

    def _select_used_color(self, color: str) -> None:
        self.selected_color = QtGui.QColor(color).name()
        self.accept()

    def _choose_auto_color(self) -> None:
        self.selected_color = unused_graph_color(self.graph_colors)
        self.accept()

    def _choose_other_color(self) -> None:
        # 従来のWindows標準色選択を引き続き使用できる。
        chosen = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.current_color), self)
        if chosen.isValid():
            self.selected_color = chosen.name()
            self.accept()
