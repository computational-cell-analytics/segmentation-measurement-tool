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


def test_target_combo_lists_groups(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    from segmentation_measurement._groups import (
        ROLE_NUCLEUS_SEGMENTATION,
        ROLE_SEGMENTATION,
        set_group,
    )
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="nuclei_01")
    widget = CellNucleusWidget(viewer)
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
            ROLE_NUCLEUS_SEGMENTATION: ["nuclei_01"],
        },
    )
    assert "exp_1" in items()
    assert widget._target_combo.currentText() == "exp_1"


@_CI_XFAIL
def test_group_mode_iterates_triples(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    from segmentation_measurement._groups import (
        ROLE_NUCLEUS_SEGMENTATION,
        ROLE_SEGMENTATION,
        set_group,
    )
    cell1, nuc1 = _make_cell_nuc_seg_2d()
    cell2, nuc2 = _make_cell_nuc_seg_2d()
    viewer = make_napari_viewer()
    cell_layer1 = viewer.add_labels(cell1, name="cells_01")
    cell_layer2 = viewer.add_labels(cell2, name="cells_02")
    viewer.add_labels(nuc1, name="nuclei_01")
    viewer.add_labels(nuc2, name="nuclei_02")
    set_group(
        viewer,
        "exp_1",
        {
            ROLE_SEGMENTATION: ["cells_01", "cells_02"],
            ROLE_NUCLEUS_SEGMENTATION: ["nuclei_01", "nuclei_02"],
        },
    )
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    assert not widget._cell_combo.isEnabled()
    assert not widget._nuc_combo.isEnabled()
    widget._run_measurement()
    assert "n_nuclei" in cell_layer1.features.columns
    assert "n_nuclei" in cell_layer2.features.columns


def test_group_mode_without_nucleus_role_raises(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=np.int32), name="cells_01")
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    with pytest.raises(ValueError, match="no nucleus segmentation"):
        widget._run_measurement()


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
    cells_layer = viewer.add_labels(cell_seg, name="cells")
    viewer.add_labels(nuc_seg, name="nuclei")
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    widget._cell_combo.setCurrentText("cells")
    widget._nuc_combo.setCurrentText("nuclei")
    widget._run_measurement()
    feats = cells_layer.features
    assert "index" in feats.columns
    assert "n_nuclei" in feats.columns
    assert "cell_area" in feats.columns
    # Padded so row position == label value; drop the background NaN row.
    real = feats.dropna(subset=["cell_area"])
    assert len(real) == 2


@_CI_XFAIL
def test_run_measurement_with_intensity(make_napari_viewer, qtbot):
    from segmentation_measurement._cell_nucleus_widget import CellNucleusWidget
    cell_seg, nuc_seg = _make_cell_nuc_seg_2d()
    intensity = np.ones((30, 30), dtype=np.float32) * 5.0
    viewer = make_napari_viewer()
    cells_layer = viewer.add_labels(cell_seg, name="cells")
    viewer.add_labels(nuc_seg, name="nuclei")
    viewer.add_image(intensity, name="img")
    widget = CellNucleusWidget(viewer)
    qtbot.addWidget(widget)
    widget._cell_combo.setCurrentText("cells")
    widget._nuc_combo.setCurrentText("nuclei")
    widget._img_combo.setCurrentText("img")
    widget._run_measurement()
    feats = cells_layer.features
    assert "cell_mean_intensity" in feats.columns
    assert "mean_intensity_ratio" in feats.columns
