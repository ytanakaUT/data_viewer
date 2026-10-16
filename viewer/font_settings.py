"""グラフ全体で共有する文字サイズ設定。Qtには依存しない。

目盛り・軸ラベルはX/Yで同じ大きさとし、タイトルだけ別に指定できる。
古いグラフJSONやテンプレートにキーがない場合は既定値を使う。
"""
from __future__ import annotations

import math
from collections.abc import Mapping

FONT_SIZE_DEFAULTS = {
    "title_font_size": 12,  # グラフタイトル（pt）
    "label_font_size": 11,  # X/Y軸ラベル共通（pt）
    "tick_font_size": 10,   # X/Y軸目盛り共通（pt）
}
MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 48


def get_font_sizes(settings: Mapping, fallback: Mapping | None = None) -> dict[str, int]:
    """保存済み辞書から文字サイズを取り出し、整数ptへ正規化する。

    fallbackがあれば欠けている項目を現在のグラフ設定から補う。
    不正な値には例外を送出し、適用中の設定が壊れるのを防ぐ。
    """
    result = {}
    for key, default in FONT_SIZE_DEFAULTS.items():
        value = settings.get(key, (fallback or {}).get(key, default))
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} は {MIN_FONT_SIZE}〜{MAX_FONT_SIZE} の整数で指定してください") from exc
        if not math.isfinite(number) or not number.is_integer() or not MIN_FONT_SIZE <= number <= MAX_FONT_SIZE:
            raise ValueError(f"{key} は {MIN_FONT_SIZE}〜{MAX_FONT_SIZE} の整数で指定してください")
        result[key] = int(number)
    return result
