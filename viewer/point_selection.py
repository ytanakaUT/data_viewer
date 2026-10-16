"""測定点の選択・非表示を扱う純粋なNumPy処理（Qt非依存）。

各曲線の点には「元データでの行番号」を識別子として使う。
選択は一時的、非表示のインデックスのみ CurveSpec に保存する。
数値そのものを書き換えないので、いつでも全点を再表示できる。
"""
from __future__ import annotations

import numpy as np


def visible_mask(length: int, hidden_indices) -> np.ndarray:
    """元データの行番号から可視点を決める。範囲外の番号は安全に無視。"""
    mask = np.ones(length, dtype=bool)
    if hidden_indices:
        indices = np.asarray(hidden_indices, dtype=np.int64)
        indices = indices[(indices >= 0) & (indices < length)]
        mask[indices] = False
    return mask


def masked_y(y: np.ndarray, hidden_indices) -> np.ndarray:
    """欠損点は NaN にし、非表示領域を跨ぐ線分を描画しない。"""
    if not hidden_indices:
        return y
    result = np.asarray(y, dtype=float).copy()
    result[~visible_mask(len(result), hidden_indices)] = np.nan
    return result


def rectangle_indices(x: np.ndarray, y: np.ndarray, bounds,
                      *, available: np.ndarray | None = None) -> np.ndarray:
    """表示座標上の矩形内にある有限値の行番号。境界も含む。"""
    xmin, xmax, ymin, ymax = bounds
    keep = (np.isfinite(x) & np.isfinite(y) &
            (x >= min(xmin, xmax)) & (x <= max(xmin, xmax)) &
            (y >= min(ymin, ymax)) & (y <= max(ymin, ymax)))
    if available is not None:
        keep &= available
    return np.flatnonzero(keep)


def hide_indices(previous: list[int], selected, length: int) -> list[int]:
    """行番号を集合として統合し、重複や範囲外を取り除く。"""
    values = set(i for i in previous if 0 <= i < length)
    values.update(int(i) for i in selected if 0 <= int(i) < length)
    return sorted(values)


def visible_bounds(series: list[tuple[np.ndarray, np.ndarray]],
                   x_log: bool = False, y_log: bool = False):
    """選択済みマスクを適用した描画データの有限点のみからオートスケール用範囲を返す。"""
    bounds = None
    for x, y in series:
        x, y = np.asarray(x), np.asarray(y)
        finite = np.isfinite(x) & np.isfinite(y)
        if x_log:
            finite &= x > 0
        if y_log:
            finite &= y > 0
        if not np.any(finite):
            continue
        xx, yy = x[finite], y[finite]
        if x_log:
            xx = np.log10(xx)
        if y_log:
            yy = np.log10(yy)
        limits = (float(np.min(xx)), float(np.max(xx)),
                  float(np.min(yy)), float(np.max(yy)))
        if bounds is None:
            bounds = limits
        else:
            bounds = (min(bounds[0], limits[0]), max(bounds[1], limits[1]),
                      min(bounds[2], limits[2]), max(bounds[3], limits[3]))
    return bounds
