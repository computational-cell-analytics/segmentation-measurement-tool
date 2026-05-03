"""GUI tests for the napari postprocessing widget."""
import numpy as np


def test_widget_instantiation(make_napari_viewer, qtbot):
    from segmentation_measurement._widget import PostprocessingWidget
    viewer = make_napari_viewer()
    widget = PostprocessingWidget(viewer)
    qtbot.addWidget(widget)
    assert widget is not None


def test_method_switching_updates_params_panel(make_napari_viewer, qtbot):
    from segmentation_measurement._widget import PostprocessingWidget
    viewer = make_napari_viewer()
    widget = PostprocessingWidget(viewer)
    qtbot.addWidget(widget)
    for i in range(3):
        widget._method_combo.setCurrentIndex(i)
        assert widget._params_stack.currentIndex() == i


def test_layer_combo_populated_on_add(make_napari_viewer, qtbot):
    from segmentation_measurement._widget import PostprocessingWidget
    viewer = make_napari_viewer()
    widget = PostprocessingWidget(viewer)
    qtbot.addWidget(widget)
    viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg")
    items = [widget._input_combo.itemText(i) for i in range(widget._input_combo.count())]
    assert "seg" in items


def test_run_filter_small_segments(make_napari_viewer, qtbot):
    from segmentation_measurement._widget import PostprocessingWidget
    seg = np.zeros((10, 10), dtype=np.int32)
    seg[0:3, 0:3] = 1  # 9 pixels — kept
    seg[5:6, 5:6] = 2  # 1 pixel  — removed
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = PostprocessingWidget(viewer)
    qtbot.addWidget(widget)
    widget._input_combo.setCurrentText("seg")
    widget._output_combo.setCurrentText("result")
    widget._method_combo.setCurrentIndex(0)
    widget._min_size_spin.setValue(5)
    widget._run()
    result = viewer.layers["result"].data
    np.testing.assert_array_equal(result[0:3, 0:3], 1)
    np.testing.assert_array_equal(result[5:6, 5:6], 0)


def test_run_remove_small_holes(make_napari_viewer, qtbot):
    from segmentation_measurement._widget import PostprocessingWidget
    seg = np.zeros((10, 10), dtype=np.int32)
    seg[1:9, 1:9] = 1
    seg[4:6, 4:6] = 0  # 4-pixel hole
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = PostprocessingWidget(viewer)
    qtbot.addWidget(widget)
    widget._input_combo.setCurrentText("seg")
    widget._output_combo.setCurrentText("result")
    widget._method_combo.setCurrentIndex(1)
    widget._max_hole_size_spin.setValue(10)
    widget._run()
    result = viewer.layers["result"].data
    np.testing.assert_array_equal(result[4:6, 4:6], 1)


def test_run_ring_mask(make_napari_viewer, qtbot):
    from segmentation_measurement._widget import PostprocessingWidget
    seg = np.zeros((20, 20), dtype=np.int32)
    seg[8:12, 8:12] = 1
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = PostprocessingWidget(viewer)
    qtbot.addWidget(widget)
    widget._input_combo.setCurrentText("seg")
    widget._output_combo.setCurrentText("result")
    widget._method_combo.setCurrentIndex(2)
    widget._ring_width_spin.setValue(2)
    widget._run()
    result = viewer.layers["result"].data
    np.testing.assert_array_equal(result[8:12, 8:12], 0)
    assert np.any(result == 1)


def test_run_in_place_updates_existing_layer(make_napari_viewer, qtbot):
    from segmentation_measurement._widget import PostprocessingWidget
    seg = np.zeros((10, 10), dtype=np.int32)
    seg[0:3, 0:3] = 1
    seg[5:6, 5:6] = 2
    viewer = make_napari_viewer()
    viewer.add_labels(seg, name="seg")
    widget = PostprocessingWidget(viewer)
    qtbot.addWidget(widget)
    widget._input_combo.setCurrentText("seg")
    widget._output_combo.setCurrentText("seg")  # same name → in-place
    widget._method_combo.setCurrentIndex(0)
    widget._min_size_spin.setValue(5)
    widget._run()
    assert len(viewer.layers) == 1
    np.testing.assert_array_equal(viewer.layers["seg"].data[5:6, 5:6], 0)
