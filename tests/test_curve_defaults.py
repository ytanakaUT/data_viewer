"""データ追加時の設定継承（Qt不要で実行可能）。"""
from pathlib import Path

import numpy as np

from viewer.curve_defaults import initial_curve_spec, matching_reader_options
from viewer.models import CurveSpec, DataRecord, ReaderOptions, COLORS


def record(path, cols, opts=None):
    return DataRecord(path=str(path), columns=cols,
                      array=np.zeros((3, len(cols))), options=opts or ReaderOptions())


def test_inherit_curve_settings_except_color_identity_or_name(tmp_path):
    original = record(tmp_path / "001.dat", ["Field", "Voltage", "Current"])
    next_record = record(tmp_path / "002.dat", ["Field", "Voltage", "Current"])
    original_spec = CurveSpec(
        path=original.path, name="manual-name", columns={"x": 0, "y": 2, "z": 1},
        use_formula=True, x_expr="x + z", y_expr="y / z * 1e6",
        color="#abcdef", plot_style="lines_markers", width=4.5,
        marker_size=13, visible=False,
    )
    new_spec = initial_curve_spec(next_record, graph_colors=[original_spec.color],
                                  previous_spec=original_spec, previous_record=original)
    assert new_spec.path == next_record.path
    assert new_spec.name == "002"
    assert new_spec.id != original_spec.id
    assert new_spec.color == COLORS[0]  # 既存色がパレット外なら最初の未使用色
    assert new_spec.color != original_spec.color
    for key in ("columns", "use_formula", "x_expr", "y_expr", "plot_style",
                "width", "marker_size", "visible"):
        assert getattr(new_spec, key) == getattr(original_spec, key)
    new_spec.columns["x"] = 99
    assert original_spec.columns["x"] == 0


def test_different_headers_fall_back_to_original_defaults(tmp_path):
    original = record(tmp_path / "before.dat", ["Field", "Rxx", "Rxy"])
    next_record = record(tmp_path / "after.dat", ["Temp", "Torque"])
    old_spec = CurveSpec(path=original.path, color="#123456", plot_style="markers", use_formula=True)
    spec = initial_curve_spec(next_record, graph_colors=[COLORS[0]],
                              previous_spec=old_spec, previous_record=original)
    assert spec.color == COLORS[1]
    assert spec.plot_style == "lines"
    assert not spec.use_formula
    assert spec.columns == {"x": 0, "y": 1, "z": 1}


def test_no_previous_curve_uses_defaults(tmp_path):
    data = record(tmp_path / "new.dat", ["B", "R", "T"])
    spec = initial_curve_spec(data, graph_colors=[])
    assert spec.columns == {"x": 0, "y": 1, "z": 2}
    assert spec.color == COLORS[0]


def test_same_column_count_but_different_names_does_not_inherit(tmp_path):
    a = record(tmp_path / "a.dat", ["Field", "Rxx"])
    b = record(tmp_path / "b.dat", ["Temperature", "Rxx"])
    new = initial_curve_spec(b, graph_colors=[COLORS[0], COLORS[1]],
                             previous_spec=CurveSpec(path=a.path, y_expr="y/2",use_formula=True),
                             previous_record=a)
    assert not new.use_formula


def test_matching_nondefault_reader_options_are_inherited(tmp_path):
    opts = ReaderOptions(delimiter="comma", header_lines=3, name_line=3)
    old_path = tmp_path / "run001.dat"
    next_path = tmp_path / "run002.dat"
    old_path.write_text("MPMS3 export\n[Data]\nField,Voltage,Current\n1,,4\n2,3,5\n",encoding="utf-8")
    next_path.write_text("MPMS3 export\n[Data]\nField,Voltage,Current\n2,,6\n3,7,8\n",encoding="utf-8")
    prev = record(old_path, ["Field", "Voltage", "Current"], opts)
    inherited = matching_reader_options(str(next_path), prev)
    assert inherited == opts
    assert inherited is not opts


