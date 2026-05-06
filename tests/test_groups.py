"""Tests for the groups storage API and concat/split helpers."""
import numpy as np
import pandas as pd
import pytest

from segmentation_measurement._groups import (
    ROLE_INTENSITY_IMAGE,
    ROLE_NUCLEUS_SEGMENTATION,
    ROLE_SEGMENTATION,
    delete_group,
    get_group,
    list_groups,
    set_group,
    subscribe,
)
from segmentation_measurement._layer_features import (
    concat_features_for_group,
    merge_features_into_layer,
    split_and_merge_back,
)


def _add_label_layer(viewer, name, features=None):
    layer = viewer.add_labels(np.zeros((4, 4), dtype=int), name=name)
    if features is not None:
        merge_features_into_layer(layer, features)
    return layer


# --------------------------------------------------------------- API ---


def test_set_and_get_group(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    _add_label_layer(viewer, "cells_02")
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]})
    assert list_groups(viewer) == ["exp_1"]
    assert get_group(viewer, "exp_1") == {
        ROLE_SEGMENTATION: ["cells_01", "cells_02"]
    }


def test_get_returns_deep_copy(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    fetched = get_group(viewer, "exp_1")
    fetched[ROLE_SEGMENTATION].append("tampered")
    assert get_group(viewer, "exp_1")[ROLE_SEGMENTATION] == ["cells_01"]


def test_get_unknown_group_raises(make_napari_viewer):
    viewer = make_napari_viewer()
    with pytest.raises(KeyError):
        get_group(viewer, "nope")


def test_set_group_validates_required_role(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "nuclei_01")
    with pytest.raises(ValueError, match="Missing required role"):
        set_group(viewer, "exp_1", {ROLE_NUCLEUS_SEGMENTATION: ["nuclei_01"]})


def test_set_group_rejects_empty_segmentation_list(make_napari_viewer):
    viewer = make_napari_viewer()
    with pytest.raises(ValueError, match="at least one segmentation"):
        set_group(viewer, "exp_1", {ROLE_SEGMENTATION: []})


def test_set_group_rejects_unknown_role(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    with pytest.raises(ValueError, match="Unknown role"):
        set_group(
            viewer,
            "exp_1",
            {ROLE_SEGMENTATION: ["cells_01"], "garbage": ["cells_01"]},
        )


def test_set_group_rejects_missing_layer(make_napari_viewer):
    viewer = make_napari_viewer()
    with pytest.raises(ValueError, match="not in the viewer"):
        set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["ghost"]})


