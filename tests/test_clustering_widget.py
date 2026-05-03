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


@pytest.fixture(autouse=True)
def _clear_registry():
    from segmentation_measurement._utils import clear_table_registry
    clear_table_registry()
    yield
    clear_table_registry()


def _register(name, df):
    from segmentation_measurement._utils import register_table
    register_table(name, df)


def _make_df(n=20):
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "label": np.arange(1, n + 1),
        "mean_intensity": rng.uniform(0, 100, n),
        "area": rng.uniform(10, 200, n),
    })


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


def test_refresh_populates_table_combo(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    _register("Intensity (cells)", _make_df())
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    items = [widget._table_combo.itemText(i) for i in range(widget._table_combo.count())]
    assert "Intensity (cells)" in items


def test_select_table_populates_display(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    df = _make_df(10)
    _register("Intensity (cells)", df)
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    widget._table_combo.setCurrentText("Intensity (cells)")
    assert widget._measurements is not None
    assert len(widget._measurements) == 10
    assert widget._table.rowCount() == 10


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
    _register("Morphology (cells)", _make_df())
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    widget._table_combo.setCurrentText("Morphology (cells)")
    widget._embedding = np.zeros((20, 2))
    widget._reduction_combo.setCurrentText("PCA")
    assert widget._embedding is None


def test_cluster_ids_are_one_based(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    df = _make_df(20)
    _register("Intensity (cells)", df)
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    widget._table_combo.setCurrentText("Intensity (cells)")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(3)
    widget._run_clustering()
    ids = widget._measurements["cluster_id"].values
    assert min(ids) == 1
    assert max(ids) == 3


def test_cluster_adds_cluster_id_column(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    df = _make_df(20)
    _register("Intensity (cells)", df)
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    widget._table_combo.setCurrentText("Intensity (cells)")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(3)
    widget._run_clustering()
    assert widget._measurements is not None
    assert "cluster_id" in widget._measurements.columns
    headers = [
        widget._table.horizontalHeaderItem(i).text()
        for i in range(widget._table.columnCount())
    ]
    assert "cluster_id" in headers


def test_cluster_rerun_excludes_cluster_id_from_features(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    df = _make_df(20)
    _register("Intensity (cells)", df)
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    widget._table_combo.setCurrentText("Intensity (cells)")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(2)
    widget._run_clustering()
    widget._kmeans_n_spin.setValue(3)
    widget._run_clustering()
    unique = set(widget._measurements["cluster_id"].unique())
    assert len(unique) == 3


def test_cluster_stores_cluster_ids(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    df = _make_df(20)
    _register("Intensity (cells)", df)
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    widget._table_combo.setCurrentText("Intensity (cells)")
    widget._run_clustering()
    assert widget._cluster_ids is not None
    assert len(widget._cluster_ids) == 20


def test_table_selection_resets_state(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    df = _make_df(20)
    _register("Intensity (cells)", df)
    _register("Morphology (cells)", df)
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    widget._table_combo.setCurrentText("Intensity (cells)")
    widget._run_clustering()
    assert widget._cluster_ids is not None
    widget._table_combo.setCurrentText("Morphology (cells)")
    assert widget._cluster_ids is None
    assert widget._embedding is None


@_CI_XFAIL
def test_cluster_output_label_values_equal_cluster_ids(make_napari_viewer, qtbot):
    """Output segmentation labels == 1-based cluster_id, not cluster_id+1."""
    from segmentation_measurement._clustering_widget import ClusteringWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    seg[10:16, 10:16] = 2
    df = pd.DataFrame({
        "label": [1, 2],
        "mean_intensity": [10.0, 90.0],
        "area": [50.0, 150.0],
    })
    _register("Intensity (seg)", df)
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    widget._table_combo.setCurrentText("Intensity (seg)")
    widget._seg_combo.setCurrentText("seg")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(2)
    widget._out_name.setText("clusters_out")
    widget._run_clustering()
    result = viewer.layers["clusters_out"].data
    # The label values in the output must equal the cluster_ids from the table
    label_to_cid = dict(zip(
        widget._measurements["label"].values,
        widget._measurements["cluster_id"].values,
    ))
    for obj_label, cluster_id in label_to_cid.items():
        mask = seg == int(obj_label)
        expected = int(cluster_id) if int(cluster_id) > 0 else 0
        assert np.all(result[mask] == expected)


@_CI_XFAIL
def test_cluster_colors_applied_to_layer(make_napari_viewer, qtbot):
    """DirectLabelColormap colours should match the scatter plot colours."""
    from napari.utils.colormaps import DirectLabelColormap
    from segmentation_measurement._clustering_widget import ClusteringWidget
    rng = np.random.default_rng(7)
    n = 20
    seg = np.zeros((30, 30), dtype=np.int32)
    for i in range(1, n + 1):
        seg[i, i] = i
    df = pd.DataFrame({
        "label": np.arange(1, n + 1),
        "mean_intensity": rng.uniform(0, 100, n),
        "area": rng.uniform(10, 200, n),
    })
    _register("Intensity (seg)", df)
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    widget._table_combo.setCurrentText("Intensity (seg)")
    widget._seg_combo.setCurrentText("seg")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(3)
    widget._out_name.setText("clusters_col")
    widget._run_clustering()
    layer = viewer.layers["clusters_col"]
    assert isinstance(layer.colormap, DirectLabelColormap)
    # Each non-noise cluster label must have the same colour in the layer and scatter
    for cid, scatter_rgba in widget._cluster_colors.items():
        if cid <= 0:
            continue
        layer_rgba = layer.get_color(cid)
        np.testing.assert_allclose(layer_rgba, np.array(scatter_rgba), atol=1e-6)


@_CI_XFAIL
def test_cluster_creates_output_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    rng = np.random.default_rng(0)
    n = 20
    seg = np.zeros((30, 30), dtype=np.int32)
    for i in range(1, n + 1):
        seg[i, i] = i
    labels = np.arange(1, n + 1)
    df = pd.DataFrame({
        "label": labels,
        "mean_intensity": rng.uniform(0, 100, n),
        "area": rng.uniform(10, 200, n),
    })
    _register("Intensity (seg)", df)
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    widget._table_combo.setCurrentText("Intensity (seg)")
    widget._seg_combo.setCurrentText("seg")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(2)
    widget._out_name.setText("my_clusters")
    widget._run_clustering()
    layer_names = [layer.name for layer in viewer.layers]
    assert "my_clusters" in layer_names
    result = viewer.layers["my_clusters"].data
    # background stays 0
    assert result[0, 0] == 0
    # labelled pixels are non-zero
    assert np.any(result > 0)


@_CI_XFAIL
def test_cluster_updates_existing_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    rng = np.random.default_rng(1)
    n = 20
    seg = np.zeros((30, 30), dtype=np.int32)
    for i in range(1, n + 1):
        seg[i, i] = i
    df = pd.DataFrame({
        "label": np.arange(1, n + 1),
        "mean_intensity": rng.uniform(0, 100, n),
        "area": rng.uniform(10, 200, n),
    })
    _register("Intensity (seg)", df)
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    widget._table_combo.setCurrentText("Intensity (seg)")
    widget._seg_combo.setCurrentText("seg")
    widget._kmeans_n_spin.setValue(3)
    widget._out_name.setText("clust")
    widget._run_clustering()
    n_layers = len(viewer.layers)
    widget._run_clustering()
    assert len(viewer.layers) == n_layers


def test_works_with_morphology_table(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    df = pd.DataFrame({
        "label": np.arange(1, 21),
        "area": np.linspace(10, 200, 20),
        "sphericity": np.linspace(0.5, 1.0, 20),
    })
    _register("Morphology (cells)", df)
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    widget._table_combo.setCurrentText("Morphology (cells)")
    widget._method_combo.setCurrentText("K-Means")
    widget._kmeans_n_spin.setValue(2)
    widget._run_clustering()
    assert "cluster_id" in widget._measurements.columns


def test_multiple_tables_in_combo(make_napari_viewer, qtbot):
    from segmentation_measurement._clustering_widget import ClusteringWidget
    _register("Intensity (cells)", pd.DataFrame({"label": [1], "mean_intensity": [5.0]}))
    _register("Morphology (cells)", pd.DataFrame({"label": [1], "area": [100.0]}))
    viewer = make_napari_viewer()
    widget = ClusteringWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_table_combo()
    items = [widget._table_combo.itemText(i) for i in range(widget._table_combo.count())]
    assert "Intensity (cells)" in items
    assert "Morphology (cells)" in items
