"""GUI tests for the Group Manager dock widget."""
import os

import numpy as np
import pytest

from segmentation_measurement._groups import (
    ROLE_INTENSITY_IMAGE,
    ROLE_NUCLEUS_SEGMENTATION,
    ROLE_SEGMENTATION,
    get_group,
    list_groups,
    set_group,
)


_IN_CI = os.environ.get("CI") == "true"
_CI_XFAIL = pytest.mark.xfail(
    _IN_CI,
    reason="viewer.add_image() requires an active GL context, unavailable in headless CI",
    strict=False,
)


def _select_layers(viewer, names):
    selection = viewer.layers.selection
    selection.clear()
    for n in names:
        selection.add(viewer.layers[n])


def test_widget_instantiation(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    assert widget is not None


def test_add_selected_appends_segmentation_layers(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_02")
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    _select_layers(viewer, ["cells_01", "cells_02"])
    widget._add_selected(ROLE_SEGMENTATION, labels_only=True)
    assert widget._role_layers_ordered(ROLE_SEGMENTATION) == [
        "cells_01",
        "cells_02",
    ]


def test_add_selected_filters_by_layer_type(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_02")
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    _select_layers(viewer, ["cells_01", "cells_02"])
    # Try to add labels into the intensity-image (image-only) role.
    widget._add_selected(ROLE_INTENSITY_IMAGE, labels_only=False)
    assert widget._role_layers_ordered(ROLE_INTENSITY_IMAGE) == []


def test_add_selected_skips_duplicates(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    _select_layers(viewer, ["cells_01"])
    widget._add_selected(ROLE_SEGMENTATION, labels_only=True)
    widget._add_selected(ROLE_SEGMENTATION, labels_only=True)
    assert widget._role_layers_ordered(ROLE_SEGMENTATION) == ["cells_01"]


def test_remove_drops_selected_entries(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_02")
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    _select_layers(viewer, ["cells_01", "cells_02"])
    widget._add_selected(ROLE_SEGMENTATION, labels_only=True)
    seg_list = widget._role_lists[ROLE_SEGMENTATION]
    seg_list.setCurrentRow(0)
    widget._remove_from(ROLE_SEGMENTATION)
    assert widget._role_layers_ordered(ROLE_SEGMENTATION) == ["cells_02"]


def test_move_up_and_down(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_02")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_03")
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    _select_layers(viewer, ["cells_01", "cells_02", "cells_03"])
    widget._add_selected(ROLE_SEGMENTATION, labels_only=True)
    seg_list = widget._role_lists[ROLE_SEGMENTATION]
    seg_list.setCurrentRow(2)
    widget._move(ROLE_SEGMENTATION, -1)
    assert widget._role_layers_ordered(ROLE_SEGMENTATION) == [
        "cells_01",
        "cells_03",
        "cells_02",
    ]
    widget._move(ROLE_SEGMENTATION, +1)
    assert widget._role_layers_ordered(ROLE_SEGMENTATION) == [
        "cells_01",
        "cells_02",
        "cells_03",
    ]


def test_pairing_preview_reflects_lists(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_02")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="nuclei_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="nuclei_02")
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    _select_layers(viewer, ["cells_01", "cells_02"])
    widget._add_selected(ROLE_SEGMENTATION, labels_only=True)
    _select_layers(viewer, ["nuclei_01", "nuclei_02"])
    widget._add_selected(ROLE_NUCLEUS_SEGMENTATION, labels_only=True)
    table = widget._preview_table
    assert table.rowCount() == 2
    assert table.item(0, 0).text() == "cells_01"
    assert table.item(0, 1).text() == "nuclei_01"
    assert table.item(1, 0).text() == "cells_02"
    assert table.item(1, 1).text() == "nuclei_02"
    assert table.item(0, 2).text() == ""


def test_save_creates_group_with_multiple_segs(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_02")
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    _select_layers(viewer, ["cells_01", "cells_02"])
    widget._add_selected(ROLE_SEGMENTATION, labels_only=True)
    widget._name_edit.setText("exp_1")
    widget._save()
    assert get_group(viewer, "exp_1") == {
        ROLE_SEGMENTATION: ["cells_01", "cells_02"]
    }


def test_save_with_multiple_roles(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_02")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="nuclei_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="nuclei_02")
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    _select_layers(viewer, ["cells_01", "cells_02"])
    widget._add_selected(ROLE_SEGMENTATION, labels_only=True)
    _select_layers(viewer, ["nuclei_01", "nuclei_02"])
    widget._add_selected(ROLE_NUCLEUS_SEGMENTATION, labels_only=True)
    widget._name_edit.setText("exp_1")
    widget._save()
    assert get_group(viewer, "exp_1") == {
        ROLE_SEGMENTATION: ["cells_01", "cells_02"],
        ROLE_NUCLEUS_SEGMENTATION: ["nuclei_01", "nuclei_02"],
    }


def test_save_rejects_length_mismatch(make_napari_viewer, qtbot, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_02")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="nuclei_01")
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    _select_layers(viewer, ["cells_01", "cells_02"])
    widget._add_selected(ROLE_SEGMENTATION, labels_only=True)
    _select_layers(viewer, ["nuclei_01"])
    widget._add_selected(ROLE_NUCLEUS_SEGMENTATION, labels_only=True)
    widget._name_edit.setText("exp_1")
    widget._save()
    assert list_groups(viewer) == []


def test_save_replaces_existing(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_02")
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    widget._name_edit.setText("exp_1")
    seg_list = widget._role_lists[ROLE_SEGMENTATION]
    seg_list.addItem("cells_02")
    widget._save()
    assert get_group(viewer, "exp_1") == {ROLE_SEGMENTATION: ["cells_02"]}


def test_save_rejects_empty_name(make_napari_viewer, qtbot, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    _select_layers(viewer, ["cells_01"])
    widget._add_selected(ROLE_SEGMENTATION, labels_only=True)
    widget._name_edit.setText("")
    widget._save()
    assert list_groups(viewer) == []


def test_save_rejects_missing_segmentation(
    make_napari_viewer, qtbot, monkeypatch
):
    from qtpy.QtWidgets import QMessageBox
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    widget._name_edit.setText("exp_1")
    widget._save()
    assert list_groups(viewer) == []


def test_group_list_refreshes_on_set(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    assert widget._group_list.count() == 1
    assert widget._group_list.item(0).data(0x0100) == "exp_1"


def test_select_group_loads_editor(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_02")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="nuclei_01")
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="nuclei_02")
    set_group(
        viewer,
        "exp_1",
        {
            ROLE_SEGMENTATION: ["cells_01", "cells_02"],
            ROLE_NUCLEUS_SEGMENTATION: ["nuclei_01", "nuclei_02"],
        },
    )
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    widget._group_list.setCurrentRow(0)
    assert widget._name_edit.text() == "exp_1"
    assert widget._role_layers_ordered(ROLE_SEGMENTATION) == [
        "cells_01",
        "cells_02",
    ]
    assert widget._role_layers_ordered(ROLE_NUCLEUS_SEGMENTATION) == [
        "nuclei_01",
        "nuclei_02",
    ]


def test_delete_selected_removes_group(make_napari_viewer, qtbot):
    from segmentation_measurement._groups_widget import GroupManagerWidget
    viewer = make_napari_viewer()
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="cells_01")
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    widget = GroupManagerWidget(viewer)
    qtbot.addWidget(widget)
    widget._group_list.setCurrentRow(0)
    widget._delete_selected()
    assert list_groups(viewer) == []
    assert widget._group_list.count() == 0