def test_reader_options_only_when_headers_match(tmp_path):
    opts = ReaderOptions(delimiter="comma", header_lines=2, name_line=2)
    old_path = tmp_path / "run001.dat"
    next_path = tmp_path / "run002.dat"
    old_path.write_text("METADATA\nField,Voltage\n1,2\n",encoding="utf-8")
    next_path.write_text("METADATA\nField,Current\n1,2\n",encoding="utf-8")
    prev = record(old_path, ["Field", "Voltage"], opts)
    assert matching_reader_options(str(next_path), prev) is None


def test_reader_options_different_extension_not_inherited(tmp_path):
    opts = ReaderOptions(delimiter="comma", header_lines=2, name_line=2)
    prev = record(tmp_path / "run001.dat", ["Field", "Voltage"], opts)
    next_path = tmp_path / "run002.csv"
    next_path.write_text("DATA\nField,Voltage\n1,2\n",encoding="utf8")
    assert matching_reader_options(str(next_path), prev) is None


def test_reader_options_dont_inherit_defaults(tmp_path):
    prev = record(tmp_path / "run001.dat", ["Field", "Voltage"])
    assert matching_reader_options(str(tmp_path / "run002.dat"), prev) is None


def test_non_numeric_candidate_not_assumed_same_format(tmp_path):
    opts = ReaderOptions(delimiter="comma", header_lines=2, name_line=2)
    prev = record(tmp_path / "run001.dat", ["Field", "Voltage"], opts)
    candidate = tmp_path / "run002.dat"
    candidate.write_text("TEXT\nField,Voltage\ninvalid,notanumber\n",encoding="utf8")
    assert matching_reader_options(str(candidate), prev) is None


def test_auto_color_uses_actual_colors_after_manual_edit(tmp_path):
    previous = record(tmp_path / "run1.dat", ["Field", "R"])
    current = record(tmp_path / "run2.dat", ["Field", "R"])
    original = CurveSpec(path=previous.path, color=COLORS[4],
                         width=3.0, plot_style="markers")
    result = initial_curve_spec(current, graph_colors=[COLORS[4]],
                                previous_spec=original, previous_record=previous)
    assert result.color == COLORS[0]  # 編集済みの色を避けつつ最初の未使用色を選ぶ
    assert result.width == 3.0
    assert result.plot_style == "markers"
    assert original.color == COLORS[4]


def test_many_curves_never_reuse_used_colors(tmp_path):
    data = record(tmp_path / "next.dat", ["Field", "R"])
    colors = []
    for _ in range(len(COLORS) + 5):
        spec = initial_curve_spec(data, graph_colors=colors)
        assert spec.color.casefold() not in {c.casefold() for c in colors}
        colors.append(spec.color)
    assert colors[:len(COLORS)] == COLORS


def test_manual_color_change_or_deletion_frees_palette_color(tmp_path):
    data = record(tmp_path / "next.dat", ["Field", "R"])
    # 赤系と青系を使っているときは3色目。
    assert initial_curve_spec(data, graph_colors=COLORS[:2]).color == COLORS[2]
    # 1色目を手動で別色に変えたら、1色目が再利用される。
    assert initial_curve_spec(data, graph_colors=["#123456", COLORS[1]]).color == COLORS[0]
    # 1色目を削除したときも同じ。
    assert initial_curve_spec(data, graph_colors=[COLORS[1]]).color == COLORS[0]


def test_uses_only_current_graph_colors(tmp_path):
    data = record(tmp_path / "next.dat", ["Field", "R"])
    # 別グラフで何色使われていても、新規曲線の初期色には影響しない。
    assert initial_curve_spec(data, graph_colors=[]).color == COLORS[0]


def test_visible_and_hidden_curves_are_both_counted(tmp_path):
    data = record(tmp_path / "next.dat", ["Field", "R"])
    # 呼び出し側はvisibleに関係なくすべてのcurve.colorを渡す。
    hidden = CurveSpec(path="old.dat", color=COLORS[0], visible=False)
    assert initial_curve_spec(data, graph_colors=[hidden.color]).color == COLORS[1]
