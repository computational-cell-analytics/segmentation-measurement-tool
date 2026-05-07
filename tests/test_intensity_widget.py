"""GUI tests for the napari intensity measurement widget."""
import os

import numpy as np
import pytest

_IN_CI = os.environ.get("CI") == "true"
_CI_XFAIL = pytest.mark.xfail(
    _IN_CI,
    reason="viewer.add_image() requires an active GL context, unavailable in headless CI",
    strict=False,
)


def test_widget_instantiation(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    viewer = make_napari_viewer()
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    assert widget is not None


def test_seg_combo_populated_on_labels_add(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    viewer = make_napari_viewer()
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg")
    items = [widget._seg_combo.itemText(i) for i in range(widget._seg_combo.count())]
    assert "seg" in items


@_CI_XFAIL
def test_img_combo_populated_on_image_add(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    viewer = make_napari_viewer()
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_image(np.zeros((10, 10), dtype=float), name="img")
    items = [widget._img_combo.itemText(i) for i in range(widget._img_combo.count())]
    assert "img" in items


@_CI_XFAIL
def test_run_measurement_writes_layer_features(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    intensity = np.ones((20, 20), dtype=np.float32) * 5.0
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    viewer.add_image(intensity, name="img")
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._img_combo.setCurrentText("img")
    widget._run_measurement()
    feats = seg_layer.features
    assert "index" in feats.columns
    assert "mean_intensity" in feats.columns
    # The features table is padded so row position == label value, so a NaN
    # row exists for the background (label 0).  Drop NaN rows to inspect the
    # actual measurement.
    real = feats.dropna(subset=["mean_intensity"])
    assert len(real) == 1
    assert int(real["index"].iloc[0]) == 1


@_CI_XFAIL
def test_target_combo_lists_groups(make_napari_viewer, qtbot):
    from segmentation_measurement._groups import (
        ROLE_INTENSITY_IMAGE,
        ROLE_SEGMENTATION,
        set_group,
    )
    from segmentation_measurement._intensity_widget import IntensityWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    viewer.add_image(np.zeros((10, 10), dtype=float), name="img_01")
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    items = lambda: [
        widget._target_combo.itemText(i)
        for i in range(widget._target_combo.count())
    ]
    assert items() == ["<single layer>"]
    set_group(
        viewer,
        "exp_1",
        {
            ROLE_SEGMENTATION: ["cells_01"],
            ROLE_INTENSITY_IMAGE: ["img_01"],
        },
    )
    assert "exp_1" in items()
    assert widget._target_combo.currentText() == "exp_1"


@_CI_XFAIL
def test_group_mode_iterates_pairs(make_napari_viewer, qtbot):
    from segmentation_measurement._groups import (
        ROLE_INTENSITY_IMAGE,
        ROLE_SEGMENTATION,
        set_group,
    )
    from segmentation_measurement._intensity_widget import IntensityWidget
    seg1 = np.zeros((20, 20), dtype=np.int32)
    seg1[2:8, 2:8] = 1
    seg2 = np.zeros((20, 20), dtype=np.int32)
    seg2[3:9, 3:9] = 1
    img1 = np.ones((20, 20), dtype=np.float32) * 5.0
    img2 = np.ones((20, 20), dtype=np.float32) * 9.0
    viewer = make_napari_viewer()
    seg_layer1 = viewer.add_labels(seg1, name="cells_01")
    seg_layer2 = viewer.add_labels(seg2, name="cells_02")
    viewer.add_image(img1, name="img_01")
    viewer.add_image(img2, name="img_02")
    set_group(
        viewer,
        "exp_1",
        {
            ROLE_SEGMENTATION: ["cells_01", "cells_02"],
            ROLE_INTENSITY_IMAGE: ["img_01", "img_02"],
        },
    )
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    assert not widget._seg_combo.isEnabled()
    widget._run_measurement()
    feats1 = seg_layer1.features
    feats2 = seg_layer2.features
    assert "mean_intensity" in feats1.columns
    assert "mean_intensity" in feats2.columns
    real1 = feats1.dropna(subset=["mean_intensity"])
    real2 = feats2.dropna(subset=["mean_intensity"])
    assert abs(float(real1["mean_intensity"].iloc[0]) - 5.0) < 1e-6
    assert abs(float(real2["mean_intensity"].iloc[0]) - 9.0) < 1e-6


def test_group_mode_without_intensity_role_raises(make_napari_viewer, qtbot):
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    from segmentation_measurement._intensity_widget import IntensityWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=np.int32), name="cells_01")
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    with pytest.raises(ValueError, match="no intensity image"):
        widget._run_measurement()


@_CI_XFAIL
def test_running_measurement_twice_overwrites(make_napari_viewer, qtbot):
    """Re-running on the same layer silently overwrites overlapping columns."""
    from segmentation_measurement._intensity_widget import IntensityWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    intensity_a = np.ones((20, 20), dtype=np.float32) * 5.0
    intensity_b = np.ones((20, 20), dtype=np.float32) * 9.0
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    viewer.add_image(intensity_a, name="ia")
    viewer.add_image(intensity_b, name="ib")
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._img_combo.setCurrentText("ia")
    widget._run_measurement()
    widget._img_combo.setCurrentText("ib")
    widget._run_measurement()
    # Row position == label value; label 1 is at row 1 (row 0 is background).
    feats = seg_layer.features
    assert abs(float(feats.loc[feats["index"] == 1, "mean_intensity"].iloc[0]) - 9.0) < 1e-6
