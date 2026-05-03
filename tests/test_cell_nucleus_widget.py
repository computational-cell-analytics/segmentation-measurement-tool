"""GUI tests for the napari cell-nucleus measurement widget."""
import os

import numpy as np
import pytest

_IN_CI = os.environ.get("CI") == "true"
_CI_XFAIL = pytest.mark.xfail(
    _IN_CI,
    reason="viewer.add_labels() may require an active GL context in headless CI",
    strict=False,
)


def _make_cell_nuc_seg_2d():
    cell_seg = np.zeros((30, 30), dtype=np.int32)
    cell_seg[2:14, 2:14] = 1
    cell_seg[16:26, 16:26] = 2
    nuc_seg = np.zeros((30, 30), dtype=np.int32)
    nuc_seg[5:10, 5:10] = 1
    return cell_seg, nuc_seg


def test_widget_instantiation(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    viewer = make_napari_viewer()
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    assert widget is not None


def test_combos_populated_on_labels_add(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    viewer = make_napari_viewer()
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells")
    cell_items = [widget._cell_combo.itemText(i) for i in range(widget._cell_combo.count())]
    nuc_items = [widget._nuc_combo.itemText(i) for i in range(widget._nuc_combo.count())]
    assert "cells" in cell_items
    assert "cells" in nuc_items


def test_default_shows_two_scale_spinboxes(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    viewer = make_napari_viewer()
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    assert len(widget._scale_spins) == 2


def test_default_scale_is_one(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    viewer = make_napari_viewer()
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    assert all(abs(s.value() - 1.0) < 1e-9 for s in widget._scale_spins)


def test_3d_seg_shows_three_spinboxes(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((5, 10, 10), dtype=int), name="cells3d")
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    widget._cell_combo.setCurrentText("cells3d")
    assert len(widget._scale_spins) == 3


def test_layer_scale_populates_spinboxes(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells", scale=[0.5, 0.25])
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    widget._cell_combo.setCurrentText("cells")
    assert abs(widget._scale_spins[0].value() - 0.5) < 1e-6
    assert abs(widget._scale_spins[1].value() - 0.25) < 1e-6


def test_img_combo_has_none_option(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget, _NO_IMAGE
    viewer = make_napari_viewer()
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    items = [widget._img_combo.itemText(i) for i in range(widget._img_combo.count())]
    assert _NO_IMAGE in items


def test_run_measurement_no_intensity(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    cell_seg, nuc_seg = _make_cell_nuc_seg_2d()
    viewer = make_napari_viewer()
    viewer.add_labels(cell_seg, name="cells")
    viewer.add_labels(nuc_seg, name="nuclei")
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    widget._cell_combo.setCurrentText("cells")
    widget._nuc_combo.setCurrentText("nuclei")
    widget._run_measurement()
    assert widget._measurements is not None
    assert len(widget._measurements) == 2
    assert widget._table.rowCount() == 2
    assert "n_nuclei" in widget._measurements.columns
    assert "cell_area" in widget._measurements.columns


def test_run_measurement_with_intensity(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    cell_seg, nuc_seg = _make_cell_nuc_seg_2d()
    intensity = np.ones((30, 30), dtype=np.float32) * 5.0
    viewer = make_napari_viewer()
    viewer.add_labels(cell_seg, name="cells")
    viewer.add_labels(nuc_seg, name="nuclei")
    viewer.add_image(intensity, name="img")
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    widget._cell_combo.setCurrentText("cells")
    widget._nuc_combo.setCurrentText("nuclei")
    widget._img_combo.setCurrentText("img")
    widget._run_measurement()
    assert widget._measurements is not None
    assert "cell_mean_intensity" in widget._measurements.columns
    assert "mean_intensity_ratio" in widget._measurements.columns


def test_table_columns_populated(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    cell_seg, nuc_seg = _make_cell_nuc_seg_2d()
    viewer = make_napari_viewer()
    viewer.add_labels(cell_seg, name="cells")
    viewer.add_labels(nuc_seg, name="nuclei")
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    widget._cell_combo.setCurrentText("cells")
    widget._nuc_combo.setCurrentText("nuclei")
    widget._run_measurement()
    headers = [
        widget._table.horizontalHeaderItem(i).text()
        for i in range(widget._table.columnCount())
    ]
    assert "n_nuclei" in headers
    assert "cell_area" in headers
    assert "area_ratio" in headers
