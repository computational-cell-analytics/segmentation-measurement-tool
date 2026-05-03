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


def test_scale_default_is_one(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    viewer = make_napari_viewer()
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    assert widget._scale_spin.value() == 1.0


def test_run_measurement_populates_table(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    seg[12:18, 12:18] = 2
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._run_measurement()
    assert widget._measurements is not None
    assert len(widget._measurements) == 2
    assert widget._table.rowCount() == 2


def test_measurement_columns_in_table(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = MorphologyWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._run_measurement()
    headers = [
        widget._table.horizontalHeaderItem(i).text()
        for i in range(widget._table.columnCount())
    ]
    assert "area" in headers
    assert "sphericity" in headers
    assert "solidity" in headers


def test_scale_applied_to_area(make_napari_viewer, qtbot):
    from segmentation_measurement._morphology_widget import MorphologyWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[4:14, 4:14] = 1  # 10x10 = 100 pixels
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")

    widget_default = MorphologyWidget(viewer)
    qtbot.addWidget(widget_default)
    widget_default._seg_combo.setCurrentText("seg")
    widget_default._run_measurement()
    area_default = widget_default._measurements.iloc[0]["area"]

    widget_scaled = MorphologyWidget(viewer)
    qtbot.addWidget(widget_scaled)
    widget_scaled._seg_combo.setCurrentText("seg")
    widget_scaled._scale_spin.setValue(0.5)
    widget_scaled._run_measurement()
    area_scaled = widget_scaled._measurements.iloc[0]["area"]

    assert abs(area_default - 100.0) < 0.1
    assert abs(area_scaled - 25.0) < 0.1
