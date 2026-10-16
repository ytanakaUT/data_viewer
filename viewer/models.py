"""UIと計算処理の間で共有する、データ構造の定義。"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from uuid import uuid4


def new_id() -> str:
    return uuid4().hex


@dataclass
class ReaderOptions:
    delimiter: str = "whitespace"  # whitespace / tab / comma / space
    header_lines: int = 1
    name_line: int = 0  # 1から始まる行番号、0は最後のヘッダー行
    encoding: str = "utf-8-sig"

    @classmethod
    def from_dict(cls, data: dict) -> ReaderOptions:
        return cls(**{key: data[key] for key in cls.__dataclass_fields__ if key in data})


@dataclass
class CurveSpec:
    path: str
    name: str = ""
    columns: dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 1, "z": 2})
    use_formula: bool = False
    x_expr: str = "x"
    y_expr: str = "y"
    color: str = "#1976d2"
    width: float = 1.5
    plot_style: str = "lines"  # lines / lines_markers / markers
    marker_size: float = 7.0  # マーカーの直径（px）。線幅とは独立
    visible: bool = True
    hidden_indices: list[int] = field(default_factory=list)  # 部分消去した元データの行番号
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CurveSpec:
        keys = cls.__dataclass_fields__
        return cls(**{k: v for k, v in data.items() if k in keys})


@dataclass
class DataRecord:
    path: str
    columns: list[str]
    array: "object"  # NumPy ndarray。GUI非依存に保つ
    options: ReaderOptions


COLORS = ["#1976d2", "#e66c28", "#268a6c", "#9b59b6", "#c04455", "#777777", "#20a9c5"]
