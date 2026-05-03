"""Tests for morphology measurement function and CLI."""

import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import tifffile

from segmentation_measurement.morphology import measure_morphology


class TestMeasureMorphology2D(unittest.TestCase):

    def _make_square_2d(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[4:14, 4:14] = 1  # 10x10 square
        return seg

    def test_returns_dataframe(self):
        result = measure_morphology(self._make_square_2d())
        self.assertIsInstance(result, pd.DataFrame)

    def test_one_row_per_label(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[2:8, 2:8] = 1
        seg[12:18, 12:18] = 2
        result = measure_morphology(seg)
        self.assertEqual(len(result), 2)
        self.assertSetEqual(set(result["label"]), {1, 2})

    def test_required_columns_2d(self):
        result = measure_morphology(self._make_square_2d())
        for col in ["label", "area", "perimeter", "sphericity", "solidity",
                    "axis_major_length", "axis_minor_length", "equivalent_diameter"]:
            self.assertIn(col, result.columns)

    def test_area_correct_unit_scale(self):
        result = measure_morphology(self._make_square_2d())
        # 10x10 square = 100 pixels
        self.assertAlmostEqual(result.iloc[0]["area"], 100.0, places=1)

    def test_area_correct_physical_scale(self):
        result = measure_morphology(self._make_square_2d(), scale=0.5)
        # 100 pixels * 0.25 = 25
        self.assertAlmostEqual(result.iloc[0]["area"], 25.0, places=1)

    def test_sphericity_bounded(self):
        result = measure_morphology(self._make_square_2d())
        s = result.iloc[0]["sphericity"]
        self.assertGreater(s, 0.0)
        self.assertLessEqual(s, 1.0 + 1e-6)  # circle has sphericity=1

    def test_solidity_bounded(self):
        result = measure_morphology(self._make_square_2d())
        sol = result.iloc[0]["solidity"]
        self.assertGreater(sol, 0.0)
        self.assertLessEqual(sol, 1.0)

    def test_empty_segmentation(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        result = measure_morphology(seg)
        self.assertEqual(len(result), 0)
        self.assertIn("label", result.columns)

    def test_raises_on_unsupported_ndim(self):
        with self.assertRaises(ValueError):
            measure_morphology(np.zeros((5, 5, 5, 5), dtype=np.int32))


class TestMeasureMorphology3D(unittest.TestCase):

    def _make_cube_3d(self):
        seg = np.zeros((20, 20, 20), dtype=np.int32)
        seg[4:14, 4:14, 4:14] = 1  # 10x10x10 cube
        return seg

    def test_returns_dataframe_3d(self):
        result = measure_morphology(self._make_cube_3d())
        self.assertIsInstance(result, pd.DataFrame)

    def test_required_columns_3d(self):
        result = measure_morphology(self._make_cube_3d())
        for col in ["label", "volume", "surface_area", "sphericity", "solidity",
                    "axis_major_length", "axis_minor_length", "equivalent_diameter"]:
            self.assertIn(col, result.columns)

    def test_volume_correct_unit_scale(self):
        result = measure_morphology(self._make_cube_3d())
        # 10x10x10 = 1000 voxels
        self.assertAlmostEqual(result.iloc[0]["volume"], 1000.0, places=1)

    def test_volume_correct_physical_scale(self):
        result = measure_morphology(self._make_cube_3d(), scale=0.5)
        # 1000 voxels * 0.125 = 125
        self.assertAlmostEqual(result.iloc[0]["volume"], 125.0, places=1)

    def test_surface_area_positive(self):
        result = measure_morphology(self._make_cube_3d())
        self.assertGreater(result.iloc[0]["surface_area"], 0.0)

    def test_sphericity_bounded_3d(self):
        result = measure_morphology(self._make_cube_3d())
        s = result.iloc[0]["sphericity"]
        self.assertGreater(s, 0.0)
        self.assertLessEqual(s, 1.0 + 1e-6)


class TestMorphologyCLI(unittest.TestCase):

    def _call_main(self, argv):
        from segmentation_measurement._cli import main
        with patch("sys.argv", ["segmentation-measurement"] + argv):
            main()

    def test_measure_morphology_cli_csv(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[2:12, 2:12] = 1
        seg[12:18, 12:18] = 2
        with tempfile.TemporaryDirectory() as tmpdir:
            seg_path = os.path.join(tmpdir, "seg.tif")
            out_path = os.path.join(tmpdir, "morphology.csv")
            tifffile.imwrite(seg_path, seg)
            self._call_main([
                "measure", "morphology",
                "--segmentation", seg_path,
                "--output", out_path,
            ])
            df = pd.read_csv(out_path)
            self.assertEqual(len(df), 2)
            self.assertIn("area", df.columns)

    def test_measure_morphology_cli_with_scale(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[2:8, 2:8] = 1
        with tempfile.TemporaryDirectory() as tmpdir:
            seg_path = os.path.join(tmpdir, "seg.tif")
            out_path = os.path.join(tmpdir, "morphology.csv")
            tifffile.imwrite(seg_path, seg)
            self._call_main([
                "measure", "morphology",
                "--segmentation", seg_path,
                "--output", out_path,
                "--scale", "0.5",
            ])
            df = pd.read_csv(out_path)
            # 6x6 = 36 pixels * 0.25 = 9.0
            self.assertAlmostEqual(df.iloc[0]["area"], 9.0, places=1)


if __name__ == "__main__":
    unittest.main()
