"""クイックルック、曲線プロパティ、軸設定などのダイアログ。"""
from __future__ import annotations

from dataclasses import replace
from PySide6 import QtWidgets, QtCore, QtGui

from .models import ReaderOptions, CurveSpec, DataRecord
from .curve_style import PLOT_STYLES
from .reader import (
    QUICKLOOK_RAW_LINES, QUICKLOOK_TABLE_ROWS, preview_lines, preview_table
)


def message_error(parent, title: str, details: str):
    QtWidgets.QMessageBox.warning(parent, title, details)


class ReaderDialog(QtWidgets.QDialog):
    """冒頭のテキストとパース結果を比較し、ファイル形式を手動指定する。"""

    def __init__(self, path: str, options: ReaderOptions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("データのクイックルック / 読み込み設定")
        self.resize(820, 760)
        self.path = path
        self.lines = []
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(path))
        self.raw = QtWidgets.QPlainTextEdit()
        self.raw.setReadOnly(True)
        self.raw.setMinimumHeight(260)
        self.raw.setMaximumHeight(350)
        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        self.raw.setFont(font)
        layout.addWidget(QtWidgets.QLabel(f"ファイル先頭（最初の{QUICKLOOK_RAW_LINES}行）"))
        layout.addWidget(self.raw)
        form = QtWidgets.QFormLayout()
        self.delimiter = QtWidgets.QComboBox()
        self.delimiter.addItem("スペース＋タブ（連続空白）", "whitespace")
        self.delimiter.addItem("タブのみ", "tab")
        self.delimiter.addItem("カンマ", "comma")
        self.delimiter.addItem("スペースのみ", "space")
        self.delimiter.setCurrentIndex(max(0, self.delimiter.findData(options.delimiter)))
        self.header = QtWidgets.QSpinBox()
        self.header.setRange(0, 10000)
        self.header.setValue(options.header_lines)
        self.name_line = QtWidgets.QSpinBox()
        self.name_line.setRange(0, 10000)
        self.name_line.setValue(options.name_line)
        self.name_line.setToolTip("0ならヘッダーの最終行。数値を入れると先頭からその行を列名として使用")
        self.encoding = QtWidgets.QComboBox()
        self.encoding.setEditable(True)
        self.encoding.addItems(["utf-8-sig", "cp932", "utf-16", "latin-1"])
        self.encoding.setCurrentText(options.encoding)
        form.addRow("区切り文字", self.delimiter)
        form.addRow("ヘッダー行数", self.header)
        form.addRow("列名に使用する行（0=最終ヘッダー行）", self.name_line)
        form.addRow("文字コード", self.encoding)
        layout.addLayout(form)
        layout.addWidget(QtWidgets.QLabel(f"数値部分のプレビュー（先頭{QUICKLOOK_TABLE_ROWS}行）"))
        self.table = QtWidgets.QTableWidget()
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.status = QtWidgets.QLabel()
        layout.addWidget(self.status)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for widget, signal in [(self.delimiter, self.delimiter.currentIndexChanged),
                               (self.name_line, self.name_line.valueChanged)]:
            signal.connect(self.update_preview)
        # ヘッダーが50行以上のファイルでも、ヘッダーより後ろの数値行をプレビューする。
        self.header.valueChanged.connect(self._read_text)
        self.encoding.currentTextChanged.connect(self._read_text)
        self._read_text()

    def options(self) -> ReaderOptions:
        return ReaderOptions(self.delimiter.currentData(), self.header.value(),
                             self.name_line.value(), self.encoding.currentText())

    def _read_text(self):
        try:
            # ヘッダー行数が大きくても、数値部分のプレビュー分まで先読みする。
            # ただし上段の生テキスト表示は先頭50行に固定する。
            count = max(QUICKLOOK_RAW_LINES, self.header.value() + QUICKLOOK_TABLE_ROWS + 10)
            self.lines = preview_lines(self.path, count, self.encoding.currentText())
            self.raw.setPlainText("\n".join(
                f"{i+1:>3}: {line}" for i, line in enumerate(self.lines[:QUICKLOOK_RAW_LINES])
            ))
            self.update_preview()
        except Exception as exc:
            self.lines = []
            self.raw.setPlainText("")
            self.status.setText(f"読み込みに失敗: {exc}")

    def update_preview(self, *_):
        opts = self.options()
        headers, rows = preview_table(self.lines, opts)
        self.table.clear()
        self.table.setColumnCount(len(headers))
        self.table.setRowCount(len(rows))
        self.table.setHorizontalHeaderLabels(headers)
        for r, row in enumerate(rows):
            for c, value in enumerate(row[:len(headers)]):
                self.table.setItem(r, c, QtWidgets.QTableWidgetItem(value))
        self.status.setText(f"プレビュー: {len(rows)}行 / {len(headers)}列（ファイル全体はまだ読み込みません）")


