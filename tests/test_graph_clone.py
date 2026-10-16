"""グラフ複製時の設定・識別子・元データ参照の独立性。"""
from viewer.graph_clone import clone_graph_definition, unique_copy_title


def _source():
    return {
        "id": "graph-before",
        "settings": {
            "title": "Torque",
            "xlabel": "Field (T)", "ylabel": "Torque (a.u.)",
            "x_min": -14.0, "x_max": 14.0, "y_min": 0.01, "y_max": 100.,
            "x_log": False, "y_log": True, "grid": False,
        },
        "curves": [{
            "id": "curve-before", "path": "C:/data/torque.dat",
            "name": "sample1", "columns": {"x": 0, "y": 2, "z": 1},
            "use_formula": True, "x_expr": "x", "y_expr": "y / z",
            "color": "#aa00bb", "width": 2.5, "marker_size": 12.0,
            "plot_style": "lines_markers", "visible": False,
        }],
    }


def test_copy_creates_new_ids_preserves_other_settings():
    source = _source()
    result = clone_graph_definition(source, ["Torque"])
    assert result["id"] != source["id"]
    assert result["settings"]["title"] == "Torque (コピー)"
    assert {k: v for k, v in result["settings"].items() if k != "title"} == {
        k: v for k, v in source["settings"].items() if k != "title"
    }
    assert result["curves"][0]["id"] != source["curves"][0]["id"]
    assert {k: v for k, v in result["curves"][0].items() if k != "id"} == {
        k: v for k, v in source["curves"][0].items() if k != "id"
    }
    assert source["settings"]["title"] == "Torque"  # 原本を汚さない
    assert source["curves"][0]["id"] == "curve-before"


def test_copy_settings_and_column_mapping_are_independent():
    source = _source()
    result = clone_graph_definition(source, [])
    result["curves"][0]["columns"]["x"] = 4
    result["curves"][0]["color"] = "#000000"
    result["settings"]["x_min"] = 10
    assert source["curves"][0]["columns"]["x"] == 0
    assert source["curves"][0]["color"] == "#aa00bb"
    assert source["settings"]["x_min"] == -14.0


def test_repeated_copies_get_distinct_names():
    assert unique_copy_title("Graph 1", ["Graph 1"]) == "Graph 1 (コピー)"
    assert unique_copy_title("Graph 1", ["Graph 1 (コピー)"]) == "Graph 1 (コピー 2)"
    assert unique_copy_title("Graph 1 (コピー 2)", ["Graph 1 (コピー)", "Graph 1 (コピー 2)"]) == "Graph 1 (コピー 3)"


def test_empty_graph_can_be_copied():
    copied = clone_graph_definition({"id": "one", "settings": {"title": "Empty"}, "curves": []}, [])
    assert copied["curves"] == []
    assert copied["settings"]["title"] == "Empty (コピー)"
