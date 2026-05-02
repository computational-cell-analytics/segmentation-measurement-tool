"""GUI tests for the napari postprocessing widget."""

import os
import sys
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestPostprocessingWidget(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from qtpy.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        import napari
        self._viewer = napari.Viewer(show=False)

    def tearDown(self):
        self._viewer.close()

    def test_widget_instantiation(self):
        from segmentation_measurement._widget import PostprocessingWidget
        widget = PostprocessingWidget(self._viewer)
        self.assertIsNotNone(widget)

    def test_method_switching_updates_params_panel(self):
        from segmentation_measurement._widget import PostprocessingWidget
        widget = PostprocessingWidget(self._viewer)
        for i in range(3):
            widget._method_combo.setCurrentIndex(i)
            self.assertEqual(widget._params_stack.currentIndex(), i)

    def test_layer_combo_populated_on_add(self):
        from segmentation_measurement._widget import PostprocessingWidget
        widget = PostprocessingWidget(self._viewer)
        self._viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg")
        items = [widget._input_combo.itemText(i) for i in range(widget._input_combo.count())]
        self.assertIn("seg", items)

    def test_run_filter_small_segments(self):
        from segmentation_measurement._widget import PostprocessingWidget
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[0:3, 0:3] = 1  # 9 pixels — kept
        seg[5:6, 5:6] = 2  # 1 pixel  — removed
        self._viewer.add_labels(seg, name="seg")
        widget = PostprocessingWidget(self._viewer)
        widget._input_combo.setCurrentText("seg")
        widget._output_combo.setCurrentText("result")
        widget._method_combo.setCurrentIndex(0)  # filter_small_segments
        widget._min_size_spin.setValue(5)
        widget._run()
        result = self._viewer.layers["result"].data
        np.testing.assert_array_equal(result[0:3, 0:3], 1)
        np.testing.assert_array_equal(result[5:6, 5:6], 0)

    def test_run_remove_small_holes(self):
        from segmentation_measurement._widget import PostprocessingWidget
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[1:9, 1:9] = 1
        seg[4:6, 4:6] = 0  # 4-pixel hole
        self._viewer.add_labels(seg, name="seg")
        widget = PostprocessingWidget(self._viewer)
        widget._input_combo.setCurrentText("seg")
        widget._output_combo.setCurrentText("result")
        widget._method_combo.setCurrentIndex(1)  # remove_small_holes
        widget._max_hole_size_spin.setValue(10)
        widget._run()
        result = self._viewer.layers["result"].data
        np.testing.assert_array_equal(result[4:6, 4:6], 1)

    def test_run_ring_mask(self):
        from segmentation_measurement._widget import PostprocessingWidget
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[8:12, 8:12] = 1
        self._viewer.add_labels(seg, name="seg")
        widget = PostprocessingWidget(self._viewer)
        widget._input_combo.setCurrentText("seg")
        widget._output_combo.setCurrentText("result")
        widget._method_combo.setCurrentIndex(2)  # ring_mask
        widget._ring_width_spin.setValue(2)
        widget._run()
        result = self._viewer.layers["result"].data
        # Original segment pixels absent; ring pixels present outside them
        np.testing.assert_array_equal(result[8:12, 8:12], 0)
        self.assertTrue(np.any(result == 1))

    def test_run_in_place_updates_existing_layer(self):
        from segmentation_measurement._widget import PostprocessingWidget
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[0:3, 0:3] = 1
        seg[5:6, 5:6] = 2
        self._viewer.add_labels(seg, name="seg")
        widget = PostprocessingWidget(self._viewer)
        widget._input_combo.setCurrentText("seg")
        widget._output_combo.setCurrentText("seg")  # same name → in-place
        widget._method_combo.setCurrentIndex(0)
        widget._min_size_spin.setValue(5)
        widget._run()
        layer_count = len(self._viewer.layers)
        self.assertEqual(layer_count, 1)
        np.testing.assert_array_equal(self._viewer.layers["seg"].data[5:6, 5:6], 0)


if __name__ == "__main__":
    unittest.main()
