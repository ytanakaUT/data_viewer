"""現在存在する曲線から「使用中の色」を集める（GUIには依存しない）。"""
from __future__ import annotations

from collections.abc import Iterable
import colorsys

from .models import COLORS


def active_curve_colors(graphs: Iterable[object]) -> list[str]:
    """全グラフの曲線で現在使われている色を、重複なしで返す。

    グラフや曲線の表示・非表示は問わない。削除済みの曲線や変更前の色は
    曲線一覧に存在しないため、自動的に候補から外れる。
    新しく追加された曲線の色を先頭にする（最後に追加されたものを優先）。
    """
    colors = []
    seen = set()
    for graph in reversed(list(graphs)):
        for curve in reversed(graph.curves):
            color = str(curve.color).strip()
            key = color.casefold()
            if color and key not in seen:
                colors.append(color)
                seen.add(key)
    return colors


def unused_graph_color(graph_colors: Iterable[str]) -> str:
    """そのグラフのどの曲線とも重複しない色を返す。

    既存曲線の色は表示・非表示を問わず使用中とみなす。編集中の曲線自身も
    使用中に含めるため、プロパティ画面の「自動設定」で別の色に変更できる。
    はじめは通常の自動色パレットを順番に使い、全部使用済みの場合は
    HSV色空間から追加の色を生成する。全グラフの色とは比較しない。
    """
    used = {str(color).strip().casefold() for color in graph_colors if str(color).strip()}
    for color in COLORS:
        if color.casefold() not in used:
            return color

    # パレットの全色が使われていても、同じ色を返さないようにする。
    for index in range(65536):
        hue = (0.13 + index * 0.618033988749895) % 1.0
        red, green, blue = colorsys.hsv_to_rgb(hue, 0.72, 0.82)
        color = "#{:02x}{:02x}{:02x}".format(
            round(red * 255), round(green * 255), round(blue * 255)
        )
        if color.casefold() not in used:
            return color
    raise ValueError("未使用の色を選べませんでした")
