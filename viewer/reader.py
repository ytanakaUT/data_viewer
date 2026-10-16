"""テキストファイルの先頭確認、列名の決定、数値データの読み込み。GUIに依存しない。"""
from __future__ import annotations

import re
from pathlib import Path
import numpy as np

from .models import ReaderOptions, DataRecord


QUICKLOOK_RAW_LINES = 50  # クイックルックで表示するファイル先頭の行数
QUICKLOOK_TABLE_ROWS = 12  # 数値プレビューの行数


def preview_lines(path: str, count: int = QUICKLOOK_RAW_LINES, encoding: str = "utf-8-sig") -> list[str]:
    with open(path, "r", encoding=encoding) as f:
        return [line.rstrip("\r\n") for _, line in zip(range(count), f)]


def split_line(line: str, delimiter: str) -> list[str]:
    line = line.strip()
    if not line:
        return []
    if delimiter == "whitespace":
        return re.split(r"\s+", line)
    if delimiter == "tab":
        return [s.strip() for s in line.split("\t")]
    if delimiter == "comma":
        return [s.strip() for s in line.split(",")]
    if delimiter == "space":
        return [s for s in re.split(r" +", line) if s]
    raise ValueError(f"不明な区切り文字: {delimiter}")


def column_names(lines: list[str], options: ReaderOptions, ncols: int) -> list[str]:
    if options.header_lines == 0:
        return [f"列{i+1}" for i in range(ncols)]
    index = options.name_line - 1 if options.name_line else options.header_lines - 1
    if index < 0 or index >= len(lines) or index >= options.header_lines:
        return [f"列{i+1}" for i in range(ncols)]
    names = split_line(lines[index].lstrip("# "), options.delimiter)
    if len(names) != ncols:
        return [f"列{i+1}" for i in range(ncols)]
    return [name or f"列{i+1}" for i, name in enumerate(names)]


def preview_table(lines: list[str], options: ReaderOptions, limit: int = QUICKLOOK_TABLE_ROWS) -> tuple[list[str], list[list[str]]]:
    rows = []
    for line in lines[options.header_lines:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        rows.append(split_line(line, options.delimiter))
        if len(rows) >= limit:
            break
    ncols = max((len(r) for r in rows), default=0)
    return column_names(lines, options, ncols), rows


def _number_or_nan(value: str | bytes) -> float:
    """空の数値フィールドをNaNにする。列の詰め直しは行わない。"""
    return float(value) if value.strip() else float("nan")


def load_data(path: str, options: ReaderOptions) -> DataRecord:
    """NumPyで数値を読み込む。失敗時には例外を投げ、既存キャッシュは変更しない。"""
    if options.header_lines < 0:
        raise ValueError("ヘッダー行数は0以上にしてください")
    path = str(Path(path).resolve())
    first = preview_lines(path, max(50, options.header_lines + 2), options.encoding)
    delimiter = {"whitespace": None, "tab": "\t", "comma": ",", "space": None}.get(options.delimiter)
    if options.delimiter not in ("whitespace", "tab", "comma", "space"):
        raise ValueError("区切り文字の設定が不正です")
    # カンマ・タブ区切りで空フィールドがある場合、列の位置を保持してNaNとする。
    # np.loadtxtの通常変換では空文字列をfloatへ変換できず、エラーになる。
    # convertersは必要な区切り形式だけに適用し、空欄のない通常の空白区切りは高速な既定処理を使う。
    converter = _number_or_nan if options.delimiter in ("comma", "tab") else None
    arr = np.loadtxt(path, delimiter=delimiter, skiprows=options.header_lines,
                     encoding=options.encoding, comments="#", ndmin=2,
                     dtype=np.float64, converters=converter)
    if arr.size == 0:
        raise ValueError("数値データが見つかりません")
    names = column_names(first, options, arr.shape[1])
    return DataRecord(path=path, array=arr, columns=names, options=options)
