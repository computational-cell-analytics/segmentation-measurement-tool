"""GUI tests for the napari morphology measurement widget."""
import os

import numpy as np
import pytest

_IN_CI = os.environ.get("CI") == "true"
_CI_XFAIL = pytest.mark.xfail(
    _IN_CI,
    reason="viewer.add_labels() may require an active GL context in headless CI",
    strict=False,
)


def test_widget_instantiation(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    viewer = make_napari_viewer()
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    assert widget is not None


def test_seg_combo_populated_on_labels_add(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    viewer = make_napari_viewer()
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg")
    items = [widget._seg_combo.itemText(i) for i in range(widget._seg_combo.count())]
    assert "seg" in items


def test_default_shows_two_spinboxes(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    viewer = make_napari_viewer()
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    assert len(widget._scale_spins) == 2


def test_default_scale_is_one(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    viewer = make_napari_viewer()
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    assert all(abs(s.value() - 1.0) < 1e-9 for s in widget._scale_spins)


def test_2d_seg_shows_two_spinboxes(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg2d")
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg2d")
    assert len(widget._scale_spins) == 2


def test_3d_seg_shows_three_spinboxes(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((5, 10, 10), dtype=int), name="seg3d")
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg3d")
    assert len(widget._scale_spins) == 3


def test_layer_scale_populates_spinboxes(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    viewer = make_napari_viewer()
    viewer.add_labels(
        np.zeros((10, 10), dtype=int), name="seg", scale=[0.5, 0.25]
    )
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    assert abs(widget._scale_spins[0].value() - 0.5) < 1e-6   # Y
    assert abs(widget._scale_spins[1].value() - 0.25) < 1e-6  # X


def test_3d_layer_scale_populates_three_spinboxes(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    viewer = make_napari_viewer()
    viewer.add_labels(
        np.zeros((5, 10, 10), dtype=int), name="seg3d", scale=[2.0, 0.5, 0.5]
    )
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg3d")
    assert len(widget._scale_spins) == 3
    assert abs(widget._scale_spins[0].value() - 2.0) < 1e-6  # Z
    assert abs(widget._scale_spins[1].value() - 0.5) < 1e-6  # Y
    assert abs(widget._scale_spins[2].value() - 0.5) < 1e-6  # X


def test_run_measurement_writes_layer_features(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    seg[12:18, 12:18] = 2
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._run_measurement()
    feats = seg_layer.features
    assert "index" in feats.columns
    assert "area" in feats.columns
    assert "sphericity" in feats.columns
    assert "solidity" in feats.columns
    # Padded so row position == label value: row 0 is background NaN, rows 1
    # and 2 are the measured segments.
    real = feats.dropna(subset=["area"])
    assert len(real) == 2
    assert set(real["index"]) == {1, 2}


def test_isotropic_scale_applied_to_area(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[4:14, 4:14] = 1  # 10x10 = 100 pixels
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")

    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._run_measurement()
    # Row 0 is background NaN; label 1 is at row 1 after padding.
    assert abs(seg_layer.features.iloc[1]["area"] - 100.0) < 0.1

    widget_scaled = MorphologyWidget(viewer)
    qtbot.addWidget(widget_scaled)
    widget_scaled._seg_combo.setCurrentText("seg")
    for spin in widget_scaled._scale_spins:
        spin.setValue(0.5)
    widget_scaled._run_measurement()
    # 100 * 0.25 = 25
    assert abs(seg_layer.features.iloc[1]["area"] - 25.0) < 0.1


def test_anisotropic_scale_applied_to_area(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[4:14, 4:14] = 1  # 10x10 = 100 pixels
    viewer = make_napari_viewer()
    seg_layer = viewer.add_labels(seg, name="seg")
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._scale_spins[0].setValue(0.5)  # Y
    widget._scale_spins[1].setValue(1.0)  # X
    widget._run_measurement()
    # 100 * (0.5 * 1.0) = 50; label 1 is at row 1 (row 0 is background).
    assert abs(seg_layer.features.iloc[1]["area"] - 50.0) < 0.1
