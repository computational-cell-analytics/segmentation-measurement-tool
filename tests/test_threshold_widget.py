"""GUI tests for the napari threshold analysis widget."""
import os

import numpy as np
import pandas as pd
import pytest

_IN_CI = os.environ.get("CI") == "true"
_CI_XFAIL = pytest.mark.xfail(
    _IN_CI,
    reason="viewer.add_labels() may require an active GL context in headless CI",
    strict=False,
)


def _seg_with_features(viewer, seg, features_df, name="seg"):
    layer = viewer.add_labels(seg, name=name)
    layer.features = features_df
    return layer


def test_widget_instantiation(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    viewer = make_napari_viewer()
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    assert widget is not None


def test_seg_combo_populated_on_labels_add(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    viewer = make_napari_viewer()
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg")
    items = [widget._seg_combo.itemText(i) for i in range(widget._seg_combo.count())]
    assert "seg" in items


def test_select_layer_populates_col_combo(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:5, 2:5] = 1
    seg[10:13, 10:13] = 2
    df = pd.DataFrame({
        "index": [1, 2],
        "mean_intensity": [10.0, 90.0],
        "area": [100.0, 200.0],
    })
    viewer = make_napari_viewer()
    _seg_with_features(viewer, seg, df, name="seg")
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    cols = [widget._col_combo.itemText(i) for i in range(widget._col_combo.count())]
    assert "mean_intensity" in cols
    assert "area" in cols
    assert "index" not in cols  # the key column is excluded


def test_suggest_thresholds_sets_spinbox_values(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[0:2, 0:2] = 1
    seg[5:7, 5:7] = 2
    seg[10:12, 10:12] = 3
    seg[15:17, 15:17] = 4
    df = pd.DataFrame({
        "index": [1, 2, 3, 4],
        "mean_intensity": [10.0, 30.0, 70.0, 90.0],
    })
    viewer = make_napari_viewer()
    _seg_with_features(viewer, seg, df, name="seg")
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("mean_intensity")
    widget._suggest_thresholds()
    assert len(widget._threshold_spins) == 1
    assert widget._threshold_spins[0].value() > 0.0


def test_n_categories_rebuilds_widgets(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    viewer = make_napari_viewer()
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    widget._n_spin.setValue(4)
    assert len(widget._threshold_spins) == 3
    assert len(widget._name_edits) == 4


@_CI_XFAIL
def test_categorize_creates_output_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    seg[12:18, 12:18] = 2
    df = pd.DataFrame({"index": [1, 2], "mean_intensity": [10.0, 90.0]})
    viewer = make_napari_viewer()
    _seg_with_features(viewer, seg, df, name="seg")
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("mean_intensity")
    widget._threshold_spins[0].setValue(50.0)
    widget._out_name.setText("my_categories")
    widget._run_categorization()
    layer_names = [layer.name for layer in viewer.layers]
    assert "my_categories" in layer_names
    result = viewer.layers["my_categories"].data
    assert np.all(result[2:8, 2:8] == 1)
    assert np.all(result[12:18, 12:18] == 2)


@_CI_XFAIL
def test_categorize_writes_back_to_source_features(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    seg[12:18, 12:18] = 2
    df = pd.DataFrame({"index": [1, 2], "mean_intensity": [10.0, 90.0]})
    viewer = make_napari_viewer()
    seg_layer = _seg_with_features(viewer, seg, df, name="seg")
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("mean_intensity")
    widget._threshold_spins[0].setValue(50.0)
    widget._run_categorization()
    feats = seg_layer.features
    assert "category_id" in feats.columns
    assert "category_name" in feats.columns


@_CI_XFAIL
def test_categorize_updates_existing_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    df = pd.DataFrame({"index": [1], "mean_intensity": [10.0]})
    viewer = make_napari_viewer()
    _seg_with_features(viewer, seg, df, name="seg")
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("mean_intensity")
    widget._threshold_spins[0].setValue(50.0)
    widget._out_name.setText("cats")
    widget._run_categorization()
    n_layers = len(viewer.layers)
    widget._run_categorization()
    assert len(viewer.layers) == n_layers


def test_target_combo_lists_groups(make_napari_viewer, qtbot):
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    from segmentation_measurement._threshold_widget import ThresholdWidget
    viewer = make_napari_viewer()
    df = pd.DataFrame({"index": [1, 2], "value": [10.0, 20.0]})
    _seg_with_features(
        viewer, np.zeros((10, 10), dtype=np.int32), df, name="cells_01"
    )
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    items = lambda: [
        widget._target_combo.itemText(i)
        for i in range(widget._target_combo.count())
    ]
    assert items() == ["<single layer>"]
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    assert "exp_1" in items()
    assert "<all groups>" not in items()


def test_target_single_member_group_disables_seg_combo(
    make_napari_viewer, qtbot
):
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    from segmentation_measurement._threshold_widget import ThresholdWidget
    viewer = make_napari_viewer()
    df = pd.DataFrame({"index": [1, 2], "value": [10.0, 20.0]})
    _seg_with_features(
        viewer, np.zeros((10, 10), dtype=np.int32), df, name="cells_01"
    )
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    assert not widget._seg_combo.isEnabled()
    cols = [
        widget._col_combo.itemText(i)
        for i in range(widget._col_combo.count())
    ]
    assert "value" in cols


def test_multi_member_histogram_uses_concat(make_napari_viewer, qtbot):
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    from segmentation_measurement._threshold_widget import ThresholdWidget
    viewer = make_napari_viewer()
    df1 = pd.DataFrame({"index": [1, 2], "value": [10.0, 20.0]})
    df2 = pd.DataFrame({"index": [1, 2], "value": [30.0, 40.0]})
    _seg_with_features(
        viewer, np.zeros((10, 10), dtype=np.int32), df1, name="cells_01"
    )
    _seg_with_features(
        viewer, np.zeros((10, 10), dtype=np.int32), df2, name="cells_02"
    )
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    widget._col_combo.setCurrentText("value")
    feats = widget._current_features_frame()
    assert feats is not None
    assert "_source_layer" in feats.columns
    assert set(feats["_source_layer"].unique()) == {"cells_01", "cells_02"}


def test_multi_member_categorize_writes_back_per_layer(
    make_napari_viewer, qtbot
):
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    from segmentation_measurement._threshold_widget import ThresholdWidget
    seg1 = np.zeros((20, 20), dtype=np.int32)
    seg1[2:8, 2:8] = 1
    seg1[12:18, 12:18] = 2
    seg2 = np.zeros((20, 20), dtype=np.int32)
    seg2[2:8, 2:8] = 1
    df1 = pd.DataFrame({"index": [1, 2], "value": [10.0, 90.0]})
    df2 = pd.DataFrame({"index": [1], "value": [55.0]})
    viewer = make_napari_viewer()
    layer1 = _seg_with_features(viewer, seg1, df1, name="cells_01")
    layer2 = _seg_with_features(viewer, seg2, df2, name="cells_02")
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("value")
    widget._threshold_spins[0].setValue(50.0)
    widget._out_name.setText("cats")
    widget._run_categorization()
    assert "category_id" in layer1.features.columns
    assert "category_id" in layer2.features.columns
    layer_names = [layer.name for layer in viewer.layers]
    assert "cats_cells_01" in layer_names
    assert "cats_cells_02" in layer_names


def test_single_member_group_no_suffix(make_napari_viewer, qtbot):
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    from segmentation_measurement._threshold_widget import ThresholdWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    seg[12:18, 12:18] = 2
    df = pd.DataFrame({"index": [1, 2], "value": [10.0, 90.0]})
    viewer = make_napari_viewer()
    _seg_with_features(viewer, seg, df, name="cells_01")
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("value")
    widget._threshold_spins[0].setValue(50.0)
    widget._out_name.setText("cats")
    widget._run_categorization()
    layer_names = [layer.name for layer in viewer.layers]
    assert "cats" in layer_names
    assert "cats_cells_01" not in layer_names


def test_works_with_morphology_features(make_napari_viewer, qtbot):
    """Threshold widget accepts morphology measurement features on the layer."""
    from segmentation_measurement._threshold_widget import ThresholdWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[0:2, 0:2] = 1
    seg[5:7, 5:7] = 2
    seg[10:12, 10:12] = 3
    df = pd.DataFrame({
        "index": [1, 2, 3],
        "area": [100.0, 200.0, 300.0],
        "sphericity": [0.8, 0.9, 0.95],
    })
    viewer = make_napari_viewer()
    _seg_with_features(viewer, seg, df, name="seg")
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    cols = [widget._col_combo.itemText(i) for i in range(widget._col_combo.count())]
    assert "area" in cols
    assert "sphericity" in cols
