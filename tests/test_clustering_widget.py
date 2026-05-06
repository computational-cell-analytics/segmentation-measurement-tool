"""GUI tests for the napari clustering analysis widget."""

import os

import numpy as np
import pandas as pd
import pytest

_IN_CI = os.environ.get("CI") == "true"
_CI_XFAIL = pytest.mark.xfail(
    _IN_CI,
    reason="viewer.add_labels() may require an active GL context in headless CI",
    strict=False,
)


def _make_seg_with_features(viewer, n=20, features=None, name="seg"):
    """Create a layer with `n` discrete pixels labelled 1..n and attach features."""
    seg = np.zeros((30, 30), dtype=np.int32)
    for i in range(1, n + 1):
        seg[i % 30, i // 30 if (i // 30) > 0 else (i % 30)] = i
        # ensure each label has at least one pixel by placing on a diagonal
        seg[i % 30, (i + 5) % 30] = i
    if features is None:
        rng = np.random.default_rng(42)
        features = pd.DataFrame({
            "index": np.arange(1, n + 1),
            "mean_intensity": rng.uniform(0, 100, n),
            "area": rng.uniform(10, 200, n),
        })
    layer = viewer.add_labels(seg, name=name)
    layer.features = features
    return layer


def test_widget_instantiation(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    assert widget is not None


def test_seg_combo_populated_on_labels_add(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg")
    items = [widget._seg_combo.itemText(i) for i in range(widget._seg_combo.count())]
    assert "seg" in items


def test_method_combo_switches_params_stack(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    for i, method in enumerate(["K-Means", "DBSCAN", "HDBSCAN", "Mean Shift"]):
        widget._method_combo.setCurrentText(method)
        assert widget._params_stack.currentIndex() == i


def test_reduction_method_change_clears_embedding(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, name="seg")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._embedding = np.zeros((20, 2))
    widget._reduction_combo.setCurrentText("PCA")
    assert widget._embedding is None


def test_seg_selection_resets_state(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, name="seg_a")
    _make_seg_with_features(viewer, name="seg_b")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg_a")
    widget._run_clustering()
    assert widget._cluster_ids is not None
    widget._seg_combo.setCurrentText("seg_b")
    assert widget._cluster_ids is None
    assert widget._embedding is None


def test_cluster_ids_are_one_based(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    viewer = make_napari_viewer()
    layer = _make_seg_with_features(viewer, n=20, name="seg")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(3)
    widget._run_clustering()
    # Skip the background row (label 0); cluster_measurements assigns -1 to
    # rows whose features are all NaN.
    feats = layer.features
    ids = feats.loc[feats["index"] > 0, "cluster_id"].values
    assert min(ids) == 1
    assert max(ids) == 3


def test_cluster_writes_back_to_source_features(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    viewer = make_napari_viewer()
    layer = _make_seg_with_features(viewer, n=20, name="seg")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(3)
    widget._run_clustering()
    feats = layer.features
    assert "cluster_id" in feats.columns


def test_cluster_rerun_excludes_cluster_id_from_features(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    viewer = make_napari_viewer()
    layer = _make_seg_with_features(viewer, n=20, name="seg")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(2)
    widget._run_clustering()
    widget._kmeans_n_spin.setValue(3)
    widget._run_clustering()
    feats = layer.features
    unique = set(feats.loc[feats["index"] > 0, "cluster_id"].unique())
    assert len(unique) == 3


@_CI_XFAIL
def test_cluster_creates_output_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, n=20, name="seg")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(2)
    widget._out_name.setText("my_clusters")
    widget._run_clustering()
    layer_names = [layer.name for layer in viewer.layers]
    assert "my_clusters" in layer_names


@_CI_XFAIL
def test_cluster_updates_existing_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, n=20, name="seg")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._kmeans_n_spin.setValue(3)
    widget._out_name.setText("clust")
    widget._run_clustering()
    n_layers = len(viewer.layers)
    widget._run_clustering()
    assert len(viewer.layers) == n_layers


def test_target_combo_lists_groups(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, n=10, name="cells_01")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    items = lambda: [
        widget._target_combo.itemText(i)
        for i in range(widget._target_combo.count())
    ]
    assert items() == ["<single layer>"]
    set_group(viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01"]})
    assert "exp_1" in items()
    assert widget._target_combo.currentText() == "exp_1"


@_CI_XFAIL
def test_group_mode_concat_features(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    viewer = make_napari_viewer()
    _make_seg_with_features(viewer, n=20, name="cells_01")
    _make_seg_with_features(viewer, n=20, name="cells_02")
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    feats = widget._current_features()
    assert feats is not None
    assert "_source_layer" in feats.columns
    assert set(feats["_source_layer"].unique()) == {"cells_01", "cells_02"}


@_CI_XFAIL
def test_group_mode_writes_back_per_layer(make_napari_viewer, qtbot):
    from napari.layers.utils._link_layers import get_linked_layers
    from segmentation_measurement._clustering_widget import ClusteringWidget
    from segmentation_measurement._groups import ROLE_SEGMENTATION, set_group
    viewer = make_napari_viewer()
    layer1 = _make_seg_with_features(viewer, n=20, name="cells_01")
    layer2 = _make_seg_with_features(viewer, n=20, name="cells_02")
    layer1.translate = (0.0, 0.0)
    layer2.translate = (0.0, 30.0)
    set_group(
        viewer, "exp_1", {ROLE_SEGMENTATION: ["cells_01", "cells_02"]}
    )
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._target_combo.setCurrentText("exp_1")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(2)
    widget._out_name.setText("clust")
    widget._run_clustering()
    assert "cluster_id" in layer1.features.columns
    assert "cluster_id" in layer2.features.columns
    layer_names = [layer.name for layer in viewer.layers]
    assert "clust_cells_01" in layer_names
    assert "clust_cells_02" in layer_names
    assert tuple(viewer.layers["clust_cells_01"].translate) == (0.0, 0.0)
    assert tuple(viewer.layers["clust_cells_02"].translate) == (0.0, 30.0)
    assert viewer.layers["clust_cells_02"] in get_linked_layers(
        viewer.layers["clust_cells_01"]
    )


def test_works_with_morphology_features(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    df = pd.DataFrame({
        "index": np.arange(1, 21),
        "area": np.linspace(10, 200, 20),
        "sphericity": np.linspace(0.5, 1.0, 20),
    })
    viewer = make_napari_viewer()
    layer = _make_seg_with_features(viewer, n=20, features=df, name="seg")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(2)
    widget._run_clustering()
    assert "cluster_id" in layer.features.columns
