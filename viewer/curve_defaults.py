"""同じグラフに連続追加する曲線の初期値を決める（GUI非依存）。

新しいファイルの列構造が直前の曲線と一致した場合に限り、列の割当・式・見た目
（色を除く）を引き継ぐ。色は現在のグラフで未使用のものを自動選択する。
ファイルパス、曲線名、識別子は必ず新しいものを使う。

また、特別な読み込み設定を要する測定装置の連続したファイルについて、
前のファイルと同じヘッダー構造をもつことを軽く確認して読み込み設定を流用する。
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from collections.abc import Iterable

from .models import CurveSpec, DataRecord, ReaderOptions, new_id
from .color_palette import unused_graph_color
from .reader import preview_lines, preview_table


def same_columns(first: DataRecord, second: DataRecord) -> bool:
    """列名と列数が一致するときだけ、同じ列の並びとして扱う。"""
    return bool(first.columns) and first.columns == second.columns


def initial_curve_spec(
    record: DataRecord,
    *,
    graph_colors: Iterable[str],
    previous_spec: CurveSpec | None = None,
    previous_record: DataRecord | None = None,
) -> CurveSpec:
    """新規追加ダイアログの初期設定を生成する。

    別ファイルのIDや名前を複製せず、前の曲線の辞書も変更しない。
    """
    # 直前の曲線の色や追加順は使わず、現在同じグラフ内で未使用の色を選ぶ。
    # 色選択画面の「自動設定」と共通の関数を使用する。
    new_color = unused_graph_color(graph_colors)
    if previous_spec is not None and previous_record is not None and same_columns(previous_record, record):
        return replace(
            previous_spec,
            id=new_id(),
            path=record.path,
            name=Path(record.path).stem,
            color=new_color,
            columns=previous_spec.columns.copy(),
            hidden_indices=[],  # 部分消去の行番号は別ファイルに引き継がない
        )

    # 異なるヘッダーなら、従来どおりの列選択を使用する。色の自動選択は共通。
    return CurveSpec(
        path=record.path,
        name=Path(record.path).stem,
        color=new_color,
        columns={
            "x": 0,
            "y": min(1, len(record.columns) - 1),
            "z": min(2, len(record.columns) - 1),
        },
    )


def matching_reader_options(
    path: str,
    previous_record: DataRecord | None,
) -> ReaderOptions | None:
    """既存データと同じ形式だと確認できた場合のみ読み込み設定を提案する。

    - 拡張子が異なる場合は引き継がない。
    - デフォルトの読み込み設定なら、そのまま既定の読込処理に任せる。
    - 先頭数行の列名・列数と数値データを比較する。全ファイルは読まない。
    - 判定不能なら既定設定に戻す（例外をGUIに伝播させない）。
    """
    if previous_record is None:
        return None
    if Path(path).suffix.lower() != Path(previous_record.path).suffix.lower():
        return None
    options = previous_record.options
    if options == ReaderOptions():
        return None
    try:
        lines = preview_lines(path, max(50, options.header_lines + 5), options.encoding)
        names, rows = preview_table(lines, options, limit=3)
        expected_count = len(previous_record.columns)
        if not rows or names != previous_record.columns:
            return None
        if not all(len(row) == expected_count for row in rows):
            return None
        # 読み込み設定が偶然同じ列数を出しただけ、という誤判定を防ぐ。
        for row in rows:
            for value in row:
                if value:
                    float(value)
        return replace(options)  # 個々のファイルの設定を独立して保持する。
    except (OSError, UnicodeError, ValueError, TypeError):
        return None
