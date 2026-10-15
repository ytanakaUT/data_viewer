"""曲線の見た目をpyqtgraphの描画設定へ変換する。

UI・保存処理から描画ライブラリの細かい指定を隠蔽するためのモジュール。
"""
from __future__ import annotations

import pyqtgraph as pg

from .models import CurveSpec


# 保存ファイルには右側の識別子を使用する。左側はGUIでの表示名。
PLOT_STYLES = (
    ("lines & markers", "lines_markers"),
    ("lines", "lines"),
    ("markers", "markers"),
)


def plot_kwargs(spec: CurveSpec) -> dict:
    """PlotDataItem.setData()へ渡す表示属性を生成する。

    pen=Noneは線を描かない指定、symbol=Noneは点を描かない指定。
    線幅とマーカーサイズは、描画されないモードでも値を保持する。
    """
    if spec.plot_style not in {key for _, key in PLOT_STYLES}:
        raise ValueError(f"未対応のプロット形式です: {spec.plot_style}")
    draw_line = spec.plot_style in ("lines", "lines_markers")
    draw_marker = spec.plot_style in ("markers", "lines_markers")
    return {
        "pen": pg.mkPen(spec.color, width=spec.width) if draw_line else None,
        "symbol": "o" if draw_marker else None,
        "symbolSize": spec.marker_size,
        "symbolPen": pg.mkPen(spec.color, width=1),
        "symbolBrush": pg.mkBrush(spec.color),
    }