def test_set_group_rejects_empty_name(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    with pytest.raises(ValueError, match="non-empty"):
        set_group(viewer, "", {ROLE_SEGMENTATION: ["cells_01"]})


def test_set_group_rejects_non_list_role(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    with pytest.raises(ValueError, match="must map to a list"):
        set_group(viewer, "exp_1", {ROLE_SEGMENTATION: "cells_01"})


def test_set_group_rejects_duplicate_within_role(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    with pytest.raises(ValueError, match="duplicate entries"):
        set_group(
            viewer,
            "exp_1",
            {ROLE_SEGMENTATION: ["cells_01", "cells_01"]},
        )


def test_set_group_validates_role_length_match(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    _add_label_layer(viewer, "cells_02")
    _add_label_layer(viewer, "nuclei_01")
    with pytest.raises(ValueError, match="must be empty or match"):
        set_group(
            viewer,
            "exp_1",
            {
                ROLE_SEGMENTATION: ["cells_01", "cells_02"],
                ROLE_NUCLEUS_SEGMENTATION: ["nuclei_01"],
            },
        )


def test_set_group_allows_optional_role_omitted(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    _add_label_layer(viewer, "cells_02")
    set_group(
        viewer,
        "exp_1",
        {ROLE_SEGMENTATION: ["cells_01", "cells_02"]},
    )
    assert get_group(viewer, "exp_1") == {
        ROLE_SEGMENTATION: ["cells_01", "cells_02"]
    }


def test_set_group_allows_optional_role_empty_list(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    _add_label_layer(viewer, "cells_02")
    set_group(
        viewer,
        "exp_1",
        {
            ROLE_SEGMENTATION: ["cells_01", "cells_02"],
            ROLE_NUCLEUS_SEGMENTATION: [],
        },
    )
    assert get_group(viewer, "exp_1") == {
        ROLE_SEGMENTATION: ["cells_01", "cells_02"],
        ROLE_NUCLEUS_SEGMENTATION: [],
    }


def test_set_group_replaces_existing(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    _add_label_layer(viewer, "cells_02")
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_02"]})
    assert get_group(viewer, "exp_1") == {ROLE_SEGMENTATION: ["cells_02"]}


def test_delete_group(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    delete_group(viewer, "exp_1")
    assert list_groups(viewer) == []
    delete_group(viewer, "exp_1")  # idempotent — must not raise


# ------------------------------------------------------------- Rename ---


def test_rename_existing_layer_updates_group(make_napari_viewer):
    viewer = make_napari_viewer()
    layer = _add_label_layer(viewer, "cells_01")
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    layer.name = "cells_renamed"
    assert get_group(viewer, "exp_1") == {ROLE_SEGMENTATION: ["cells_renamed"]}


def test_rename_within_multi_layer_role(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    layer2 = _add_label_layer(viewer, "cells_02")
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    layer2.name = "cells_v2"
    assert get_group(viewer, "exp_1") == {
        ROLE_SEGMENTATION: ["cells_01", "cells_v2"]
    }


def test_rename_layer_added_after_listener(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    new_layer = _add_label_layer(viewer, "cells_02")
    set_group(viewer, "exp_2", {ROLE_SEGMENTATION: ["cells_02"]})
    new_layer.name = "cells_v2"
    assert get_group(viewer, "exp_2") == {ROLE_SEGMENTATION: ["cells_v2"]}


def test_rename_updates_across_roles(make_napari_viewer):
    viewer = make_napari_viewer()
    cells = _add_label_layer(viewer, "cells_01")
    nuclei = _add_label_layer(viewer, "nuclei_01")
    set_group(
        viewer,
        "exp_1",
        {
            ROLE_SEGMENTATION: ["cells_01"],
            ROLE_NUCLEUS_SEGMENTATION: ["nuclei_01"],
        },
    )
    cells.name = "cells_v2"
    nuclei.name = "nuclei_v2"
    assert get_group(viewer, "exp_1") == {
        ROLE_SEGMENTATION: ["cells_v2"],
        ROLE_NUCLEUS_SEGMENTATION: ["nuclei_v2"],
    }


# ----------------------------------------------------------- Subscribe ---


def test_subscribe_fires_on_set_and_delete(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    calls = []
    unsubscribe = subscribe(viewer, lambda: calls.append("ping"))
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    delete_group(viewer, "exp_1")
    assert calls == ["ping", "ping"]
    unsubscribe()
    set_group(viewer, "exp_2", {ROLE_SEGMENTATION: ["cells_01"]})
    assert calls == ["ping", "ping"]


# ------------------------------------------------------- Concat / split ---


def test_concat_features_for_group_round_trip(make_napari_viewer):
    viewer = make_napari_viewer()
    df1 = pd.DataFrame({"index": [0, 1, 2], "value": [10.0, 20.0, 30.0]})
    df2 = pd.DataFrame({"index": [0, 1], "value": [40.0, 50.0]})
    _add_label_layer(viewer, "cells_01", df1)
    _add_label_layer(viewer, "cells_02", df2)
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )

    df = concat_features_for_group(viewer, "exp_1")
    assert "_source_layer" in df.columns
    assert set(df["_source_layer"].unique()) == {"cells_01", "cells_02"}

    df["cluster_id"] = np.arange(len(df))
    split_and_merge_back(viewer, df, ["cluster_id"])
    assert "cluster_id" in viewer.layers["cells_01"].features.columns
    assert "cluster_id" in viewer.layers["cells_02"].features.columns
    assert "value" in viewer.layers["cells_01"].features.columns


def test_concat_for_group_raises_on_unknown_group(make_napari_viewer):
    viewer = make_napari_viewer()
    with pytest.raises(KeyError):
        concat_features_for_group(viewer, "nope")


def test_concat_for_group_raises_on_empty_role(make_napari_viewer):
    viewer = make_napari_viewer()
    df = pd.DataFrame({"index": [0, 1], "value": [1.0, 2.0]})
    _add_label_layer(viewer, "cells_01", df)
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    with pytest.raises(ValueError, match="no layers under role"):
        concat_features_for_group(
            viewer, "exp_1", role=ROLE_INTENSITY_IMAGE
        )


def test_concat_for_group_raises_on_column_mismatch(make_napari_viewer):
    viewer = make_napari_viewer()
    df1 = pd.DataFrame({"index": [0, 1], "intensity": [1.0, 2.0]})
    df2 = pd.DataFrame({"index": [0, 1], "area": [100.0, 200.0]})
    _add_label_layer(viewer, "cells_01", df1)
    _add_label_layer(viewer, "cells_02", df2)
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    with pytest.raises(ValueError, match="Feature columns"):
        concat_features_for_group(viewer, "exp_1")


def test_concat_for_group_raises_on_missing_features(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    with pytest.raises(ValueError, match="has no features"):
        concat_features_for_group(viewer, "exp_1")


def test_split_and_merge_back_validates_columns(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    df = pd.DataFrame(
        {"index": [0, 1], "_source_layer": ["cells_01", "cells_01"]}
    )
    with pytest.raises(ValueError, match="missing requested column"):
        split_and_merge_back(viewer, df, ["nope"])


def test_split_and_merge_back_requires_index_and_source(make_napari_viewer):
    viewer = make_napari_viewer()
    _add_label_layer(viewer, "cells_01")
    with pytest.raises(ValueError, match="_source_layer"):
        split_and_merge_back(viewer, pd.DataFrame({"index": [0]}), [])
    with pytest.raises(ValueError, match="index"):
        split_and_merge_back(
            viewer, pd.DataFrame({"_source_layer": ["cells_01"]}), []
        )


def test_split_raises_on_unknown_layer(make_napari_viewer):
    viewer = make_napari_viewer()
    df = pd.DataFrame(
        {"index": [0], "_source_layer": ["ghost"], "cluster_id": [1]}
    )
    with pytest.raises(KeyError, match="not in the viewer"):
        split_and_merge_back(viewer, df, ["cluster_id"])
