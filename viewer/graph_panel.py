"""グラフ1枚分のUI。描画・マウス操作・曲線プロパティ・2点マーカーを担当。"""
from __future__ import annotations

import math
from pathlib import Path
import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets, QtGui

from .models import CurveSpec, DataRecord, COLORS, new_id
from .formula import calculate_xy, FormulaError
from .dialogs import AxisDialog, message_error
from .plot_viewbox import MiddlePanViewBox
from .curve_style import plot_kwargs
from .plot_optimization import prepare_plot_data
from .legend_interaction import curve_id_at_legend_label
from .font_settings import FONT_SIZE_DEFAULTS, get_font_sizes
from .point_selection import (visible_mask, masked_y, rectangle_indices,
                              hide_indices, visible_bounds)


class ClickableAxis(pg.AxisItem):
    clicked = QtCore.Signal()

    def mouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
            ev.accept()
        else:
            super().mouseClickEvent(ev)


class DroppablePlot(pg.PlotWidget):
    fileDropped = QtCore.Signal(str)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if any(url.isLocalFile() and Path(url.toLocalFile()).is_file()
               for url in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile() and Path(url.toLocalFile()).is_file():
                self.fileDropped.emit(url.toLocalFile())
                event.acceptProposedAction()
                return
        event.ignore()


class GraphPanel(QtWidgets.QWidget):
    """状態と曲線はグラフごとに独立。読み込んだデータ自体はDataManagerから共有する。"""
    fileDropped = QtCore.Signal(str, str)   # graph_id, path
    editCurve = QtCore.Signal(str, str)     # graph_id, curve_id
    saveRequested = QtCore.Signal(str)
    duplicateRequested = QtCore.Signal(str)
    exportRequested = QtCore.Signal(str)
    templateRequested = QtCore.Signal(str)
    saveTemplateRequested = QtCore.Signal(str)
    deleteRequested = QtCore.Signal(str)
    changed = QtCore.Signal(str)

    def __init__(self, title: str, graph_id: str | None = None, parent=None):
        super().__init__(parent)
        self.graph_id = graph_id or new_id()
        self.title_text = title
        self.xlabel = "X"
        self.ylabel = "Y"
        self.x_log = False
        self.y_log = False
        self.show_grid = True
        self.title_font_size = FONT_SIZE_DEFAULTS["title_font_size"]
        self.label_font_size = FONT_SIZE_DEFAULTS["label_font_size"]
        self.tick_font_size = FONT_SIZE_DEFAULTS["tick_font_size"]
        self.curves: list[CurveSpec] = []
        self.items: dict[str, pg.PlotDataItem] = {}
        self.values: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self.display_values: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._marker_items: list[pg.TargetItem] = []
        # 選択は一時的な操作状態。非表示の行番号はCurveSpecに保持する。
        self.selected_points: dict[str, set[int]] = {}
        self.selection_items: dict[str, pg.ScatterPlotItem] = {}
        self._markers: list[tuple[float, float]] = []
        self._marking_guard = False
        self._history: list[list[list[float]]] = []
        self._history_pending = None
        self._changing_range = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)
        top = QtWidgets.QHBoxLayout()
        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold")
        top.addWidget(self.title_label)
        top.addStretch()
        self.menu_button = QtWidgets.QToolButton()
        self.menu_button.setText("⋯")
        self.menu_button.setToolTip("グラフの保存・設定・削除")
        self.menu_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QtWidgets.QMenu(self)
        for label, signal in [("グラフを複製", self.duplicateRequested),
                              ("グラフを保存（JSON）", self.saveRequested),
                              ("画像として出力（PNG / SVG）", self.exportRequested),
                              ("テンプレートを適用", self.templateRequested),
                              ("現在の設定をテンプレート保存", self.saveTemplateRequested),
                              ("グラフを削除", self.deleteRequested)]:
            menu.addAction(label, lambda checked=False, sig=signal: sig.emit(self.graph_id))
        self.menu_button.setMenu(menu)
        top.addWidget(self.menu_button)
        layout.addLayout(top)

        tools = QtWidgets.QHBoxLayout()
        tools.setSpacing(3)
        self.mode_group = QtWidgets.QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for key, text in [("rect", "範囲"), ("pan", "Pan"), ("marker", "2点測定"),
                          ("select", "部分消去")]:
            button = QtWidgets.QToolButton()
            button.setText(text)
            button.setToolTip({"rect": "左ドラッグで範囲拡大／中央ドラッグでPan", "pan": "左ドラッグで移動",
                               "marker": "クリックで2点配置。マーカーはドラッグ可能",
                               "select": "左ドラッグで範囲内の点を選択／Ctrl+クリックで1点の選択を切替"}[key])
            button.setCheckable(True)
            self.mode_group.addButton(button)
            button.clicked.connect(lambda checked=False, m=key: self.set_mode(m))
            if key == "rect":
                button.setChecked(True)
            tools.addWidget(button)
        for text, callback in [("Auto", self.auto_range), ("Undo", self.undo_range),
                               ("軸設定", self.edit_axes)]:
            b = QtWidgets.QToolButton()
            b.setText(text)
            b.clicked.connect(callback)
            tools.addWidget(b)
        curve_button = QtWidgets.QToolButton()
        curve_button.setText("曲線...")
        curve_button.setToolTip("曲線を一覧から選んでプロパティを編集")
        curve_button.clicked.connect(self.choose_curve)
        tools.addWidget(curve_button)
        # 画面を4分割しても操作ボタンが横にはみ出さないよう、
        # 部分消去用の3ボタンはモード専用の2段目にまとめる。
        mask_toolbar = QtWidgets.QWidget(self)
        mask_tools = QtWidgets.QHBoxLayout(mask_toolbar)
        mask_tools.setContentsMargins(0, 0, 0, 0)
        mask_tools.setSpacing(3)
        self.mask_toolbar = mask_toolbar
        self.hide_points_button = QtWidgets.QToolButton()
        self.hide_points_button.setText("選択点を非表示")
        self.hide_points_button.setToolTip("部分消去モードで選択した点だけを非表示にする")
        self.hide_points_button.clicked.connect(self.hide_selected_points)
        mask_tools.addWidget(self.hide_points_button)
        self.restore_points_button = QtWidgets.QToolButton()
        self.restore_points_button.setText("すべて表示")
        self.restore_points_button.setToolTip("このグラフの部分消去を取り消し、すべての点を復元")
        self.restore_points_button.clicked.connect(self.show_all_points)
        mask_tools.addWidget(self.restore_points_button)
        self.clear_selection_button = QtWidgets.QToolButton()
        self.clear_selection_button.setText("選択解除")
        self.clear_selection_button.clicked.connect(self.clear_point_selection)
        mask_tools.addWidget(self.clear_selection_button)
        mask_tools.addStretch()
        clear_button = QtWidgets.QToolButton()
        clear_button.setText("マーカー消去")
        clear_button.clicked.connect(self.clear_markers)
        tools.addWidget(clear_button)
        self.hover_box = QtWidgets.QCheckBox("座標")
        self.hover_box.setChecked(True)
        tools.addWidget(self.hover_box)
        tools.addStretch()
        layout.addLayout(tools)
        layout.addWidget(mask_toolbar)
        mask_toolbar.hide()

        self.axis_x = ClickableAxis(orientation="bottom")
        self.axis_y = ClickableAxis(orientation="left")
        plot_item = pg.PlotItem(axisItems={"bottom": self.axis_x, "left": self.axis_y},
                                viewBox=MiddlePanViewBox(), enableMenu=False)
        self.plot = DroppablePlot(plotItem=plot_item)
        self.plot.setMinimumSize(210, 135)
        self.plot.setBackground("w")
        self.plot_item = self.plot.getPlotItem()
        self.plot_item.showGrid(x=True, y=True, alpha=0.2)
        self._update_labels_and_fonts()
        self.plot_item.addLegend(offset=(10, 10))
        # 凡例の文字だけをダブルクリックしてもプロパティを開けるようにする。
        # イベントはviewport側で受け、既存の曲線のダブルクリックとは干渉しない。
        self.plot.viewport().installEventFilter(self)
        self.vb = self.plot_item.getViewBox()
        self.vb.setMouseMode(pg.ViewBox.RectMode)
        self.vb.setMenuEnabled(False)
        self.vb.selectionFinished.connect(self.select_rectangle)
        self.plot.fileDropped.connect(lambda p: self.fileDropped.emit(self.graph_id, p))
        self.axis_x.clicked.connect(self.edit_axes)
        self.axis_y.clicked.connect(self.edit_axes)
        self.vb.sigRangeChangedManually.connect(self._range_changed_manually)
        self._history_timer = QtCore.QTimer(self)
        self._history_timer.setSingleShot(True)
        self._history_timer.setInterval(250)
        self._history_timer.timeout.connect(self._commit_history)
        self._hover_proxy = pg.SignalProxy(self.plot.scene().sigMouseMoved, rateLimit=24,
                                          slot=self._mouse_moved)
        self.plot.scene().sigMouseClicked.connect(self._mouse_clicked)
        layout.addWidget(self.plot, stretch=1)
        self.information = QtWidgets.QLabel("ファイルをグラフにドラッグ＆ドロップしてください")
        self.information.setMinimumHeight(22)
        self.information.setWordWrap(True)
        layout.addWidget(self.information)
        self._marker_label = QtWidgets.QLabel("")
        layout.addWidget(self._marker_label)
        self.setStyleSheet("GraphPanel { border: 1px solid #d1d5db; }")
        shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self)
        shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.undo_range)
        self.mode = "rect"
        self._last_stable_range = self._range_snapshot()

    def eventFilter(self, watched, event):
        """凡例の文字を左ダブルクリックしたときだけ曲線の編集を要求する。"""
        if (watched is self.plot.viewport()
                and event.type() == QtCore.QEvent.Type.MouseButtonDblClick
                and event.button() == QtCore.Qt.MouseButton.LeftButton):
            # QWidgetのマウス座標をpyqtgraphのシーン座標へ変換する。
            scene_position = self.plot.mapToScene(event.position().toPoint())
            curve_id = curve_id_at_legend_label(
                self.plot_item.legend, scene_position, self.items
            )
            if curve_id is not None:
                self.editCurve.emit(self.graph_id, curve_id)
                return True  # 凡例側で不要なドラッグ・ズーム操作をさせない
        return super().eventFilter(watched, event)

    def set_mode(self, mode: str):
        self.mode = mode
        self.vb.point_selection_mode = mode == "select"
        self.mask_toolbar.setVisible(mode == "select")
        self.vb.setMouseMode(pg.ViewBox.PanMode if mode in ("pan", "marker")
                             else pg.ViewBox.RectMode)

    def _range_snapshot(self):
        return [list(v) for v in self.vb.viewRange()]

    def _same_range(self, a, b) -> bool:
        return bool(np.allclose(np.asarray(a), np.asarray(b), rtol=1e-10, atol=1e-12))

    def _range_changed_manually(self, *_):
        if self._changing_range:
            return
        if self._history_pending is None:
            # 最初のマウス操作の直前に保持していた範囲を推定する。
            self._history_pending = getattr(self, "_last_stable_range", self._range_snapshot())
        self._history_timer.start()

    def _commit_history(self):
        if self._history_pending is not None:
            now = self._range_snapshot()
            if not self._same_range(now, self._history_pending):
                self._history.append(self._history_pending)
                self._history = self._history[-100:]
            self._history_pending = None
            self._last_stable_range = now

    def _push_previous(self):
        self._commit_history()
        self._history.append(self._range_snapshot())
        self._history = self._history[-100:]

    def auto_range(self):
        # pyqtgraphの標準autoRangeは非表示（NaN）の点のX境界を考慮する
        # 場合があるため、有効な可視点のみから範囲を明示的に計算する。
        datasets = []
        for curve in self.curves:
            if not curve.visible or curve.id not in self.values:
                continue
            x, y = self.values[curve.id]
            datasets.append((x, masked_y(y, curve.hidden_indices)))
        bounds = visible_bounds(datasets, self.x_log, self.y_log)
        if bounds is None:
            return
        xmin, xmax, ymin, ymax = bounds
        # 一定値のみでも正常な矩形領域になるようにする。
        if xmin == xmax:
            pad = max(abs(xmin) * .02, .01)
            xmin, xmax = xmin-pad, xmax+pad
        if ymin == ymax:
            pad = max(abs(ymin) * .02, .01)
            ymin, ymax = ymin-pad, ymax+pad
        self._push_previous()
        self._changing_range = True
        try:
            self.vb.disableAutoRange()
            self.vb.setRange(xRange=(xmin, xmax), yRange=(ymin, ymax), padding=0.02)
        finally:
            self._changing_range = False
        self._last_stable_range = self._range_snapshot()

    def undo_range(self):
        self._commit_history()
        if not self._history:
            return
        limits = self._history.pop()
        self._changing_range = True
        try:
            self.vb.setRange(xRange=limits[0], yRange=limits[1], padding=0)
        finally:
            self._changing_range = False
        self._last_stable_range = self._range_snapshot()

    def _update_labels_and_fonts(self):
        """Qt/pyqtgraphへ文字サイズをまとめて適用する（X/Y共通）。"""
        self.plot_item.setTitle(self.title_text, size=f"{self.title_font_size}pt")
        label_style = {"font-size": f"{self.label_font_size}pt"}
        self.plot_item.setLabel("bottom", self.xlabel, **label_style)
        self.plot_item.setLabel("left", self.ylabel, **label_style)
        tick_font = QtGui.QFont(self.plot.font())
        tick_font.setPointSize(self.tick_font_size)
        self.axis_x.setTickFont(tick_font)
        self.axis_y.setTickFont(tick_font)
        # フォント変更後は目盛りが収まるように軸の占有幅を再計算。
        self.axis_x.setHeight(None)
        self.axis_y.setWidth(None)

    def settings(self) -> dict:
        ranges = self.vb.viewRange()
        def physical(value, is_log):
            return float(10 ** value) if is_log else float(value)
        return {"title": self.title_text, "xlabel": self.xlabel, "ylabel": self.ylabel,
                "title_font_size": self.title_font_size,
                "label_font_size": self.label_font_size,
                "tick_font_size": self.tick_font_size,
                "x_log": self.x_log, "y_log": self.y_log, "grid": self.show_grid,
                "x_min": physical(ranges[0][0], self.x_log),
                "x_max": physical(ranges[0][1], self.x_log),
                "y_min": physical(ranges[1][0], self.y_log),
                "y_max": physical(ranges[1][1], self.y_log)}

    def edit_axes(self):
        dialog = AxisDialog(self.settings(), self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.apply_settings(dialog.settings())

    def apply_settings(self, settings: dict, record_history: bool = True):
        # 先に検証する。保存済み設定が不正でも途中まで表示を変えない。
        sizes = get_font_sizes(settings, self.settings())
        if record_history:
            self._push_previous()
        self._changing_range = True
        try:
            previous_x_log = self.x_log
            self.title_text = settings.get("title", self.title_text)
            self.xlabel = settings.get("xlabel", self.xlabel)
            self.ylabel = settings.get("ylabel", self.ylabel)
            self.x_log = bool(settings.get("x_log", self.x_log))
            self.y_log = bool(settings.get("y_log", self.y_log))
            self.show_grid = bool(settings.get("grid", self.show_grid))
            self.title_label.setText(self.title_text)
            self.title_font_size = sizes["title_font_size"]
            self.label_font_size = sizes["label_font_size"]
            self.tick_font_size = sizes["tick_font_size"]
            self._update_labels_and_fonts()
            # X対数設定の変更時は最適化の安全性も再判定する。
            # (X<=0の値はlog変換で非有限になるため、clipToViewは使用しない。)
            if previous_x_log != self.x_log:
                for curve in self.curves:
                    item = self.items.get(curve.id)
                    if item is None or curve.id not in self.values:
                        continue
                    x, y = self.values[curve.id]
                    display_y = masked_y(y, curve.hidden_indices)
                    plan = prepare_plot_data(x, display_y, x_log=self.x_log)
                    self._configure_plot_item(item, plan)
                    item.setData(plan.x, plan.y, **self._curve_plot_options(curve))
                    self.display_values[curve.id] = (plan.x, plan.y)
            self.plot_item.setLogMode(x=self.x_log, y=self.y_log)
            self.plot_item.showGrid(x=self.show_grid, y=self.show_grid, alpha=0.2)
            for idx, axis in enumerate("xy"):
                low, high = settings.get(f"{axis}_min"), settings.get(f"{axis}_max")
                if low is None or high is None:
                    self.vb.enableAutoRange(axis=idx)
                    continue
                if (self.x_log if axis == "x" else self.y_log):
                    low, high = math.log10(low), math.log10(high)
                if axis == "x":
                    self.vb.setXRange(low, high, padding=0)
                else:
                    self.vb.setYRange(low, high, padding=0)
        finally:
            self._changing_range = False
        self._last_stable_range = self._range_snapshot()
        self.changed.emit(self.graph_id)

    def add_curve(self, spec: CurveSpec):
        self.curves.append(spec)
        self.changed.emit(self.graph_id)

    def find_curve(self, curve_id: str) -> CurveSpec | None:
        return next((curve for curve in self.curves if curve.id == curve_id), None)

    def choose_curve(self):
        if not self.curves:
            return
        labels = [f"{i+1}: {c.name} ({Path(c.path).name})" for i, c in enumerate(self.curves)]
        selected, ok = QtWidgets.QInputDialog.getItem(self, "曲線を選択", "プロパティを編集する曲線", labels, 0, False)
        if ok:
            self.editCurve.emit(self.graph_id, self.curves[labels.index(selected)].id)

    def delete_curve(self, curve_id: str):
        self.curves = [c for c in self.curves if c.id != curve_id]
        item = self.items.pop(curve_id, None)
        if item is not None:
            self.plot_item.removeItem(item)
            if self.plot_item.legend is not None:
                self.plot_item.legend.removeItem(item)
        self.values.pop(curve_id, None)
        self.display_values.pop(curve_id, None)
        self.selected_points.pop(curve_id, None)
        self._clear_selection_item(curve_id)
        self.clear_markers()
        self.changed.emit(self.graph_id)

    @staticmethod
    def _configure_plot_item(item: pg.PlotDataItem, plan) -> None:
        """Xが非単調な曲線には、昇順を前提とした高速化を適用しない。"""
        item.setClipToView(plan.clip_to_view)
        item.setDownsampling(ds=1, auto=plan.auto_downsample, method="peak")

    @staticmethod
    def _curve_plot_options(spec: CurveSpec) -> dict:
        options = plot_kwargs(spec)
        # MPMSのもともとの欠損値、部分消去した点の両方で線を分断。
        options["connect"] = "finite"
        return options

    def _refresh_curve_display(self, spec: CurveSpec):
        """ディスク読み込みや計算をせず、部分消去と描画を更新する。"""
        if spec.id not in self.values:
            return
        x, y = self.values[spec.id]
        plan = prepare_plot_data(x, masked_y(y, spec.hidden_indices), x_log=self.x_log)
        self.display_values[spec.id] = (plan.x, plan.y)
        item = self.items.get(spec.id)
        if item is not None:
            self._configure_plot_item(item, plan)
            item.setData(plan.x, plan.y, **self._curve_plot_options(spec))
            item.setVisible(spec.visible)

    def set_curve_data(self, spec: CurveSpec, record: DataRecord) -> None:
        x, y = calculate_xy(record.array, spec.columns, spec.use_formula,
                            spec.x_expr, spec.y_expr)
        # 元データは解析・マーカー用にそのまま保持する。
        self.values[spec.id] = (x, y)
        # 更新後の行数が短くなっても、範囲外の保存済みインデックスは安全に無視。
        plan = prepare_plot_data(x, masked_y(y, spec.hidden_indices), x_log=self.x_log)
        self.display_values[spec.id] = (plan.x, plan.y)
        item = self.items.get(spec.id)
        options = self._curve_plot_options(spec)
        if item is None:
            item = self.plot_item.plot(plan.x, plan.y, name=spec.name, **options)
            # 線は線上を、点表示の場合はマーカーをダブルクリックして編集できる。
            item.setCurveClickable(True, width=10)
            item.sigClicked.connect(lambda _, ev, cid=spec.id: self._curve_clicked(cid, ev))
            self.items[spec.id] = item
        else:
            # 変更後のXの並びに応じた設定を、setDataより先に適用する。
            self._configure_plot_item(item, plan)
            # pen / symbol を毎回明示して、線のみ⇔点のみ切替時に古い表示を残さない。
            item.setData(plan.x, plan.y, **options)
            item.opts["name"] = spec.name
            legend = self.plot_item.legend
            if legend is not None:
                legend.removeItem(item)
                legend.addItem(item, spec.name)
        self._configure_plot_item(item, plan)
        item.setVisible(spec.visible)
        self.information.setText(f"曲線: {len(self.curves)}本（ダブルクリックでプロパティ）")
        self.clear_markers()
        self.clear_point_selection()
        self._last_stable_range = self._range_snapshot()

    def _curve_clicked(self, cid: str, event):
        if event.double():
            self.editCurve.emit(self.graph_id, cid)

    def _point_to_plot(self, x: np.ndarray, y: np.ndarray):
        with np.errstate(all="ignore"):
            xp = np.log10(x) if self.x_log else x
            yp = np.log10(y) if self.y_log else y
        return xp, yp

    def _nearest(self, scene_pos) -> tuple[str, int, float] | None:
        """表示座標から近い元データ点を探す（大きい配列は粗探索→近傍を精査）。"""
        point = self.vb.mapSceneToView(scene_pos)
        ranges = self.vb.viewRange()
        xspan = max(abs(ranges[0][1]-ranges[0][0]), 1e-14)
        yspan = max(abs(ranges[1][1]-ranges[1][0]), 1e-14)
        w = max(self.vb.width(), 1)
        h = max(self.vb.height(), 1)
        best = None
        for spec in self.curves:
            if not spec.visible or spec.id not in self.values:
                continue
            x, y = self.values[spec.id]
            n = len(x)
            if n == 0:
                continue
            available = visible_mask(n, spec.hidden_indices)
            if not available.any():
                continue
            stride = max(1, n // 4000)
            sample = np.arange(0, n, stride)
            xs, ys = self._point_to_plot(x[sample], y[sample])
            with np.errstate(all="ignore"):
                dist = ((xs-point.x()) / xspan*w)**2 + ((ys-point.y())/yspan*h)**2
            dist[~np.isfinite(dist) | ~available[sample]] = np.inf
            idx = int(np.argmin(dist))
            center = int(sample[idx])
            lo, hi = max(0, center-2*stride), min(n, center+2*stride+1)
            cx, cy = self._point_to_plot(x[lo:hi], y[lo:hi])
            with np.errstate(all="ignore"):
                fine = ((cx-point.x())/xspan*w)**2 + ((cy-point.y())/yspan*h)**2
            fine[~np.isfinite(fine) | ~available[lo:hi]] = np.inf
            ix = int(np.argmin(fine)) + lo
            distance = float(fine[ix-lo])
            if not np.isfinite(distance):
                continue
            if best is None or distance < best[2]:
                best = (spec.id, ix, distance)
        return best

    def _mouse_moved(self, evt):
        if not self.hover_box.isChecked():
            return
        scene_pos = evt[0]
        if not self.vb.sceneBoundingRect().contains(scene_pos):
            return
        near = self._nearest(scene_pos)
        if near is None:
            return
        cid, idx, dist2 = near
        if dist2 <= 18**2:
            spec = self.find_curve(cid)
            x, y = self.values[cid]
            self.information.setText(f"{spec.name}: X = {x[idx]:.9g}  Y = {y[idx]:.9g}  [行 {idx+1}]")
        else:
            self.information.setText(f"曲線: {len(self.curves)}本")

    def _mouse_clicked(self, ev):
        if (getattr(self, "mode", "rect") == "select"
                and ev.button() == QtCore.Qt.MouseButton.LeftButton
                and ev.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier):
            if self.vb.sceneBoundingRect().contains(ev.scenePos()):
                self.toggle_nearest_selection(ev.scenePos())
                ev.accept()
            return
        if getattr(self, "mode", "rect") != "marker" or ev.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        if not self.vb.sceneBoundingRect().contains(ev.scenePos()):
            return
        near = self._nearest(ev.scenePos())
        if near is None or not np.isfinite(near[2]):
            return
        cid, idx, _ = near
        self._place_marker(float(self.values[cid][0][idx]), float(self.values[cid][1][idx]))
        ev.accept()

    def select_rectangle(self, xmin: float, xmax: float, ymin: float, ymax: float):
        """表示中のすべての曲線から範囲内のデータ点を選択する。"""
        self.clear_point_selection()
        count = 0
        for spec in self.curves:
            if not spec.visible or spec.id not in self.values:
                continue
            x, y = self.values[spec.id]
            xp, yp = self._point_to_plot(x, y)
            indices = rectangle_indices(xp, yp, (xmin, xmax, ymin, ymax),
                                        available=visible_mask(len(x), spec.hidden_indices))
            if len(indices):
                self.selected_points[spec.id] = set(int(i) for i in indices)
                count += len(indices)
        self._refresh_selection_overlays()
        self.information.setText(f"{count}点を選択しました。「選択点を非表示」で隠せます")

    def toggle_nearest_selection(self, scene_pos):
        near = self._nearest(scene_pos)
        if near is None or near[2] > 18**2:
            return
        cid, idx, _ = near
        selected = self.selected_points.setdefault(cid, set())
        if idx in selected:
            selected.remove(idx)
            if not selected:
                self.selected_points.pop(cid, None)
        else:
            selected.add(idx)
        self._refresh_selection_overlays()
        self.information.setText(f"{sum(map(len, self.selected_points.values()))}点を選択中")

    def _clear_selection_item(self, cid: str):
        item = self.selection_items.pop(cid, None)
        if item is not None:
            self.plot_item.removeItem(item)

    def _refresh_selection_overlays(self):
        """選択位置だけ強調する。大量選択では強調点だけ間引き、実際の選択は保持。"""
        for cid in list(self.selection_items):
            self._clear_selection_item(cid)
        for spec in self.curves:
            indices = self.selected_points.get(spec.id)
            if not indices or spec.id not in self.values:
                continue
            x, y = self.values[spec.id]
            idx = np.asarray(sorted(indices), dtype=int)
            idx = idx[(idx >= 0) & (idx < len(x))]
            if not len(idx):
                continue
            if len(idx) > 2000:
                idx = idx[np.linspace(0, len(idx)-1, 2000).astype(int)]
            xp, yp = self._point_to_plot(x[idx], y[idx])
            points = np.isfinite(xp) & np.isfinite(yp)
            if not np.any(points):
                continue
            item = pg.ScatterPlotItem(x=xp[points], y=yp[points], size=8,
                                      pen=pg.mkPen("#db143e", width=1.5),
                                      brush=pg.mkBrush(255, 225, 70, 150), pxMode=True)
            item.setZValue(100)
            self.plot_item.addItem(item, ignoreBounds=True)
            self.selection_items[spec.id] = item

    def clear_point_selection(self):
        self.selected_points.clear()
        for cid in list(self.selection_items):
            self._clear_selection_item(cid)

    def hide_selected_points(self):
        """選択した行番号だけ隠す。元データ・式・他グラフは変更しない。"""
        count = 0
        for spec in self.curves:
            selected = self.selected_points.get(spec.id)
            if not selected or spec.id not in self.values:
                continue
            n = len(self.values[spec.id][0])
            old = len(spec.hidden_indices)
            spec.hidden_indices = hide_indices(spec.hidden_indices, selected, n)
            count += len(spec.hidden_indices) - old
            self._refresh_curve_display(spec)
        self.clear_point_selection()
        self.clear_markers()
        if count:
            self.information.setText(f"{count}点を非表示にしました。「すべて表示」で復元できます")
            self.changed.emit(self.graph_id)

    def show_all_points(self):
        """グラフ内のすべての曲線の部分消去を解除する。"""
        changed = False
        for spec in self.curves:
            if spec.hidden_indices:
                spec.hidden_indices = []
                self._refresh_curve_display(spec)
                changed = True
        self.clear_point_selection()
        self.clear_markers()
        if changed:
            self.information.setText("非表示の点をすべて復元しました")
            self.changed.emit(self.graph_id)

    def _place_marker(self, x: float, y: float):
        if len(self._marker_items) >= 2:
            self.clear_markers()
        label = "AB"[len(self._marker_items)]
        # TargetItemは表示データの座標系に置く。対数軸ではlog10座標。
        xp, yp = self._point_to_plot(np.asarray([x]), np.asarray([y]))
        marker = pg.TargetItem(pos=(float(xp[0]), float(yp[0])), label=label, movable=True,
                               pen=pg.mkPen("#ce3d24" if label == "A" else "#24a175", width=2))
        marker.sigPositionChangeFinished.connect(lambda obj, m=marker: self._snap_marker(m))
        self.plot_item.addItem(marker, ignoreBounds=True)
        self._marker_items.append(marker)
        self._markers.append((x, y))
        self._show_markers()

    def _snap_marker(self, marker):
        if self._marking_guard:
            return
        near = self._nearest(self.vb.mapViewToScene(marker.pos()))
        if near is None:
            return
        cid, idx, _ = near
        x, y = self.values[cid]
        n = self._marker_items.index(marker)
        self._markers[n] = (float(x[idx]), float(y[idx]))
        xp, yp = self._point_to_plot(np.asarray([x[idx]]), np.asarray([y[idx]]))
        self._marking_guard = True
        try:
            marker.setPos(float(xp[0]), float(yp[0]))
        finally:
            self._marking_guard = False
        self._show_markers()

    def _show_markers(self):
        if len(self._markers) < 2:
            self._marker_label.setText("Marker A: 設置済み / Marker B: 未設定")
            return
        (x1, y1), (x2, y2) = self._markers
        dx, dy = x2-x1, y2-y1
        slope = f"{dy/dx:.8g}" if dx != 0 else "未定義 (Δx=0)"
        self._marker_label.setText(f"A=({x1:.7g}, {y1:.7g})  B=({x2:.7g}, {y2:.7g})  |  "
                                   f"Δx={dx:.7g}  Δy={dy:.7g}  Δy/Δx={slope}")

    def clear_markers(self):
        for marker in self._marker_items:
            self.plot_item.removeItem(marker)
        self._marker_items.clear()
        self._markers.clear()
        self._marker_label.setText("")

    def to_dict(self) -> dict:
        return {"id": self.graph_id, "settings": self.settings(),
                "curves": [c.to_dict() for c in self.curves]}

    def template_data(self) -> dict:
        # 曲線ごとの表示形式・線幅・マーカーサイズもテンプレートへ保存。
        # 元ファイルと数式は含めず、曲線数が違えば順番に繰り返し適用する。
        return {"settings": self.settings(),
                "palette": [c.color for c in self.curves] or COLORS,
                "curve_styles": [
                    {"plot_style": c.plot_style, "width": c.width, "marker_size": c.marker_size}
                    for c in self.curves
                ]}

    def apply_template(self, template: dict):
        self.apply_settings(template.get("settings", {}))
        palette = template.get("palette", COLORS) or COLORS
        styles = template.get("curve_styles", [])
        for i, curve in enumerate(self.curves):
            curve.color = palette[i % len(palette)]
            if styles:
                style = styles[i % len(styles)]
                curve.plot_style = style.get("plot_style", curve.plot_style)
                curve.width = style.get("width", curve.width)
                curve.marker_size = style.get("marker_size", curve.marker_size)
            item = self.items.get(curve.id)
            if item is not None:
                # データの再計算やディスクの読み直しをせず、見た目だけ変更。
                item.setData(*self.display_values[curve.id], **self._curve_plot_options(curve))
                legend = self.plot_item.legend
                if legend is not None:
                    legend.removeItem(item)
                    legend.addItem(item, curve.name)
        self.changed.emit(self.graph_id)
