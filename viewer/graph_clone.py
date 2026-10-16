"""グラフの複製用データを生成する（Qtには依存しない）。

各曲線のファイル参照、計算式、色、表示形式などはそのまま複製する。
グラフと曲線には新しいIDを割り当て、複製元と独立して編集できるようにする。
測定データ本体は含めず、既存のDataManagerのキャッシュを再利用する。
"""
from __future__ import annotations

from copy import deepcopy
import re
from collections.abc import Iterable

from .models import new_id


def unique_copy_title(title: str, existing_titles: Iterable[str]) -> str:
    """'Graph 1 (コピー)'、'Graph 1 (コピー 2)' のように名前を重複させない。"""
    occupied = set(existing_titles)
    base = re.sub(r" \(コピー(?: \d+)?\)$", "", title)
    first = f"{base} (コピー)"
    if first not in occupied:
        return first
    index = 2
    while f"{base} (コピー {index})" in occupied:
        index += 1
    return f"{base} (コピー {index})"


def clone_graph_definition(source: dict, existing_titles: Iterable[str]) -> dict:
    """グラフの設定と曲線仕様を複製。元の辞書・IDは一切変更しない。"""
    cloned = deepcopy(source)
    settings = cloned.setdefault("settings", {})
    title = settings.get("title", "Graph")
    settings["title"] = unique_copy_title(title, existing_titles)
    cloned["id"] = new_id()
    for curve in cloned.get("curves", []):
        curve["id"] = new_id()
    return cloned
