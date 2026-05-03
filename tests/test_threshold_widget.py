"""GUI tests for the napari threshold analysis widget."""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

_IN_CI = os.environ.get("CI") == "true"
_CI_XFAIL = pytest.mark.xfail(
    _IN_CI,
    reason="viewer.add_labels() may require an active GL context in headless CI",
    strict=False,
)


def _write_csv(tmpdir, df, filename="measurements.csv"):
    path = os.path.join(tmpdir, filename)
    df.to_csv(path, index=False)
    return path


def test_widget_instantiation(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    viewer = make_napari_viewer()
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    assert widget is not None


def test_seg_combo_populated_on_labels_add(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    viewer = make_napari_viewer()
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg")
    items = [widget._seg_combo.itemText(i) for i in range(widget._seg_combo.count())]
    assert "seg" in items


def test_load_table_populates_table_widget(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    df = pd.DataFrame({
        "label": [1, 2, 3],
        "mean_intensity": [10.0, 50.0, 90.0],
    })
    viewer = make_napari_viewer()
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_csv(tmpdir, df)
        widget._path_edit.setText(path)
        widget._load_table()
    assert widget._measurements is not None
    assert len(widget._measurements) == 3
    assert widget._table.rowCount() == 3


def test_load_table_populates_col_combo(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    df = pd.DataFrame({
        "label": [1, 2],
        "mean_intensity": [10.0, 90.0],
        "area": [100.0, 200.0],
    })
    viewer = make_napari_viewer()
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_csv(tmpdir, df)
        widget._path_edit.setText(path)
        widget._load_table()
    cols = [widget._col_combo.itemText(i) for i in range(widget._col_combo.count())]
    assert "mean_intensity" in cols
    assert "area" in cols
    assert "label" not in cols


def test_suggest_thresholds_sets_spinbox_values(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    df = pd.DataFrame({
        "label": [1, 2, 3, 4],
        "mean_intensity": [10.0, 30.0, 70.0, 90.0],
    })
    viewer = make_napari_viewer()
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_csv(tmpdir, df)
        widget._path_edit.setText(path)
        widget._load_table()
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("mean_intensity")
    widget._suggest_thresholds()
    assert len(widget._threshold_spins) == 1
    assert widget._threshold_spins[0].value() > 0.0


def test_n_categories_rebuilds_widgets(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    viewer = make_napari_viewer()
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    widget._n_spin.setValue(4)
    assert len(widget._threshold_spins) == 3
    assert len(widget._name_edits) == 4


@_CI_XFAIL
def test_categorize_creates_output_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    seg[12:18, 12:18] = 2
    df = pd.DataFrame({
        "label": [1, 2],
        "mean_intensity": [10.0, 90.0],
    })
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_csv(tmpdir, df)
        widget._path_edit.setText(path)
        widget._load_table()
    widget._seg_combo.setCurrentText("seg")
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("mean_intensity")
    widget._threshold_spins[0].setValue(50.0)
    widget._out_name.setText("my_categories")
    widget._run_categorization()
    layer_names = [layer.name for layer in viewer.layers]
    assert "my_categories" in layer_names
    result = viewer.layers["my_categories"].data
    assert np.all(result[2:8, 2:8] == 1)
    assert np.all(result[12:18, 12:18] == 2)


@_CI_XFAIL
def test_categorize_adds_category_columns_to_table(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    df = pd.DataFrame({
        "label": [1],
        "mean_intensity": [10.0],
    })
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_csv(tmpdir, df)
        widget._path_edit.setText(path)
        widget._load_table()
    widget._seg_combo.setCurrentText("seg")
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("mean_intensity")
    widget._threshold_spins[0].setValue(50.0)
    widget._run_categorization()
    headers = [
        widget._table.horizontalHeaderItem(i).text()
        for i in range(widget._table.columnCount())
    ]
    assert "category_id" in headers
    assert "category_name" in headers


@_CI_XFAIL
def test_categorize_updates_existing_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._threshold_widget import ThresholdWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    df = pd.DataFrame({"label": [1], "mean_intensity": [10.0]})
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_csv(tmpdir, df)
        widget._path_edit.setText(path)
        widget._load_table()
    widget._seg_combo.setCurrentText("seg")
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("mean_intensity")
    widget._threshold_spins[0].setValue(50.0)
    widget._out_name.setText("cats")
    widget._run_categorization()
    n_layers = len(viewer.layers)
    widget._run_categorization()
    assert len(viewer.layers) == n_layers


def test_works_with_morphology_table(make_napari_viewer, qtbot):
    """Threshold widget accepts morphology measurement tables."""
    from segmentation_measurement._threshold_widget import ThresholdWidget
    df = pd.DataFrame({
        "label": [1, 2, 3],
        "area": [100.0, 200.0, 300.0],
        "sphericity": [0.8, 0.9, 0.95],
    })
    viewer = make_napari_viewer()
    widget = ThresholdWidget(viewer)
    qtbot.addWidget(widget)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_csv(tmpdir, df)
        widget._path_edit.setText(path)
        widget._load_table()
    cols = [widget._col_combo.itemText(i) for i in range(widget._col_combo.count())]
    assert "area" in cols
    assert "sphericity" in cols