class CurveDialog(QtWidgets.QDialog):
    """ファイルの列をx,y,z,a,b,cへ割り当て、X/Y式と描画属性を編集する。"""

    def __init__(self, spec: CurveSpec, record: DataRecord, parent=None, editing=False):
        super().__init__(parent)
        self.setWindowTitle("曲線のプロパティ" if editing else "グラフにデータを追加")
        self.resize(560, 590)
        self.spec = replace(spec, columns=spec.columns.copy())
        self.delete_requested = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(f"ファイル: {record.path}"))
        form = QtWidgets.QFormLayout()
        self.name = QtWidgets.QLineEdit(self.spec.name)
        form.addRow("曲線名", self.name)
        self.mapping = {}
        for letter in "xyzabc":
            combo = QtWidgets.QComboBox()
            combo.addItem("（未指定）", -1)
            for i, header in enumerate(record.columns):
                combo.addItem(f"{i+1}: {header}", i)
            default = self.spec.columns.get(letter, -1)
            combo.setCurrentIndex(max(0, combo.findData(default)))
            self.mapping[letter] = combo
            form.addRow(f"変数 {letter}", combo)
        layout.addLayout(form)
        self.use_formula = QtWidgets.QCheckBox("計算式を使用する")
        self.use_formula.setChecked(self.spec.use_formula)
        layout.addWidget(self.use_formula)
        self.x_expr = QtWidgets.QLineEdit(self.spec.x_expr)
        self.y_expr = QtWidgets.QLineEdit(self.spec.y_expr)
        expr_form = QtWidgets.QFormLayout()
        expr_form.addRow("X =", self.x_expr)
        expr_form.addRow("Y =", self.y_expr)
        layout.addLayout(expr_form)
        self.use_formula.toggled.connect(self.x_expr.setEnabled)
        self.use_formula.toggled.connect(self.y_expr.setEnabled)
        self.x_expr.setEnabled(self.use_formula.isChecked())
        self.y_expr.setEnabled(self.use_formula.isChecked())
        layout.addWidget(QtWidgets.QLabel("関数例: sin, cos, exp, log, log10, sqrt, abs, minimum, maximum, pi"))
        style_form = QtWidgets.QFormLayout()
        self.plot_style = QtWidgets.QComboBox()
        for label, value in PLOT_STYLES:
            self.plot_style.addItem(label, value)
        self.plot_style.setCurrentIndex(max(0, self.plot_style.findData(self.spec.plot_style)))
        style_form.addRow("プロットの種類", self.plot_style)

        self.width = QtWidgets.QDoubleSpinBox()
        self.width.setRange(0.5, 20.0)
        self.width.setSingleStep(0.5)
        self.width.setSuffix(" px")
        self.width.setValue(self.spec.width)
        self.width.setToolTip("データ点間を結ぶ線の幅")
        style_form.addRow("線の幅", self.width)

        self.marker_size = QtWidgets.QDoubleSpinBox()
        self.marker_size.setRange(1.0, 50.0)
        self.marker_size.setSingleStep(1.0)
        self.marker_size.setSuffix(" px")
        self.marker_size.setValue(self.spec.marker_size)
        self.marker_size.setToolTip("各データ点に描く丸マーカーの直径")
        style_form.addRow("点のサイズ（直径）", self.marker_size)
        layout.addLayout(style_form)

        row = QtWidgets.QHBoxLayout()
        self.color = self.spec.color
        self.color_button = QtWidgets.QPushButton("色を選択")
        self.color_button.clicked.connect(self.choose_color)
        self.visible = QtWidgets.QCheckBox("表示する")
        self.visible.setChecked(self.spec.visible)
        row.addWidget(self.color_button)
        row.addWidget(self.visible)
        row.addStretch()
        layout.addLayout(row)
        self._set_button_color()
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        if editing:
            delete_btn = buttons.addButton("この曲線を削除", QtWidgets.QDialogButtonBox.ButtonRole.DestructiveRole)
            delete_btn.clicked.connect(self._confirm_delete)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_button_color(self):
        self.color_button.setStyleSheet(f"background-color: {self.color}; color: white")

    def choose_color(self):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.color), self)
        if c.isValid():
            self.color = c.name()
            self._set_button_color()

    def _confirm_delete(self):
        if QtWidgets.QMessageBox.question(self, "削除確認", "この曲線をグラフから削除しますか？") == \
                QtWidgets.QMessageBox.StandardButton.Yes:
            self.delete_requested = True
            self.accept()

    def accept(self):
        self.spec.name = self.name.text().strip() or "Curve"
        self.spec.columns = {letter: combo.currentData() for letter, combo in self.mapping.items()
                             if combo.currentData() is not None and combo.currentData() >= 0}
        self.spec.use_formula = self.use_formula.isChecked()
        self.spec.x_expr = self.x_expr.text().strip()
        self.spec.y_expr = self.y_expr.text().strip()
        self.spec.color = self.color
        self.spec.width = self.width.value()
        self.spec.plot_style = self.plot_style.currentData()
        self.spec.marker_size = self.marker_size.value()
        self.spec.visible = self.visible.isChecked()
        super().accept()


