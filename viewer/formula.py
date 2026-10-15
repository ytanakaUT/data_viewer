"""ユーザー入力の数式を、許可した演算子と関数に限定して安全に計算する。"""
from __future__ import annotations

import ast
import operator
import numpy as np

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {name: getattr(np, name) for name in (
    "sin", "cos", "tan", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh",
    "exp", "log", "log10", "sqrt", "abs", "floor", "ceil", "sign",
    "minimum", "maximum", "arctan2"
)}
_CONSTS = {"pi": np.pi, "e": np.e}


class FormulaError(ValueError):
    pass


def evaluate(expression: str, variables: dict[str, np.ndarray], length: int) -> np.ndarray:
    """式を計算し、必ず1次元(length,)の配列を返す。任意のPythonコードは実行しない。"""
    if not expression.strip() or len(expression) > 400:
        raise FormulaError("数式が空、または長すぎます")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"数式の構文エラー: {e.msg}") from e

    def visit(node, depth=0):
        if depth > 40:
            raise FormulaError("数式が複雑すぎます")
        if isinstance(node, ast.Expression):
            return visit(node.body, depth + 1)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in variables:
                return variables[node.id]
            if node.id in _CONSTS:
                return _CONSTS[node.id]
            raise FormulaError(f"未定義の変数: {node.id}")
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            return _BIN[type(node.op)](visit(node.left, depth + 1), visit(node.right, depth + 1))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](visit(node.operand, depth + 1))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            func = _FUNCS.get(node.func.id)
            if func is None or len(node.args) > 2:
                raise FormulaError("許可されていない関数です")
            return func(*(visit(arg, depth + 1) for arg in node.args))
        raise FormulaError("許可されていない式です（属性参照・添字・リストなどは不可）")

    try:
        with np.errstate(all="ignore"):
            value = np.asarray(visit(tree), dtype=np.float64)
        if value.ndim == 0:
            return np.full(length, float(value))
        if value.shape != (length,):
            raise FormulaError("計算結果の配列サイズが不正です")
        return value
    except (TypeError, ValueError, OverflowError, ZeroDivisionError) as e:
        if isinstance(e, FormulaError):
            raise
        raise FormulaError(f"計算に失敗しました: {e}") from e


def calculate_xy(array: np.ndarray, columns: dict[str, int], use_formula: bool,
                 x_expr: str, y_expr: str) -> tuple[np.ndarray, np.ndarray]:
    var = {k: array[:, i] for k, i in columns.items() if 0 <= i < array.shape[1]}
    if "x" not in var or "y" not in var:
        raise FormulaError("xとyにデータ列を割り当ててください")
    if use_formula:
        return evaluate(x_expr, var, len(array)), evaluate(y_expr, var, len(array))
    return var["x"], var["y"]
