"""GUI tests for the napari table manipulation widget."""

import os
import tempfile

import numpy as np
import pandas as pd


def _seg_with_features(viewer, features, name="seg"):
    seg = np.zeros((20, 20), dtype=np.int32)
    # Place at least one pixel per labelled index value
    for i, idx in enumerate(features["index"].values):
        seg[i % 20, (i + 5) % 20] = int(idx)
    layer = viewer.add_labels(seg, name=name)
    layer.features = features
    return layer


def test_widget_instantiation(make_napari_viewer, qtbot):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    viewer = make_napari_viewer()
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    assert widget is not None


def test_seg_combo_populated_on_labels_add(make_napari_viewer, qtbot):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    viewer = make_napari_viewer()
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg")
    items = [widget._seg_combo.itemText(i) for i in range(widget._seg_combo.count())]
    assert "seg" in items


def test_drop_combo_excludes_index(make_napari_viewer, qtbot):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    df = pd.DataFrame({"index": [1, 2], "x": [1.0, 2.0], "y": [3.0, 4.0]})
    viewer = make_napari_viewer()
    _seg_with_features(viewer, df, name="seg")
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    items = [widget._drop_combo.itemText(i) for i in range(widget._drop_combo.count())]
    assert "index" not in items
    assert "x" in items
    assert "y" in items


def test_drop_column_removes_from_layer_features(make_napari_viewer, qtbot):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    df = pd.DataFrame({"index": [1, 2], "x": [1.0, 2.0], "y": [3.0, 4.0]})
    viewer = make_napari_viewer()
    layer = _seg_with_features(viewer, df, name="seg")
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._drop_combo.setCurrentText("y")
    widget._drop_column()
    assert "y" not in layer.features.columns
    assert "x" in layer.features.columns
    assert "index" in layer.features.columns


def test_load_from_file_rejects_table_without_index(make_napari_viewer, qtbot, monkeypatch):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    df = pd.DataFrame({"id": [1, 2], "x": [1.0, 2.0]})
    viewer = make_napari_viewer()
    seg = np.zeros((10, 10), dtype=np.int32)
    seg[1:3, 1:3] = 1
    layer = viewer.add_labels(seg, name="seg")
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "no_index.csv")
        df.to_csv(path, index=False)
        monkeypatch.setattr(
            "segmentation_measurement._table_manipulation_widget.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (path, "")),
        )
        warnings = []
        monkeypatch.setattr(
            "segmentation_measurement._table_manipulation_widget.QMessageBox.warning",
            staticmethod(lambda *a, **k: warnings.append(a)),
        )
        widget._load_from_file()
    assert len(warnings) == 1
    feats = getattr(layer, "features", None)
    assert feats is None or len(feats.columns) == 0


def test_load_from_file_merges_into_features(make_napari_viewer, qtbot, monkeypatch):
    """Loading an external table merges its columns into the layer's existing features."""
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget

    existing = pd.DataFrame({"index": [1, 2], "mean_intensity": [10.0, 20.0]})
    extra = pd.DataFrame({"index": [1, 2], "area": [100, 200]})

    viewer = make_napari_viewer()
    layer = _seg_with_features(viewer, existing, name="seg")
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "extra.csv")
        extra.to_csv(path, index=False)
        monkeypatch.setattr(
            "segmentation_measurement._table_manipulation_widget.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (path, "")),
        )
        widget._load_from_file()

    cols = set(layer.features.columns)
    assert cols == {"index", "mean_intensity", "area"}


def test_load_overwrites_conflicting_columns(make_napari_viewer, qtbot, monkeypatch):
    """A loaded column with the same name overwrites the existing one."""
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget

    existing = pd.DataFrame({"index": [1, 2], "mean_intensity": [10.0, 20.0]})
    overwrite = pd.DataFrame({"index": [1, 2], "mean_intensity": [99.0, 88.0]})

    viewer = make_napari_viewer()
    layer = _seg_with_features(viewer, existing, name="seg")
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "ov.csv")
        overwrite.to_csv(path, index=False)
        monkeypatch.setattr(
            "segmentation_measurement._table_manipulation_widget.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (path, "")),
        )
        widget._load_from_file()

    feats = layer.features.set_index("index")
    assert feats.loc[1, "mean_intensity"] == 99.0
    assert feats.loc[2, "mean_intensity"] == 88.0
