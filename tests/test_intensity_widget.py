"""GUI tests for the napari intensity measurement widget."""
import numpy as np


def test_widget_instantiation(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    viewer = make_napari_viewer()
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    assert widget is not None


def test_seg_combo_populated_on_labels_add(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    viewer = make_napari_viewer()
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg")
    items = [widget._seg_combo.itemText(i) for i in range(widget._seg_combo.count())]
    assert "seg" in items


def test_img_combo_populated_on_image_add(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    viewer = make_napari_viewer()
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_image(np.zeros((10, 10), dtype=float), name="img")
    items = [widget._img_combo.itemText(i) for i in range(widget._img_combo.count())]
    assert "img" in items


def test_run_measurement_populates_table(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    intensity = np.ones((20, 20), dtype=np.float32) * 5.0
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    viewer.add_image(intensity, name="img")
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._img_combo.setCurrentText("img")
    widget._run_measurement()
    assert widget._measurements is not None
    assert len(widget._measurements) == 1
    assert widget._table.rowCount() == 1


def test_col_combo_populated_after_measurement(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    intensity = np.ones((20, 20), dtype=np.float32)
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    viewer.add_image(intensity, name="img")
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._img_combo.setCurrentText("img")
    widget._run_measurement()
    cols = [widget._col_combo.itemText(i) for i in range(widget._col_combo.count())]
    assert "mean_intensity" in cols
    assert "label" not in cols


def test_suggest_thresholds_sets_spinbox_values(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    seg[12:18, 12:18] = 2
    intensity = np.zeros((20, 20), dtype=np.float32)
    intensity[2:8, 2:8] = 10.0
    intensity[12:18, 12:18] = 50.0
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    viewer.add_image(intensity, name="img")
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._img_combo.setCurrentText("img")
    widget._run_measurement()
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("mean_intensity")
    widget._suggest_thresholds()
    assert len(widget._threshold_spins) == 1
    assert widget._threshold_spins[0].value() > 0.0


def test_categorize_creates_output_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    seg[12:18, 12:18] = 2
    intensity = np.zeros((20, 20), dtype=np.float32)
    intensity[2:8, 2:8] = 10.0
    intensity[12:18, 12:18] = 50.0
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    viewer.add_image(intensity, name="img")
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._img_combo.setCurrentText("img")
    widget._run_measurement()
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("mean_intensity")
    widget._threshold_spins[0].setValue(30.0)
    widget._out_name.setText("my_categories")
    widget._run_categorization()
    layer_names = [layer.name for layer in viewer.layers]
    assert "my_categories" in layer_names
    result = viewer.layers["my_categories"].data
    assert np.all(result[2:8, 2:8] == 1)
    assert np.all(result[12:18, 12:18] == 2)
    assert np.all(result[0:2, :] == 0)


def test_categorize_updates_existing_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    intensity = np.ones((20, 20), dtype=np.float32) * 5.0
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    viewer.add_image(intensity, name="img")
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._img_combo.setCurrentText("img")
    widget._run_measurement()
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("mean_intensity")
    widget._threshold_spins[0].setValue(10.0)
    widget._out_name.setText("cats")
    widget._run_categorization()
    n_layers_first = len(viewer.layers)
    widget._run_categorization()
    assert len(viewer.layers) == n_layers_first


def test_n_categories_rebuilds_widgets(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    viewer = make_napari_viewer()
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._n_spin.setValue(4)
    assert len(widget._threshold_spins) == 3
    assert len(widget._name_edits) == 4


def test_categorize_adds_category_id_to_table(make_napari_viewer, qtbot):
    from segmentation_measurement._intensity_widget import IntensityWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[2:8, 2:8] = 1
    intensity = np.ones((20, 20), dtype=np.float32) * 5.0
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    viewer.add_image(intensity, name="img")
    widget = IntensityWidget(viewer)
    qtbot.addWidget(widget)
    widget._seg_combo.setCurrentText("seg")
    widget._img_combo.setCurrentText("img")
    widget._run_measurement()
    widget._n_spin.setValue(2)
    widget._col_combo.setCurrentText("mean_intensity")
    widget._threshold_spins[0].setValue(10.0)
    widget._out_name.setText("cats")
    widget._run_categorization()
    headers = [
        widget._table.horizontalHeaderItem(i).text()
        for i in range(widget._table.columnCount())
    ]
    assert "category_id" in headers
    assert "category_name" in headers
