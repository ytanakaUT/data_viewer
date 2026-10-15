"""GUIがなくても動作確認できる、数値計算とデータ読み込みのテスト。"""
from pathlib import Path
import numpy as np
import pytest

from viewer.formula import calculate_xy, evaluate, FormulaError
from viewer.models import ReaderOptions
from viewer.reader import load_data, preview_lines, preview_table

SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"


def test_default_space_header():
    path = SAMPLES / "demo.dat"
    record = load_data(str(path), ReaderOptions())
    assert record.array.shape == (11, 4)
    assert record.columns == ["Field(T)", "Rxx(ohm)", "Rxy(ohm)", "Current(A)"]
    assert record.array[0, 0] == -5


def test_comma_multiple_header_lines():
    path = SAMPLES / "demo_comma.csv"
    opts = ReaderOptions(delimiter="comma", header_lines=3)
    record = load_data(str(path), opts)
    assert record.array.shape == (5, 3)
    assert record.columns == ["Field", "Temperature", "Voltage"]
    headers, rows = preview_table(preview_lines(str(path)), opts)
    assert headers == record.columns
    assert rows[0] == ["0", "0.5", "0.001"]


def test_formula_array_and_constants():
    arr = np.array([[1, 2, 4], [2, 3, 6]], dtype=float)
    x, y = calculate_xy(arr, {"x": 0, "y": 1, "z": 2}, True,
                        "x+y", "z*y+x")
    np.testing.assert_allclose(x, [3, 5])
    np.testing.assert_allclose(y, [9, 20])
    np.testing.assert_allclose(evaluate("sin(pi/2)+3", {}, 2), [4, 4])


def test_formula_rejects_arbitrary_python():
    for expr in ["__import__('os').system('ls')", "x.__class__", "x[0]", "[1,2]", "open('x')"]:
        with pytest.raises(FormulaError):
            evaluate(expr, {"x": np.arange(3)}, 3)


def test_nonfinite_values_supported():
    arr = np.array([[1., 1.], [2., 0.]])
    _, y = calculate_xy(arr, {"x": 0, "y": 1}, True, "x", "1/y")
    assert np.isinf(y[1])
