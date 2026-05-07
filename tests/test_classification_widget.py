"""GUI tests for the napari classification widget."""

from __future__ import annotations

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


def _make_annotated_df(n=20):
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "index": np.arange(1, n + 1),
        "mean_intensity": np.concatenate([
            rng.uniform(0, 40, n // 2),
            rng.uniform(60, 100, n - n // 2),
        ]),
        "area": rng.uniform(10, 200, n),
    })
    annotations = np.zeros(n, dtype=int)
    annotations[: n // 2] = 1
    annotations[n // 2 :] = 2
    df["annotation"] = annotations
    return df


def _make_seg_with_features(viewer, n=20, features=None, name="seg"):
    seg = np.zeros((30, 30), dtype=np.int32)
    for i in range(1, n + 1):
        seg[i % 30, (i + 5) % 30] = i
    if features is None:
        features = _make_annotated_df(n)
    layer = viewer.add_labels(seg, name=name)
    layer.features = features
    return layer


def test_widget_instantiation(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    viewer = make_napari_viewer()
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    assert widget is not None


def test_seg_combo_populated_on_labels_add(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    viewer = make_napari_viewer()
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg")
    items = [widget._seg_combo.itemText(i) for i in range(widget._seg_combo.count())]
    assert "seg" in items


def test_ann_combo_populated_on_labels_add(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    viewer = make_napari_viewer()
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg")
    items = [widget._ann_combo.itemText(i) for i in range(widget._ann_combo.count())]
    assert "seg" in items


def test_method_combo_changes_params_stack(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    viewer = make_napari_viewer()
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._method_combo.setCurrentText("Random Forest")
    assert widget._params_stack.currentIndex() == 0
    widget._method_combo.setCurrentText("Logistic Regression")
    assert widget._params_stack.currentIndex() == 1


def test_project_annotations_writes_to_features(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    seg = np.zeros((10, 10), dtype=np.int32)
    seg[1:4, 1:4] = 1
    seg[5:8, 5:8] = 2
    ann = np.zeros_like(seg)
    ann[1:4, 1:4] = 1
    ann[5:8, 5:8] = 2
    df = pd.DataFrame({"index": [1, 2], "mean_intensity": [10.0, 90.0]})
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    seg_layer.features = df
    viewer.add_labels(ann, name="ann")
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._ann_combo.setCurrentText("ann")
    widget._project_annotations()
    feats = seg_layer.features
    assert "annotation" in feats.columns
    anns = feats.set_index("index")["annotation"]
    assert anns[1] == 1
    assert anns[2] == 2


def test_project_annotations_updates_class_names_table(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    seg = np.zeros((10, 10), dtype=np.int32)
    seg[1:4, 1:4] = 1
    ann = np.zeros_like(seg)
    ann[1:4, 1:4] = 1
    df = pd.DataFrame({"index": [1], "mean_intensity": [50.0]})
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    seg_layer.features = df
    viewer.add_labels(ann, name="ann")
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._ann_combo.setCurrentText("ann")
    widget._project_annotations()
    assert widget._class_names_table.rowCount() == 1
    id_item = widget._class_names_table.item(0, 0)
    assert id_item is not None
    assert id_item.text() == "1"


def test_annotation_projection_button_removed(make_napari_viewer, qtbot):
    from qtpy.QtWidgets import QCheckBox, QPushButton
    from segmentation_measurement._classification_widget import ClassificationWidget

    viewer = make_napari_viewer()
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)

    button_texts = [button.text() for button in widget.findChildren(QPushButton)]
    assert "Project annotations to features" not in button_texts
    assert "Load classifier" not in button_texts
    assert "Apply" not in button_texts
    assert "Train & Apply" in button_texts
    live_update = [
        checkbox
        for checkbox in widget.findChildren(QCheckBox)
        if checkbox.text() == "Live Update"
    ]
    assert len(live_update) == 1
    assert live_update[0].isChecked()
    assert not widget._train_btn.isEnabled()


def test_live_update_checkbox_controls_train_button(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget

    viewer = make_napari_viewer()
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)

    assert widget._live_update_checkbox.isChecked()
    assert not widget._train_btn.isEnabled()
    widget._live_update_checkbox.setChecked(False)
    assert widget._train_btn.isEnabled()
    widget._live_update_checkbox.setChecked(True)
    assert not widget._train_btn.isEnabled()


def test_annotation_paint_updates_features_automatically(
    make_napari_viewer, qtbot
):
    from segmentation_measurement._classification_widget import ClassificationWidget

    seg = np.zeros((10, 10), dtype=np.int32)
    seg[1:4, 1:4] = 1
    df = pd.DataFrame({"index": [1], "mean_intensity": [10.0]})
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    seg_layer.features = df
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._create_annotation_layer()
    ann = viewer.layers[widget._ann_combo.currentText()]

    ann.brush_size = 1
    ann.selected_label = 1
    ann.paint((2, 2), ann.selected_label)
    assert "annotation" not in seg_layer.features.columns
    qtbot.wait(widget._annotation_projection_timer.interval() + 50)

    feats = seg_layer.features.set_index("index")
    assert int(feats.loc[1, "annotation"]) == 1


def test_automatic_annotation_projection_preserves_layer_selection(
    make_napari_viewer, qtbot
):
    from segmentation_measurement._classification_widget import ClassificationWidget

    seg = np.zeros((10, 10), dtype=np.int32)
    seg[1:4, 1:4] = 1
    df = pd.DataFrame({"index": [1], "mean_intensity": [10.0]})
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    seg_layer.features = df
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._create_annotation_layer()
    ann = viewer.layers[widget._ann_combo.currentText()]

    viewer.layers.selection.clear()
    viewer.layers.selection.add(ann)
    viewer.layers.selection.active = ann
    ann.brush_size = 1
    ann.selected_label = 1
    ann.paint((2, 2), ann.selected_label)
    qtbot.wait(widget._annotation_projection_timer.interval() + 50)

    feats = seg_layer.features.set_index("index")
    assert int(feats.loc[1, "annotation"]) == 1
    assert viewer.layers.selection.active is ann
    assert ann in viewer.layers.selection
    assert seg_layer not in viewer.layers.selection


def test_annotation_frame_marks_active_annotation_layer(
    make_napari_viewer, qtbot
):
    from segmentation_measurement._classification_widget import (
        _ANNOTATION_FRAME_LAYER_NAME,
        ClassificationWidget,
    )

    seg = np.zeros((10, 12), dtype=np.int32)
    seg[1:4, 1:4] = 1
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    seg_layer.translate = (5, 7)
    seg_layer.scale = (2, 3)
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._create_annotation_layer()
    ann = viewer.layers[widget._ann_combo.currentText()]

    assert _ANNOTATION_FRAME_LAYER_NAME in viewer.layers
    frame = viewer.layers[_ANNOTATION_FRAME_LAYER_NAME]
    expected = np.array([
        [-0.5, -0.5],
        [-0.5, 11.5],
        [9.5, 11.5],
        [9.5, -0.5],
        [-0.5, -0.5],
    ])
    np.testing.assert_allclose(frame.data[0], expected)
    assert tuple(frame.translate) == tuple(ann.translate)
    assert tuple(frame.scale) == tuple(ann.scale)
    assert str(frame.mode) == "pan_zoom"
    assert frame.visible
    assert viewer.layers.selection.active is ann

    ann_items = [
        widget._ann_combo.itemText(i)
        for i in range(widget._ann_combo.count())
    ]
    assert _ANNOTATION_FRAME_LAYER_NAME not in ann_items


def test_annotation_erase_and_relabel_update_features_automatically(
    make_napari_viewer, qtbot
):
    from segmentation_measurement._classification_widget import ClassificationWidget

    seg = np.zeros((10, 10), dtype=np.int32)
    seg[1:4, 1:4] = 1
    df = pd.DataFrame({"index": [1], "mean_intensity": [10.0]})
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    seg_layer.features = df
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._create_annotation_layer()
    ann = viewer.layers[widget._ann_combo.currentText()]
    ann.brush_size = 1

    ann.paint((2, 2), 1)
    qtbot.wait(widget._annotation_projection_timer.interval() + 50)
    assert int(seg_layer.features.set_index("index").loc[1, "annotation"]) == 1

    ann.paint((2, 2), 0)
    qtbot.wait(widget._annotation_projection_timer.interval() + 50)
    assert int(seg_layer.features.set_index("index").loc[1, "annotation"]) == 0

    ann.paint((2, 2), 2)
    qtbot.wait(widget._annotation_projection_timer.interval() + 50)
    assert int(seg_layer.features.set_index("index").loc[1, "annotation"]) == 2


def test_live_update_trains_and_applies_after_annotation_change(
    make_napari_viewer, qtbot
):
    from segmentation_measurement._classification_widget import ClassificationWidget

    seg = np.zeros((10, 10), dtype=np.int32)
    seg[1:4, 1:4] = 1
    seg[5:8, 5:8] = 2
    df = pd.DataFrame({
        "index": [1, 2],
        "mean_intensity": [10.0, 90.0],
    })
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    seg_layer.features = df
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._create_annotation_layer()
    ann = viewer.layers[widget._ann_combo.currentText()]
    viewer.layers.selection.clear()
    viewer.layers.selection.add(ann)
    viewer.layers.selection.active = ann
    live_update_calls = []
    original_live_update = widget._train_and_apply_live

    def wrapped_live_update():
        live_update_calls.append(True)
        original_live_update()

    widget._train_and_apply_live = wrapped_live_update

    ann.brush_size = 1
    ann.paint((2, 2), 1)
    ann.paint((6, 6), 2)
    qtbot.wait(widget._annotation_projection_timer.interval() + 50)

    feats = seg_layer.features.set_index("index")
    assert widget._classifier is not None
    assert "classification_id" in feats.columns
    assert "classification" in viewer.layers
    out = viewer.layers["classification"]
    assert int(out.data[2, 2]) == 1
    assert int(out.data[6, 6]) == 2
    assert viewer.layers.selection.active is ann
    assert ann in viewer.layers.selection
    assert len(live_update_calls) == 1
    qtbot.wait(widget._annotation_projection_timer.interval() * 2)
    assert len(live_update_calls) == 1
    assert not widget._annotation_projection_timer.isActive()


def test_get_class_names_reads_table(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    from qtpy.QtWidgets import QTableWidgetItem
    viewer = make_napari_viewer()
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._class_names_table.setRowCount(2)
    widget._class_names_table.setItem(0, 0, QTableWidgetItem("1"))
    widget._class_names_table.setItem(0, 1, QTableWidgetItem("type_A"))
    widget._class_names_table.setItem(1, 0, QTableWidgetItem("2"))
    widget._class_names_table.setItem(1, 1, QTableWidgetItem("type_B"))
    names = widget._get_class_names()
    assert names == {1: "type_A", 2: "type_B"}


def test_train_and_apply_writes_classification_columns(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    viewer = make_napari_viewer()
    seg_layer = _make_seg_with_features(viewer, n=20, name="seg")
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._method_combo.setCurrentText("Logistic Regression")
    widget._train_and_apply()
    feats = seg_layer.features
    assert "classification_id" in feats.columns
    assert "classification_name" in feats.columns


def test_train_and_apply_stores_classifier(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, n=20, name="seg")
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._train_and_apply()
    assert widget._classifier is not None


def test_train_skipped_when_no_annotation_column(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    df = pd.DataFrame({
        "index": [1, 2, 3],
        "mean_intensity": [10.0, 50.0, 90.0],
    })  # no annotation column
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, n=3, features=df, name="seg")
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._train_and_apply()
    assert widget._classifier is None


def test_random_forest_method(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    viewer = make_napari_viewer()
    seg_layer = _make_seg_with_features(viewer, n=20, name="seg")
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._method_combo.setCurrentText("Random Forest")
    widget._rf_n_spin.setValue(10)
    widget._train_and_apply()
    assert widget._classifier is not None
    assert "classification_id" in seg_layer.features.columns


def test_classification_ids_are_one_based(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    viewer = make_napari_viewer()
    seg_layer = _make_seg_with_features(viewer, n=20, name="seg")
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._train_and_apply()
    cids = seg_layer.features["classification_id"].values
    nonzero = cids[cids > 0]
    assert len(nonzero) > 0
    assert nonzero.min() >= 1


@_CI_XFAIL
def test_train_and_apply_creates_output_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[1:6, 1:6] = 1
    seg[7:12, 7:12] = 2
    df = _make_annotated_df(2)
    df["index"] = [1, 2]
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    seg_layer.features = df
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._out_name.setText("clf_out")
    widget._train_and_apply()
    layer_names = [layer.name for layer in viewer.layers]
    assert "clf_out" in layer_names


@_CI_XFAIL
def test_train_and_apply_updates_existing_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    for i in range(1, 5):
        seg[i, i] = i
    df = _make_annotated_df(4)
    df["index"] = [1, 2, 3, 4]
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    seg_layer.features = df
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._out_name.setText("clf_layer")
    widget._train_and_apply()
    n_layers = len(viewer.layers)
    widget._train_and_apply()
    assert len(viewer.layers) == n_layers


@_CI_XFAIL
def test_create_annotation_layer(make_napari_viewer, qtbot):
    from napari.layers import Labels
    from segmentation_measurement._classification_widget import (
        _ANNOTATION_INITIAL_BRUSH_SIZE,
        ClassificationWidget,
    )
    seg = np.zeros((10, 10), dtype=np.int32)
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    initial_count = sum(isinstance(layer, Labels) for layer in viewer.layers)
    widget._create_annotation_layer()
    label_count = sum(isinstance(layer, Labels) for layer in viewer.layers)
    assert label_count == initial_count + 1
    assert widget._ann_combo.currentText() == "annotations"
    assert viewer.layers["annotations"].brush_size == _ANNOTATION_INITIAL_BRUSH_SIZE


def test_project_annotations_helper():
    from segmentation_measurement._classification_widget import _project_annotations_to_segments
    seg = np.array([[1, 1, 0], [0, 2, 2], [2, 0, 0]], dtype=np.int32)
    ann = np.array([[1, 1, 0], [0, 2, 1], [2, 0, 0]], dtype=np.int32)
    result = _project_annotations_to_segments(seg, ann)
    assert result[1] == 1
    assert result[2] == 2  # majority (2 votes for 2, 1 vote for 1)


def test_project_annotations_all_unannotated():
    from segmentation_measurement._classification_widget import _project_annotations_to_segments
    seg = np.array([[1, 1, 0], [0, 2, 2]], dtype=np.int32)
    ann = np.zeros_like(seg)
    result = _project_annotations_to_segments(seg, ann)
    assert result[1] == 0
    assert result[2] == 0


def test_project_annotations_3d():
    from segmentation_measurement._classification_widget import _project_annotations_to_segments
    seg = np.zeros((5, 5, 5), dtype=np.int32)
    seg[1:3, 1:3, 1:3] = 1
    ann = np.zeros_like(seg)
    ann[1:3, 1:3, 1:3] = 2
    result = _project_annotations_to_segments(seg, ann)
    assert result[1] == 2


def test_target_combo_lists_groups(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, n=20, name="cells_01")
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    items = lambda: [
        widget._target_combo.itemText(i)
        for i in range(widget._target_combo.count())
    ]
    assert items() == ["<single layer>"]
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    assert "exp_1" in items()
    assert widget._target_combo.currentText() == "exp_1"


def test_group_mode_seg_combo_restricted_to_members(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, n=20, name="cells_01")
    _make_seg_with_features(viewer, n=20, name="cells_02")
    _make_seg_with_features(viewer, n=20, name="other")
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    seg_items = [
        widget._seg_combo.itemText(i)
        for i in range(widget._seg_combo.count())
    ]
    assert seg_items == ["cells_01", "cells_02"]


@_CI_XFAIL
def test_group_mode_train_and_apply(make_napari_viewer, qtbot):
    from napari.layers.utils._link_layers import get_linked_layers
    from segmentation_measurement._classification_widget import ClassificationWidget
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    viewer = make_napari_viewer()
    layer1 = _make_seg_with_features(viewer, n=20, name="cells_01")
    layer2 = _make_seg_with_features(viewer, n=20, name="cells_02")
    layer1.translate = (0.0, 0.0)
    layer2.translate = (0.0, 30.0)
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    widget._method_combo.setCurrentText("Random Forest")
    widget._update_class_names_table([1, 2])
    widget._out_name.setText("cls")
    widget._train_and_apply()
    assert "classification_id" in layer1.features.columns
    assert "classification_id" in layer2.features.columns
    layer_names = [layer.name for layer in viewer.layers]
    assert "cls_cells_01" in layer_names
    assert "cls_cells_02" in layer_names
    assert tuple(viewer.layers["cls_cells_01"].translate) == (0.0, 0.0)
    assert tuple(viewer.layers["cls_cells_02"].translate) == (0.0, 30.0)
    assert viewer.layers["cls_cells_02"] in get_linked_layers(
        viewer.layers["cls_cells_01"]
    )


@_CI_XFAIL
def test_group_mode_train_with_unprojected_member(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group

    viewer = make_napari_viewer()
    layer1 = _make_seg_with_features(viewer, n=20, name="cells_01")
    unannotated = _make_annotated_df(20).drop(columns=["annotation"])
    layer2 = _make_seg_with_features(
        viewer, n=20, features=unannotated, name="cells_02"
    )
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    widget._method_combo.setCurrentText("Random Forest")
    widget._update_class_names_table([1, 2])
    widget._out_name.setText("cls")
    widget._train_and_apply()

    assert "classification_id" in layer1.features.columns
    assert "classification_id" in layer2.features.columns
    assert "cls_cells_01" in [layer.name for layer in viewer.layers]
    assert "cls_cells_02" in [layer.name for layer in viewer.layers]


def test_class_color_dict_deterministic_per_id():
    from segmentation_measurement._classification_widget import _class_color_dict
    full = _class_color_dict([1, 2, 3], max_class=3)
    sparse = _class_color_dict([3], max_class=3)
    assert full[3] == sparse[3]


def test_class_color_dict_uses_id_not_position():
    from segmentation_measurement._classification_widget import _class_color_dict
    # Class 1 should get a different colour from class 3 — the bug was
    # that a layer containing only class 3 would receive the colour of
    # class 1 because of position-based assignment.
    colors = _class_color_dict([3], max_class=3)
    full = _class_color_dict([1, 2, 3], max_class=3)
    assert colors[3] != full[1]


def test_class_color_dict_picks_tab20_for_many_classes():
    from segmentation_measurement._classification_widget import _class_color_dict
    colors = _class_color_dict([1, 12], max_class=12)
    # tab10 has 10 colours; tab20 has 20.  With max_class=12 we must be in
    # tab20, so class 12 maps to tab20 index 11 (not wrapping back to 1).
    import matplotlib
    cmap20 = matplotlib.colormaps["tab20"]
    assert colors[12] == tuple(cmap20(11))


def test_apply_class_colors_keeps_missing_global_classes_visible(
    make_napari_viewer,
):
    from segmentation_measurement._classification_widget import _apply_class_colors
    viewer = make_napari_viewer()
    layer = viewer.add_labels(np.zeros((10, 10), dtype=np.int32), name="cls")
    _apply_class_colors(layer, [3], max_class=3)
    assert layer.colormap.color_dict[1][3] > 0
    assert layer.colormap.color_dict[2][3] > 0
    assert layer.colormap.color_dict[3][3] > 0


def test_compress_decompress_round_trip():
    from segmentation_measurement._classification_widget import (
        _compress_annotation,
        _decompress_annotation,
    )
    arr = np.zeros((30, 30), dtype=np.int32)
    arr[5:10, 5:10] = 1
    arr[20:25, 20:25] = 2
    compressed = _compress_annotation(arr)
    restored = _decompress_annotation(compressed)
    np.testing.assert_array_equal(restored, arr)


def test_compress_empty_annotation():
    from segmentation_measurement._classification_widget import (
        _compress_annotation,
        _decompress_annotation,
    )
    arr = np.zeros((10, 10), dtype=np.int32)
    compressed = _compress_annotation(arr)
    assert compressed["values"].size == 0
    restored = _decompress_annotation(compressed)
    np.testing.assert_array_equal(restored, arr)


def test_group_target_does_not_clear_segmentation_when_no_annotation(
    make_napari_viewer, qtbot
):
    """Selecting a group must not zero a segmentation layer just because
    no annotation layer has been chosen yet.

    Regression: the annotation combo defaulted to the first Labels layer
    in the viewer (often a group member), so the per-member persistence
    code zeroed that layer when loading the first member's (empty) cache.
    """
    from segmentation_measurement._classification_widget import ClassificationWidget
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    viewer = make_napari_viewer()
    layer1 = _make_seg_with_features(viewer, n=20, name="cells_01")
    layer2 = _make_seg_with_features(viewer, n=20, name="cells_02")
    seg1_before = layer1.data.copy()
    seg2_before = layer2.data.copy()
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    widget._seg_combo.setCurrentText("cells_02")  # also trigger a member switch
    np.testing.assert_array_equal(layer1.data, seg1_before)
    np.testing.assert_array_equal(layer2.data, seg2_before)


def test_ann_combo_defaults_to_none_sentinel(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    assert widget._ann_combo.currentText() == "(none)"


def test_member_persistence_round_trip(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, n=20, name="cells_01")
    _make_seg_with_features(viewer, n=20, name="cells_02")
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    ann = viewer.add_labels(
        np.zeros((30, 30), dtype=np.int32), name="annotations"
    )
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    widget._ann_combo.setCurrentText("annotations")

    # Paint annotations on member 1.
    widget._seg_combo.setCurrentText("cells_01")
    new_data = np.zeros((30, 30), dtype=np.int32)
    new_data[5:10, 5:10] = 1
    ann.data = new_data

    # Switch to member 2 — annotation layer should be cleared.
    widget._seg_combo.setCurrentText("cells_02")
    assert int(ann.data.sum()) == 0

    # Paint different annotations on member 2.
    new_data2 = np.zeros((30, 30), dtype=np.int32)
    new_data2[20:25, 20:25] = 2
    ann.data = new_data2

    # Switch back to member 1 — original member-1 annotations restored.
    widget._seg_combo.setCurrentText("cells_01")
    np.testing.assert_array_equal(ann.data[5:10, 5:10], 1)
    assert int(ann.data[20:25, 20:25].sum()) == 0

    # Switch to member 2 again — its painted annotations come back.
    widget._seg_combo.setCurrentText("cells_02")
    np.testing.assert_array_equal(ann.data[20:25, 20:25], 2)
    assert int(ann.data[5:10, 5:10].sum()) == 0


def test_group_annotation_layer_follows_member_and_projects(
    make_napari_viewer, qtbot
):
    from segmentation_measurement._classification_widget import (
        ClassificationWidget,
        _class_color_dict,
    )
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group

    viewer = make_napari_viewer()
    layer1 = _make_seg_with_features(viewer, n=20, name="cells_01")
    layer2 = _make_seg_with_features(viewer, n=20, name="cells_02")
    layer1.translate = (0.0, 0.0)
    layer2.translate = (0.0, 30.0)
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )

    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    widget._create_annotation_layer()
    ann = viewer.layers[widget._ann_combo.currentText()]

    assert tuple(ann.translate) == (0.0, 0.0)
    expected_colors = _class_color_dict([1, 2], max_class=10)
    np.testing.assert_allclose(ann.colormap.color_dict[1], expected_colors[1])
    np.testing.assert_allclose(ann.colormap.color_dict[2], expected_colors[2])
    ann_data = np.zeros((30, 30), dtype=np.int32)
    ann_data[1, 6] = 1
    ann.data = ann_data
    widget._project_annotations()
    feats1 = layer1.features.set_index("index")
    assert int(feats1.loc[1, "annotation"]) == 1
    ann.selected_label = 3
    assert ann.colormap.color_dict[3][3] > 0
    ann.brush_size = 1
    ann.paint((3, 8), ann.selected_label)
    assert int(ann.data[3, 8]) == 3
    widget._project_annotations()
    feats1 = layer1.features.set_index("index")
    assert int(feats1.loc[3, "annotation"]) == 3

    widget._seg_combo.setCurrentText("cells_02")
    assert tuple(ann.translate) == (0.0, 30.0)
    assert int(ann.data.sum()) == 0
    ann_data = np.zeros((30, 30), dtype=np.int32)
    ann_data[2, 7] = 2
    ann.data = ann_data
    widget._project_annotations()
    feats2 = layer2.features.set_index("index")
    assert int(feats2.loc[2, "annotation"]) == 2

    widget._seg_combo.setCurrentText("cells_01")
    assert tuple(ann.translate) == (0.0, 0.0)
    assert int(ann.data[1, 6]) == 1
    feats1 = layer1.features.set_index("index")
    feats2 = layer2.features.set_index("index")
    assert int(feats1.loc[1, "annotation"]) == 1
    assert int(feats2.loc[2, "annotation"]) == 2
    expected_colors = _class_color_dict([1, 2], max_class=10)
    np.testing.assert_allclose(ann.colormap.color_dict[1], expected_colors[1])
    np.testing.assert_allclose(ann.colormap.color_dict[2], expected_colors[2])


def test_persistence_inactive_in_single_mode(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, n=20, name="cells_01")
    _make_seg_with_features(viewer, n=20, name="cells_02")
    ann = viewer.add_labels(
        np.zeros((30, 30), dtype=np.int32), name="annotations"
    )
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    # In single-layer mode, switching the seg combo must not touch the
    # annotation layer.
    widget._seg_combo.setCurrentText("cells_01")
    new_data = np.zeros((30, 30), dtype=np.int32)
    new_data[5:10, 5:10] = 1
    ann.data = new_data
    widget._ann_combo.setCurrentText("annotations")
    widget._seg_combo.setCurrentText("cells_02")
    np.testing.assert_array_equal(ann.data[5:10, 5:10], 1)
    assert widget._member_annotations == {}


def test_target_switch_saves_current_member(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, n=20, name="cells_01")
    _make_seg_with_features(viewer, n=20, name="cells_02")
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    ann = viewer.add_labels(
        np.zeros((30, 30), dtype=np.int32), name="annotations"
    )
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._ann_combo.setCurrentText("annotations")
    widget._target_combo.setCurrentText("exp_1")
    # Paint on member 1.
    new_data = np.zeros((30, 30), dtype=np.int32)
    new_data[5:10, 5:10] = 1
    ann.data = new_data
    # Switch back to single-layer mode — the painted annotations should be
    # cached so coming back to the group restores them.
    widget._target_combo.setCurrentText("<single layer>")
    assert "cells_01" in widget._member_annotations
    widget._target_combo.setCurrentText("exp_1")
    widget._seg_combo.setCurrentText("cells_01")
    np.testing.assert_array_equal(ann.data[5:10, 5:10], 1)


def test_collect_annotation_ids_pools_across_members(make_napari_viewer, qtbot):
    from segmentation_measurement._classification_widget import ClassificationWidget
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    viewer = make_napari_viewer()
    df1 = _make_annotated_df(20).copy()
    df1["annotation"] = [1] * 10 + [2] * 10
    df2 = _make_annotated_df(20).copy()
    df2["annotation"] = [3] * 10 + [2] * 10
    _make_seg_with_features(viewer, n=20, features=df1, name="cells_01")
    _make_seg_with_features(viewer, n=20, features=df2, name="cells_02")
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    assert widget._collect_annotation_ids() == [1, 2, 3]
