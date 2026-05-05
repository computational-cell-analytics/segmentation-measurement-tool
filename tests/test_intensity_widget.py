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
