"""凡例上の座標から曲線IDを特定する（Qtのイベント処理から分離）。

凡例の文字（LabelItem）の矩形だけを対象にする。色見本部分のクリックや
凡例のドラッグによる移動は従来どおり利用できるようにする。
"""
from __future__ import annotations


def curve_id_at_legend_label(legend, scene_position, plot_items: dict) -> str | None:
    """scene_position にある凡例の文字に対応する曲線IDを返す。

    Parameters
    ----------
    legend:
        pyqtgraph.LegendItem（items に (ItemSample, LabelItem) が並ぶ）。
    scene_position:
        Qt のシーン座標（QPointF）。
    plot_items:
        GraphPanel.items と同じ {curve_id: PlotDataItem}。

    Returns
    -------
    str | None:
        文字部分以外／削除済みの曲線なら None。
    """
    if legend is None:
        return None

    # 曲線名の変更時に凡例のLabelItemが作り直されても追従できるよう、
    # 最新のLegendItem.itemsとPlotDataItemから毎回対応を取得する。
    curve_ids = {id(item): curve_id for curve_id, item in plot_items.items()}
    for sample, label in legend.items:
        if not label.isVisible():
            continue
        curve_id = curve_ids.get(id(sample.item))
        if curve_id is not None and label.sceneBoundingRect().contains(scene_position):
            return curve_id
    return None
