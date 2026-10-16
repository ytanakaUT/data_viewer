"""グラフ上のドラッグ操作。左ドラッグは選択モード、中央ドラッグは常にPan。"""
from __future__ import annotations

import pyqtgraph as pg
from PySide6 import QtCore


class MiddlePanViewBox(pg.ViewBox):
    selectionFinished = QtCore.Signal(float, float, float, float)
    """マウス中央ボタンで、表示モードにかかわらずPanするViewBox。

    pyqtgraph標準のRectModeでは中央ドラッグまで範囲拡大になるため、
    中央ボタンだけ処理を上書きする。左ドラッグとホイール操作は標準実装を使う。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.point_selection_mode = False

    def mouseDragEvent(self, ev, axis=None):
        # 部分消去モードでは左ドラッグはズームではなく点の矩形選択。
        # 中央ドラッグのPanは全モード共通で維持。
        if (self.point_selection_mode and axis is None and
                ev.button() == QtCore.Qt.MouseButton.LeftButton):
            ev.accept()
            if ev.isFinish():
                self.rbScaleBox.hide()
                a = self.mapToView(ev.buttonDownPos())
                b = self.mapToView(ev.pos())
                self.selectionFinished.emit(min(a.x(), b.x()), max(a.x(), b.x()),
                                            min(a.y(), b.y()), max(a.y(), b.y()))
            else:
                self.updateScaleBox(ev.buttonDownPos(), ev.pos())
            return

        if ev.button() != QtCore.Qt.MouseButton.MiddleButton:
            # 範囲モードでは左ドラッグで矩形拡大、Panモードでは左ドラッグで移動。
            super().mouseDragEvent(ev, axis=axis)
            return

        ev.accept()
        if ev.isFinish():
            return

        # 元のViewBoxと同様に、操作が許可された軸だけを動かす。
        enabled = self.mouseEnabled()
        if axis in (0, 1):
            enabled[1 - axis] = False
        if not any(enabled):
            return

        # ViewBox座標でのマウス移動量を、グラフ座標に変換する。
        # マウスが右に動けばデータ全体も右に動く（表示範囲は左に移動する）。
        previous = self.mapToView(ev.lastPos())
        current = self.mapToView(ev.pos())
        dx = previous.x() - current.x() if enabled[0] else None
        dy = previous.y() - current.y() if enabled[1] else None

        # pyqtgraph本来のPan操作と同じ処理・通知を使用する。
        self._resetTarget()
        self.translateBy(x=dx, y=dy)
        self.sigRangeChangedManually.emit(enabled)