class AxisDialog(QtWidgets.QDialog):
    """XY軸ラベル・範囲・対数・グリッドの一括設定。"""

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("グラフ・軸の設定")
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.title = QtWidgets.QLineEdit(settings.get("title", ""))
        self.xlabel = QtWidgets.QLineEdit(settings.get("xlabel", "X"))
        self.ylabel = QtWidgets.QLineEdit(settings.get("ylabel", "Y"))
        form.addRow("タイトル", self.title)
        form.addRow("X軸ラベル", self.xlabel)
        form.addRow("Y軸ラベル", self.ylabel)
        self.limits = {}
        for axis in "xy":
            for edge in ("min", "max"):
                edit = QtWidgets.QLineEdit()
                value = settings.get(f"{axis}_{edge}")
                edit.setText("" if value is None else f"{value:.10g}")
                edit.setPlaceholderText("空欄 = Auto")
                self.limits[f"{axis}_{edge}"] = edit
                form.addRow(f"{axis.upper()}軸 {edge}", edit)
        layout.addLayout(form)
        self.x_log = QtWidgets.QCheckBox("X軸を対数表示")
        self.y_log = QtWidgets.QCheckBox("Y軸を対数表示")
        self.grid = QtWidgets.QCheckBox("グリッドを表示")
        self.x_log.setChecked(settings.get("x_log", False))
        self.y_log.setChecked(settings.get("y_log", False))
        self.grid.setChecked(settings.get("grid", True))
        for w in (self.x_log, self.y_log, self.grid):
            layout.addWidget(w)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def settings(self) -> dict:
        data = {"title": self.title.text(), "xlabel": self.xlabel.text(),
                "ylabel": self.ylabel.text(), "x_log": self.x_log.isChecked(),
                "y_log": self.y_log.isChecked(), "grid": self.grid.isChecked()}
        for key, edit in self.limits.items():
            data[key] = float(edit.text()) if edit.text().strip() else None
        for axis in "xy":
            lo, hi = data[f"{axis}_min"], data[f"{axis}_max"]
            if lo is not None and hi is not None and lo >= hi:
                raise ValueError(f"{axis.upper()}軸では最小値 < 最大値 にしてください")
            if data[f"{axis}_log"] and any(v is not None and v <= 0 for v in (lo, hi)):
                raise ValueError(f"{axis.upper()}軸を対数にする場合は正の範囲を指定してください")
        return data

    def accept(self):
        try:
            self.settings()
        except ValueError as exc:
            message_error(self, "軸設定エラー", str(exc))
            return
        super().accept()
