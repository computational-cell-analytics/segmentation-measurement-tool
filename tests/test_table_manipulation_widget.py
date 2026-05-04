"""GUI tests for the napari table manipulation widget."""

import os
import tempfile

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _clear_registry():
    from segmentation_measurement._utils import clear_table_registry
    clear_table_registry()
    yield
    clear_table_registry()


def _register(name, df):
    from segmentation_measurement._utils import register_table
    register_table(name, df)


def test_widget_instantiation(make_napari_viewer, qtbot):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    viewer = make_napari_viewer()
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    assert widget is not None


def test_refresh_populates_combos(make_napari_viewer, qtbot):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    df = pd.DataFrame({"label": [1, 2], "mean_intensity": [10.0, 20.0]})
    _register("Intensity (cells)", df)
    viewer = make_napari_viewer()
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_registry_combos()
    items = [widget._source_combo.itemText(i) for i in range(widget._source_combo.count())]
    assert "Intensity (cells)" in items


def test_load_from_registry_populates_table(make_napari_viewer, qtbot):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    df = pd.DataFrame({"label": [1, 2], "x": [1.0, 2.0]})
    _register("t1", df)
    viewer = make_napari_viewer()
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_registry_combos()
    widget._source_combo.setCurrentText("t1")
    widget._load_from_registry()
    assert widget._table_data is not None
    assert widget._table.rowCount() == 2
    headers = [
        widget._table.horizontalHeaderItem(i).text()
        for i in range(widget._table.columnCount())
    ]
    assert "label" in headers
    assert "x" in headers


def test_drop_combo_excludes_label(make_napari_viewer, qtbot):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    df = pd.DataFrame({"label": [1, 2], "x": [1.0, 2.0], "y": [3.0, 4.0]})
    _register("t1", df)
    viewer = make_napari_viewer()
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_registry_combos()
    widget._source_combo.setCurrentText("t1")
    widget._load_from_registry()
    items = [widget._drop_combo.itemText(i) for i in range(widget._drop_combo.count())]
    assert "label" not in items
    assert "x" in items
    assert "y" in items


def test_drop_column_updates_table(make_napari_viewer, qtbot):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    df = pd.DataFrame({"label": [1, 2], "x": [1.0, 2.0], "y": [3.0, 4.0]})
    _register("t1", df)
    viewer = make_napari_viewer()
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_registry_combos()
    widget._source_combo.setCurrentText("t1")
    widget._load_from_registry()
    widget._drop_combo.setCurrentText("y")
    widget._drop_column()
    assert "y" not in widget._table_data.columns
    assert "x" in widget._table_data.columns
    assert "label" in widget._table_data.columns


def test_merge_with_registered_table(make_napari_viewer, qtbot):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    a = pd.DataFrame({"label": [1, 2], "mean_intensity": [10.0, 20.0]})
    b = pd.DataFrame({"label": [1, 2], "area": [100, 200]})
    _register("intensity", a)
    _register("morphology", b)
    viewer = make_napari_viewer()
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_registry_combos()
    widget._source_combo.setCurrentText("intensity")
    widget._load_from_registry()
    widget._merge_combo.setCurrentText("morphology")
    widget._merge_with_selected()
    assert set(widget._table_data.columns) == {"label", "mean_intensity", "area"}
    assert len(widget._table_data) == 2


def test_load_from_file_rejects_table_without_label(make_napari_viewer, qtbot, monkeypatch):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    df = pd.DataFrame({"id": [1, 2], "x": [1.0, 2.0]})
    viewer = make_napari_viewer()
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "no_label.csv")
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
    assert widget._table_data is None
    assert len(warnings) == 1


def test_load_from_file_accepts_table_with_label(make_napari_viewer, qtbot, monkeypatch):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    df = pd.DataFrame({"label": [1, 2], "x": [1.0, 2.0]})
    viewer = make_napari_viewer()
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "tbl.csv")
        df.to_csv(path, index=False)
        monkeypatch.setattr(
            "segmentation_measurement._table_manipulation_widget.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (path, "")),
        )
        widget._load_from_file()
    assert widget._table_data is not None
    assert list(widget._table_data.columns) == ["label", "x"]


def test_merge_with_conflicting_columns_warns(make_napari_viewer, qtbot, monkeypatch):
    from segmentation_measurement._table_manipulation_widget import TableManipulationWidget
    a = pd.DataFrame({"label": [1, 2], "shared": [1.0, 2.0]})
    b = pd.DataFrame({"label": [1, 2], "shared": [3.0, 4.0]})
    _register("a", a)
    _register("b", b)
    viewer = make_napari_viewer()
    widget = TableManipulationWidget(viewer)
    qtbot.addWidget(widget)
    widget._refresh_registry_combos()
    widget._source_combo.setCurrentText("a")
    widget._load_from_registry()
    widget._merge_combo.setCurrentText("b")
    warnings = []
    monkeypatch.setattr(
        "segmentation_measurement._table_manipulation_widget.QMessageBox.warning",
        staticmethod(lambda *a, **k: warnings.append(a)),
    )
    widget._merge_with_selected()
    # The warning was shown and the table was not changed.
    assert len(warnings) == 1
    assert set(widget._table_data.columns) == {"label", "shared"}
