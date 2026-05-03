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
def test_run_measurement_populates_table(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    intensity = np.ones((20, 20), dtype=np.float32) * 5.0
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    viewer.add_image(intensity, name="img")
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._img_combo.setCurrentText("img")
    widget._run_measurement()
    assert widget._measurements is not None
    assert len(widget._measurements) == 1
    assert widget._table.rowCount() == 1


@_CI_XFAIL
def test_measurement_columns_in_table(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    intensity = np.ones((20, 20), dtype=np.float32)
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    viewer.add_image(intensity, name="img")
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._img_combo.setCurrentText("img")
    widget._run_measurement()
    headers = [
        widget._table.horizontalHeaderItem(i).text()
        for i in range(widget._table.columnCount())
    ]
    assert "mean_intensity" in headers
    assert "label" in headers
