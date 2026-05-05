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
    from segmentation_measurement._classification_widget import ClassificationWidget
    seg = np.zeros((10, 10), dtype=np.int32)
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = ClassificationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    initial_count = len(viewer.layers)
    widget._create_annotation_layer()
    assert len(viewer.layers) == initial_count + 1
    assert widget._ann_combo.currentText() == "annotations"


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
