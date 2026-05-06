"""Tests for the napari-opening CLI command."""

from argparse import Namespace

import numpy as np
import pytest
import tifffile


def test_expand_open_paths_recursive_names_relative_to_glob_root(tmp_path):
    from segmentation_measurement._cli import _expand_open_paths

    root = tmp_path / "data"
    path_a = root / "well_a" / "seg.tif"
    path_b = root / "well_b" / "seg.tif"
    path_a.parent.mkdir(parents=True)
    path_b.parent.mkdir(parents=True)
    tifffile.imwrite(path_a, np.zeros((4, 4), dtype=np.uint16))
    tifffile.imwrite(path_b, np.zeros((4, 4), dtype=np.uint16))

    paths = _expand_open_paths([str(root / "**" / "seg.tif")], "segmentation")

    assert [item.path for item in paths] == [path_a, path_b]
    assert [item.layer_name for item in paths] == ["well_a/seg", "well_b/seg"]


def test_expand_open_paths_raises_for_unmatched_glob(tmp_path):
    from segmentation_measurement._cli import _expand_open_paths

    with pytest.raises(ValueError, match="No files matched segmentation"):
        _expand_open_paths([str(tmp_path / "**" / "missing.tif")], "segmentation")


def test_validate_open_path_counts_raises_for_mismatch(tmp_path):
    from segmentation_measurement._cli import (
        _OpenPath,
        _validate_open_path_counts,
    )

    segs = [
        _OpenPath(tmp_path / "seg_1.tif", "seg_1"),
        _OpenPath(tmp_path / "seg_2.tif", "seg_2"),
    ]
    intensities = [_OpenPath(tmp_path / "raw_1.tif", "raw_1")]

    with pytest.raises(ValueError, match="Expected 2 intensity image path"):
        _validate_open_path_counts(segs, intensities, None)


def test_open_command_creates_group_and_grid(
    tmp_path, make_napari_viewer, qtbot, monkeypatch
):
    import napari
    from segmentation_measurement._cli import cmd_open
    from segmentation_measurement._groups import (
        ROLE_INTENSITY_IMAGE,
        ROLE_SEGMENTATION,
        get_group,
    )

    seg_1 = tmp_path / "seg_1.tif"
    seg_2 = tmp_path / "seg_2.tif"
    raw_1 = tmp_path / "raw_1.tif"
    raw_2 = tmp_path / "raw_2.tif"
    tifffile.imwrite(seg_1, np.zeros((5, 5), dtype=np.uint16))
    tifffile.imwrite(seg_2, np.zeros((5, 5), dtype=np.uint16))
    tifffile.imwrite(raw_1, np.zeros((5, 5), dtype=np.float32))
    tifffile.imwrite(raw_2, np.zeros((5, 5), dtype=np.float32))

    viewer = make_napari_viewer()
    monkeypatch.setattr(napari, "Viewer", lambda: viewer)
    monkeypatch.setattr(napari, "run", lambda: None)

    cmd_open(Namespace(
        segmentations=[str(tmp_path / "seg_*.tif")],
        intensities=[str(tmp_path / "raw_*.tif")],
        nuclei=None,
        no_group=False,
        no_grid=False,
        group_name="exp_1",
    ))

    qtbot.wait(1)
    assert get_group(viewer, "exp_1") == {
        ROLE_SEGMENTATION: ["seg_1", "seg_2"],
        ROLE_INTENSITY_IMAGE: ["raw_1", "raw_2"],
    }
    assert tuple(viewer.layers["seg_1"].translate) == (0.0, 0.0)
    assert tuple(viewer.layers["raw_1"].translate) == (0.0, 0.0)
    assert tuple(viewer.layers["seg_2"].translate) == (0.0, 5.0)
    assert tuple(viewer.layers["raw_2"].translate) == (0.0, 5.0)


def test_open_command_no_group_skips_group_creation(
    tmp_path, make_napari_viewer, monkeypatch
):
    import napari
    from segmentation_measurement._cli import cmd_open
    from segmentation_measurement._groups import list_groups

    seg_1 = tmp_path / "seg_1.tif"
    seg_2 = tmp_path / "seg_2.tif"
    tifffile.imwrite(seg_1, np.zeros((5, 5), dtype=np.uint16))
    tifffile.imwrite(seg_2, np.zeros((5, 5), dtype=np.uint16))

    viewer = make_napari_viewer()
    monkeypatch.setattr(napari, "Viewer", lambda: viewer)
    monkeypatch.setattr(napari, "run", lambda: None)

    cmd_open(Namespace(
        segmentations=[str(tmp_path / "seg_*.tif")],
        intensities=None,
        nuclei=None,
        no_group=True,
        no_grid=False,
        group_name="exp_1",
    ))

    assert list_groups(viewer) == []
