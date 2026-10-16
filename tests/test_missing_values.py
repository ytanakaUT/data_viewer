"""MPMS3形式に見られる空欄フィールドを保持するテスト。"""
import numpy as np
import pytest

from viewer.models import ReaderOptions
from viewer.reader import load_data, preview_lines, preview_table
from viewer.formula import calculate_xy


def test_comma_empty_cells_preserve_columns(tmp_path):
    path = tmp_path / "mpms.csv"
    path.write_text(
        "Comment 1\nComment 2\nComment 3\n"
        "a,b,c,d,e,f,g,h,i\n"
        ",,,3.0,4.0,,5.0,,\n"
        "1,2,3,4,5,6,7,8,9\n",
        encoding="utf-8",
    )
    opts = ReaderOptions(delimiter="comma", header_lines=4)
    record = load_data(str(path), opts)
    assert record.array.shape == (2, 9)
    assert record.columns == list("abcdefghi")
    assert np.isnan(record.array[0, [0, 1, 2, 5, 7, 8]]).all()
    np.testing.assert_array_equal(record.array[0, [3, 4, 6]], [3., 4., 5.])
    np.testing.assert_array_equal(record.array[1], np.arange(1., 10.))
    names, rows = preview_table(preview_lines(str(path)), opts)
    assert names == list("abcdefghi")
    assert rows[0] == ["", "", "", "3.0", "4.0", "", "5.0", "", ""]
    # 存在する列を選択すれば、欠損を含む他の列の有無に関係なくプロットできる。
    x, y = calculate_xy(record.array, {"x": 3, "y": 6}, False, "x", "y")
    np.testing.assert_array_equal(x, [3., 4.])
    np.testing.assert_array_equal(y, [5., 7.])


def test_tabs_blank_columns(tmp_path):
    path = tmp_path / "tabs.dat"
    path.write_text("x\ty\tz\n1\t\t3\n2\t4\t5\n", encoding="utf-8")
    rec = load_data(str(path), ReaderOptions(delimiter="tab", header_lines=1))
    assert rec.array.shape == (2, 3)
    assert np.isnan(rec.array[0, 1])
    assert rec.array[0, 2] == 3


def test_csv_inconsistent_column_count_raises(tmp_path):
    path = tmp_path / "inconsistent.csv"
    path.write_text("a,b,c\n1,,3\n4,5\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_data(str(path), ReaderOptions(delimiter="comma", header_lines=1))


def test_whitespace_default_stays_unchanged(tmp_path):
    path = tmp_path / "normal.dat"
    path.write_text("X Y\n1 2\n2 3\n", encoding="utf-8")
    rec = load_data(str(path), ReaderOptions())
    np.testing.assert_array_equal(rec.array, [[1., 2.], [2., 3.]])
