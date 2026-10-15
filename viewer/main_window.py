"""メインウィンドウ。機能モジュール間の連携を担当し、詳細処理はそれぞれに委譲する。"""
from __future__ import annotations

from pathlib import Path
from PySide6 import QtCore, QtWidgets
import pyqtgraph.exporters

from .models import ReaderOptions, CurveSpec, COLORS
from .data_manager import DataManager
from .file_tree import FileTree
from .dialogs import ReaderDialog, CurveDialog, message_error
from .graph_panel import GraphPanel
from .serialization import save_graph, load_graph, TemplateStore


class MainWindow(QtWidgets.QMainWindow):
    MAX_VISIBLE = 4

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Measurement Viewer v0.1.2")
        self.resize(1450, 850)
        self.data_manager = DataManager(self)
        self.data_manager.loaded.connect(self._on_data_loaded)
        self.data_manager.failed.connect(self._on_data_failed)
        self.templates = TemplateStore()
        self.graphs: dict[str, GraphPanel] = {}
        self._pending_drops: dict[str, list[str]] = {}
        self._pending_edits: dict[str, list[tuple[str, str]]] = {}

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)
        sidebar = QtWidgets.QWidget()
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar)
        sidebar_layout.addWidget(QtWidgets.QLabel("ファイル一覧（ドラッグしてグラフに追加）"))
        self.tree = FileTree()
        self.tree.fileActivated.connect(self.quicklook)
        sidebar_layout.addWidget(self.tree, stretch=4)
        row = QtWidgets.QHBoxLayout()
        for text, callback in [("フォルダを開く", self.select_folder),
                               ("クイックルック", self.quicklook_selected),
                               ("更新", self.refresh_selected)]:
            button = QtWidgets.QPushButton(text)
            button.clicked.connect(callback)
            row.addWidget(button)
        sidebar_layout.addLayout(row)
        sidebar_layout.addWidget(QtWidgets.QLabel("グラフ一覧（チェックで表示・非表示、最大4枚）"))
        self.graph_list = QtWidgets.QListWidget()
        self.graph_list.itemChanged.connect(self._visibility_changed)
        sidebar_layout.addWidget(self.graph_list, stretch=1)
        graph_row = QtWidgets.QHBoxLayout()
        self.add_button = QtWidgets.QPushButton("＋ グラフを追加")
        self.add_button.clicked.connect(self.add_graph)
        graph_row.addWidget(self.add_button)
        delete_button = QtWidgets.QPushButton("グラフを削除")
        delete_button.clicked.connect(self.delete_selected_graph)
        graph_row.addWidget(delete_button)
        sidebar_layout.addLayout(graph_row)
        splitter.addWidget(sidebar)

        self.workspace = QtWidgets.QWidget()
        self.graph_layout = QtWidgets.QGridLayout(self.workspace)
        self.graph_layout.setContentsMargins(5, 5, 5, 5)
        self.graph_layout.setSpacing(5)
        splitter.addWidget(self.workspace)
        splitter.setSizes([350, 1100])
        self.statusBar().showMessage("フォルダを開く → グラフを追加 → データをドラッグ＆ドロップ")
        file_menu = self.menuBar().addMenu("ファイル")
        file_menu.addAction("フォルダを開く", self.select_folder, "Ctrl+O")
        file_menu.addAction("グラフを追加", self.add_graph, "Ctrl+N")
        file_menu.addAction("保存したグラフを開く", self.open_saved_graph)
        file_menu.addAction("選択ファイルを更新", self.refresh_selected, "Ctrl+R")
        template_menu = self.menuBar().addMenu("テンプレート")
        template_menu.addAction("テンプレートを削除", self.delete_template)
        help_menu = self.menuBar().addMenu("ヘルプ")
        help_menu.addAction("操作方法", self.show_help)
        # サンプルからすぐ試せるようにする。初回は任意の測定フォルダに切り替え可能。
        sample = Path(__file__).resolve().parent.parent / "sample_data"
        if sample.is_dir():
            self.tree.select_folder(str(sample))
        self.add_graph()

    def select_folder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "測定フォルダを選択")
        if path:
            self.tree.select_folder(path)
            self.statusBar().showMessage(f"フォルダを選択: {path}", 5000)

    def _connect_graph(self, graph: GraphPanel):
        graph.fileDropped.connect(self.on_drop)
        graph.editCurve.connect(self.edit_curve)
        graph.saveRequested.connect(self.save_one_graph)
        graph.exportRequested.connect(self.export_graph)
        graph.templateRequested.connect(self.apply_template)
        graph.saveTemplateRequested.connect(self.save_template)
        graph.deleteRequested.connect(self.delete_graph)
        graph.changed.connect(self._refresh_graph_labels)

    def add_graph(self, title: str | None = None) -> GraphPanel:
        graph = GraphPanel(title or f"Graph {len(self.graphs)+1}")
        self._connect_graph(graph)
        self.graphs[graph.graph_id] = graph
        item = QtWidgets.QListWidgetItem(graph.title_text)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, graph.graph_id)
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        self.graph_list.blockSignals(True)
        item.setCheckState(QtCore.Qt.CheckState.Checked if self._visible_count() < self.MAX_VISIBLE
                           else QtCore.Qt.CheckState.Unchecked)
        self.graph_list.addItem(item)
        self.graph_list.setCurrentItem(item)
        self.graph_list.blockSignals(False)
        self._rebuild_grid()
        return graph

    def _visible_count(self):
        return sum(self.graph_list.item(i).checkState() == QtCore.Qt.CheckState.Checked
                   for i in range(self.graph_list.count()))

    def _visibility_changed(self, item):
        if item.checkState() == QtCore.Qt.CheckState.Checked and self._visible_count() > self.MAX_VISIBLE:
            self.graph_list.blockSignals(True)
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self.graph_list.blockSignals(False)
            self.statusBar().showMessage("同時表示は最大4グラフです。別のグラフのチェックを外してください", 6000)
        self._rebuild_grid()

    def _rebuild_grid(self):
        for graph in self.graphs.values():
            self.graph_layout.removeWidget(graph)
            graph.hide()
        ids = [self.graph_list.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
               for i in range(self.graph_list.count())
               if self.graph_list.item(i).checkState() == QtCore.Qt.CheckState.Checked]
        n = len(ids)
        for i, gid in enumerate(ids):
            graph = self.graphs[gid]
            if n == 1:
                self.graph_layout.addWidget(graph, 0, 0, 2, 2)
            elif n == 2:
                self.graph_layout.addWidget(graph, 0, i, 2, 1)
            else:
                self.graph_layout.addWidget(graph, i // 2, i % 2)
            graph.show()

    def _refresh_graph_labels(self, *_):
        for i in range(self.graph_list.count()):
            item = self.graph_list.item(i)
            gid = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if gid in self.graphs:
                graph = self.graphs[gid]
                item.setText(f"{graph.title_text} ({len(graph.curves)}本)")

    def delete_selected_graph(self):
        item = self.graph_list.currentItem()
        if item is not None:
            self.delete_graph(item.data(QtCore.Qt.ItemDataRole.UserRole))

    def delete_graph(self, graph_id: str):
        graph = self.graphs.pop(graph_id, None)
        if graph is None:
            return
        for i in range(self.graph_list.count()):
            if self.graph_list.item(i).data(QtCore.Qt.ItemDataRole.UserRole) == graph_id:
                self.graph_list.blockSignals(True)
                self.graph_list.takeItem(i)
                self.graph_list.blockSignals(False)
                break
        self.graph_layout.removeWidget(graph)
        graph.deleteLater()
        self._rebuild_grid()

    def on_drop(self, graph_id: str, path: str):
        path = self.data_manager.normalize(path)
        if graph_id not in self.graphs:
            return
        self._pending_drops.setdefault(path, []).append(graph_id)
        if path in self.data_manager.cache:
            self._pending_drops[path].remove(graph_id)
            if not self._pending_drops[path]:
                self._pending_drops.pop(path)
            self._add_curve_dialog(self.graphs[graph_id], self.data_manager.cache[path])
        else:
            self.data_manager.request(path)
            self.statusBar().showMessage(f"読み込み中: {Path(path).name}")

    def _on_data_loaded(self, path: str):
        record = self.data_manager.get(path)
        if record is None:
            return
        # キャッシュ更新のたびに、そのファイルを参照するすべての曲線を描き直す。
        for graph in self.graphs.values():
            for spec in graph.curves:
                if self.data_manager.normalize(spec.path) == path:
                    try:
                        graph.set_curve_data(spec, record)
                    except (ValueError, IndexError, TypeError) as exc:
                        self.statusBar().showMessage(f"{spec.name}: {exc}", 12000)
        for gid in self._pending_drops.pop(path, []):
            if gid in self.graphs:
                self._add_curve_dialog(self.graphs[gid], record)
        for gid, cid in self._pending_edits.pop(path, []):
            if gid in self.graphs:
                self._edit_curve_dialog(self.graphs[gid], cid, record)
        self.statusBar().showMessage(f"読み込み完了: {Path(path).name} / {len(record.array)}行", 5000)

    def _on_data_failed(self, path: str, error: str):
        self._pending_drops.pop(path, None)
        self._pending_edits.pop(path, None)
        message_error(self, "データ読み込み失敗", f"{path}\n\n{error}\n\n"
                      "クイックルックで区切り文字・ヘッダー行数を確認してください。\n"
                      "更新に失敗した場合、以前のキャッシュは保持されています。")
        self.statusBar().showMessage(f"読み込み失敗: {Path(path).name}", 8000)

    def _add_curve_dialog(self, graph: GraphPanel, record):
        idx = len(graph.curves)
        spec = CurveSpec(path=record.path, name=Path(record.path).stem,
                         color=COLORS[idx % len(COLORS)],
                         columns={"x": 0, "y": min(1, len(record.columns)-1),
                                  "z": min(2, len(record.columns)-1)})
        dlg = CurveDialog(spec, record, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            try:
                # 式のエラーは曲線を追加する前に検出する。
                from .formula import calculate_xy
                calculate_xy(record.array, dlg.spec.columns, dlg.spec.use_formula,
                             dlg.spec.x_expr, dlg.spec.y_expr)
                graph.add_curve(dlg.spec)
                graph.set_curve_data(dlg.spec, record)
                self._refresh_graph_labels()
            except (ValueError, IndexError, TypeError) as exc:
                message_error(self, "プロット設定エラー", str(exc))

    def edit_curve(self, graph_id: str, curve_id: str):
        graph = self.graphs.get(graph_id)
        if graph is None:
            return
        spec = graph.find_curve(curve_id)
        if spec is None:
            return
        path = self.data_manager.normalize(spec.path)
        record = self.data_manager.get(path)
        if record is None:
            self._pending_edits.setdefault(path, []).append((graph_id, curve_id))
            self.data_manager.request(path)
        else:
            self._edit_curve_dialog(graph, curve_id, record)

    def _edit_curve_dialog(self, graph: GraphPanel, curve_id: str, record):
        spec = graph.find_curve(curve_id)
        if spec is None:
            return
        dlg = CurveDialog(spec, record, self, editing=True)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            if dlg.delete_requested:
                graph.delete_curve(curve_id)
                return
            try:
                from .formula import calculate_xy
                calculate_xy(record.array, dlg.spec.columns, dlg.spec.use_formula,
                             dlg.spec.x_expr, dlg.spec.y_expr)
                pos = graph.curves.index(spec)
                graph.curves[pos] = dlg.spec
                graph.set_curve_data(dlg.spec, record)
                graph.changed.emit(graph.graph_id)
            except (ValueError, IndexError, TypeError) as exc:
                message_error(self, "数式エラー", str(exc))

    def quicklook_selected(self):
        path = self.tree.current_file()
        if path:
            self.quicklook(path)
        else:
            self.statusBar().showMessage("ファイルを選択してください", 4000)

    def quicklook(self, path: str):
        path = self.data_manager.normalize(path)
        options = self.data_manager.options.get(path, ReaderOptions())
        dlg = ReaderDialog(path, options, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.data_manager.set_options(path, dlg.options())
            self.statusBar().showMessage(f"形式を変更して再読み込み: {Path(path).name}", 5000)

    def refresh_selected(self):
        path = self.tree.current_file()
        if path is not None:
            self.data_manager.request(path, force=True)
            self.statusBar().showMessage(f"更新中: {Path(path).name}", 5000)
        else:
            self.statusBar().showMessage("更新するファイルをサイドバーで選択してください", 5000)

    def save_one_graph(self, graph_id: str):
        graph = self.graphs.get(graph_id)
        if graph is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "グラフを保存", "graph.plot.json",
                                                        "グラフJSON (*.json)")
        if path:
            try:
                save_graph(path, graph.to_dict(), self.data_manager.options)
                self.statusBar().showMessage(f"保存しました: {path}", 5000)
            except Exception as exc:
                message_error(self, "保存エラー", str(exc))

    def open_saved_graph(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "保存したグラフを開く", "",
                                                        "グラフJSON (*.json)")
        if not path:
            return
        try:
            data = load_graph(path)
            graph = self.add_graph(data.get("settings", {}).get("title", "Loaded graph"))
            for curve_data in data.get("curves", []):
                opts = curve_data.pop("reader_options", None)
                curve_data.pop("absolute_path", None)
                spec = CurveSpec.from_dict(curve_data)
                if opts is not None:
                    self.data_manager.options[self.data_manager.normalize(spec.path)] = ReaderOptions.from_dict(opts)
                graph.add_curve(spec)
            graph.apply_settings(data.get("settings", {}), record_history=False)
            for source in set(c.path for c in graph.curves):
                self.data_manager.request(source)
        except Exception as exc:
            message_error(self, "グラフ読み込みエラー", str(exc))

    def export_graph(self, graph_id: str):
        graph = self.graphs.get(graph_id)
        if graph is None:
            return
        path, selected = QtWidgets.QFileDialog.getSaveFileName(self, "グラフ画像を出力", "plot.png",
                                                               "PNG (*.png);;SVG (*.svg)")
        if not path:
            return
        ext = Path(path).suffix.lower()
        if ext not in (".png", ".svg"):
            path += ".svg" if "SVG" in selected else ".png"
        try:
            if path.lower().endswith(".svg"):
                exporter = pyqtgraph.exporters.SVGExporter(graph.plot_item)
            else:
                exporter = pyqtgraph.exporters.ImageExporter(graph.plot_item)
                width, ok = QtWidgets.QInputDialog.getInt(self, "PNGの横幅", "出力横幅（px）", 1600, 200, 10000)
                if not ok:
                    return
                exporter.parameters()["width"] = width
            exporter.export(path)
            self.statusBar().showMessage(f"画像を保存しました: {path}", 6000)
        except Exception as exc:
            message_error(self, "画像出力エラー", str(exc))

    def save_template(self, graph_id: str):
        graph = self.graphs.get(graph_id)
        if graph is None:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "テンプレートとして保存", "テンプレート名")
        if ok and name.strip():
            try:
                self.templates.put(name.strip(), graph.template_data())
            except Exception as exc:
                message_error(self, "保存エラー", str(exc))

    def apply_template(self, graph_id: str):
        graph = self.graphs.get(graph_id)
        if graph is None:
            return
        names = self.templates.names()
        if not names:
            self.statusBar().showMessage("テンプレートがありません。グラフメニューから保存してください", 7000)
            return
        name, ok = QtWidgets.QInputDialog.getItem(self, "テンプレートの適用", "テンプレート", names, 0, False)
        if ok:
            graph.apply_template(self.templates.templates[name])

    def delete_template(self):
        names = self.templates.names()
        if not names:
            return
        name, ok = QtWidgets.QInputDialog.getItem(self, "テンプレートを削除", "テンプレート", names, 0, False)
        if ok and QtWidgets.QMessageBox.question(self, "確認", f"{name} を削除しますか？") == \
                QtWidgets.QMessageBox.StandardButton.Yes:
            self.templates.delete(name)

    def show_help(self):
        QtWidgets.QMessageBox.information(self, "操作方法", """
1. 左の「フォルダを開く」で測定データの場所を選択します。
2. 「グラフを追加」で白紙グラフを作ります。
3. 左のファイルをグラフにドラッグして列や計算式を指定します。
4. 左ドラッグで矩形拡大。Panボタンで移動。中ボタンドラッグもPan。
5. ホイール回転で拡大縮小。Autoで全表示、Undo/Ctrl+Zで範囲を戻せます。
6. 曲線をダブルクリックして式や色を編集できます。
7. 2点測定を選んで、グラフを2回クリックするとΔx, Δy, 傾きを表示します。
8. 軸をクリックすると設定できます。
9. 左の「更新」は選択ファイルだけ再読み込みします。
10. 各グラフの「⋯」でJSON保存、画像出力、テンプレート操作ができます。
""")
