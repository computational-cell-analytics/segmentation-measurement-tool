"""GUI tests for the napari intensity measurement widget."""

import os
import sys
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestIntensityWidget(unittest.TestCase):

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
        from segmentation_measurement._intensity_widget import IntensityWidget
        widget = IntensityWidget(self._viewer)
        self.assertIsNotNone(widget)

    def test_seg_combo_populated_on_labels_add(self):
        from segmentation_measurement._intensity_widget import IntensityWidget
        widget = IntensityWidget(self._viewer)
        self._viewer.add_labels(np.zeros((10, 10), dtype=int), name="seg")
        items = [widget._seg_combo.itemText(i) for i in range(widget._seg_combo.count())]
        self.assertIn("seg", items)

    def test_img_combo_populated_on_image_add(self):
        from segmentation_measurement._intensity_widget import IntensityWidget
        widget = IntensityWidget(self._viewer)
        self._viewer.add_image(np.zeros((10, 10), dtype=float), name="img")
        items = [widget._img_combo.itemText(i) for i in range(widget._img_combo.count())]
        self.assertIn("img", items)

    def test_run_measurement_populates_table(self):
        from segmentation_measurement._intensity_widget import IntensityWidget
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[2:8, 2:8] = 1
        intensity = np.ones((20, 20), dtype=np.float32) * 5.0
        self._viewer.add_labels(seg, name="seg")
        self._viewer.add_image(intensity, name="img")
        widget = IntensityWidget(self._viewer)
        widget._seg_combo.setCurrentText("seg")
        widget._img_combo.setCurrentText("img")
        widget._run_measurement()
        self.assertIsNotNone(widget._measurements)
        self.assertEqual(len(widget._measurements), 1)
        self.assertEqual(widget._table.rowCount(), 1)

    def test_col_combo_populated_after_measurement(self):
        from segmentation_measurement._intensity_widget import IntensityWidget
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[2:8, 2:8] = 1
        intensity = np.ones((20, 20), dtype=np.float32)
        self._viewer.add_labels(seg, name="seg")
        self._viewer.add_image(intensity, name="img")
        widget = IntensityWidget(self._viewer)
        widget._seg_combo.setCurrentText("seg")
        widget._img_combo.setCurrentText("img")
        widget._run_measurement()
        cols = [widget._col_combo.itemText(i) for i in range(widget._col_combo.count())]
        self.assertIn("mean_intensity", cols)
        self.assertNotIn("label", cols)

    def test_suggest_thresholds_sets_spinbox_values(self):
        from segmentation_measurement._intensity_widget import IntensityWidget
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[2:8, 2:8] = 1
        seg[12:18, 12:18] = 2
        intensity = np.zeros((20, 20), dtype=np.float32)
        intensity[2:8, 2:8] = 10.0
        intensity[12:18, 12:18] = 50.0
        self._viewer.add_labels(seg, name="seg")
        self._viewer.add_image(intensity, name="img")
        widget = IntensityWidget(self._viewer)
        widget._seg_combo.setCurrentText("seg")
        widget._img_combo.setCurrentText("img")
        widget._run_measurement()
        widget._n_spin.setValue(2)
        widget._col_combo.setCurrentText("mean_intensity")
        widget._suggest_thresholds()
        self.assertEqual(len(widget._threshold_spins), 1)
        self.assertGreater(widget._threshold_spins[0].value(), 0.0)

    def test_categorize_creates_output_layer(self):
        from segmentation_measurement._intensity_widget import IntensityWidget
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[2:8, 2:8] = 1
        seg[12:18, 12:18] = 2
        intensity = np.zeros((20, 20), dtype=np.float32)
        intensity[2:8, 2:8] = 10.0
        intensity[12:18, 12:18] = 50.0
        self._viewer.add_labels(seg, name="seg")
        self._viewer.add_image(intensity, name="img")
        widget = IntensityWidget(self._viewer)
        widget._seg_combo.setCurrentText("seg")
        widget._img_combo.setCurrentText("img")
        widget._run_measurement()
        widget._n_spin.setValue(2)
        widget._col_combo.setCurrentText("mean_intensity")
        widget._threshold_spins[0].setValue(30.0)
        widget._out_name.setText("my_categories")
        widget._run_categorization()
        layer_names = [layer.name for layer in self._viewer.layers]
        self.assertIn("my_categories", layer_names)
        result = self._viewer.layers["my_categories"].data
        # label 1 (mean=10) < 30 → category 1
        # label 2 (mean=50) >= 30 → category 2
        self.assertTrue(np.all(result[2:8, 2:8] == 1))
        self.assertTrue(np.all(result[12:18, 12:18] == 2))
        self.assertTrue(np.all(result[0:2, :] == 0))  # background stays 0

    def test_categorize_updates_existing_layer(self):
        from segmentation_measurement._intensity_widget import IntensityWidget
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[2:8, 2:8] = 1
        intensity = np.ones((20, 20), dtype=np.float32) * 5.0
        self._viewer.add_labels(seg, name="seg")
        self._viewer.add_image(intensity, name="img")
        widget = IntensityWidget(self._viewer)
        widget._seg_combo.setCurrentText("seg")
        widget._img_combo.setCurrentText("img")
        widget._run_measurement()
        widget._n_spin.setValue(2)
        widget._col_combo.setCurrentText("mean_intensity")
        widget._threshold_spins[0].setValue(10.0)
        widget._out_name.setText("cats")
        widget._run_categorization()
        n_layers_first = len(self._viewer.layers)
        widget._run_categorization()
        self.assertEqual(len(self._viewer.layers), n_layers_first)

    def test_n_categories_rebuilds_widgets(self):
        from segmentation_measurement._intensity_widget import IntensityWidget
        widget = IntensityWidget(self._viewer)
        widget._n_spin.setValue(4)
        self.assertEqual(len(widget._threshold_spins), 3)
        self.assertEqual(len(widget._name_edits), 4)

    def test_categorize_adds_category_id_to_table(self):
        from segmentation_measurement._intensity_widget import IntensityWidget
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[2:8, 2:8] = 1
        intensity = np.ones((20, 20), dtype=np.float32) * 5.0
        self._viewer.add_labels(seg, name="seg")
        self._viewer.add_image(intensity, name="img")
        widget = IntensityWidget(self._viewer)
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
        self.assertIn("category_id", headers)
        self.assertIn("category_name", headers)


if __name__ == "__main__":
    unittest.main()
