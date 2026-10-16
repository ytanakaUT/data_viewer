"""高速描画に渡すデータの整列方向を判定する（元データは変更しない）。

pyqtgraph の clipToView は X が昇順であることを前提に二分探索する。
磁場の下降掃引をそのまま渡すと、ズーム時に曲線が消える場合がある。

* 昇順: そのまま描画し、高速化機能を使用。
* 降順: 描画するときだけ逆順のビューを使い、高速化機能を使用。
* 往復掃引・NaN 等: 点の接続順を保持し、高速化機能を使用しない。

オリジナルの配列は GraphPanel.values に保持し、座標照会と計算に使用する。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PlotPlan:
    x: np.ndarray
    y: np.ndarray
    clip_to_view: bool
    auto_downsample: bool
    direction: str  # ascending / descending / nonmonotonic / nonfinite


def prepare_plot_data(x: np.ndarray, y: np.ndarray, *, x_log: bool = False) -> PlotPlan:
    """描画に渡す配列と、使用してよい高速化設定を返す。

    返す配列は原則としてオリジナルか逆順ビューで、測定データをコピー・並べ替えしない。
    非単調なXを単純にソートするとヒステリシスループを壊すのでソートは行わない。
    """
    x = np.asarray(x)
    y = np.asarray(y)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("描画データは長さの一致した1次元配列が必要です")

    if not np.all(np.isfinite(x)):
        return PlotPlan(x, y, False, False, "nonfinite")

    # 対数変換後のXが無効になる点は、二分探索による切り出しを使わない。
    if x_log and np.any(x <= 0):
        return PlotPlan(x, y, False, False, "nonfinite")

    if len(x) < 2 or np.all(x[1:] >= x[:-1]):
        return PlotPlan(x, y, True, True, "ascending")

    if np.all(x[1:] <= x[:-1]):
        # スライスはビューなので元配列を変更・複製しない。線分の軌跡も不変。
        return PlotPlan(x[::-1], y[::-1], True, True, "descending")

    # 途中で反転する掃引は、時間順の曲線のつながりを維持する。
    return PlotPlan(x, y, False, False, "nonmonotonic")
