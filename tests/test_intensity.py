"""Tests for intensity measurement function and CLI."""

import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import tifffile

from segmentation_measurement.intensity import measure_intensities


class TestMeasureIntensities(unittest.TestCase):

    def _make_data_2d(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[2:8, 2:8] = 1    # 36 pixels, intensity 10
        seg[12:18, 12:18] = 2  # 36 pixels, intensity 50
        intensity = np.zeros((20, 20), dtype=np.float32)
        intensity[2:8, 2:8] = 10.0
        intensity[12:18, 12:18] = 50.0
        return seg, intensity

    def test_returns_dataframe(self):
        seg, intensity = self._make_data_2d()
        result = measure_intensities(seg, intensity)
        self.assertIsInstance(result, pd.DataFrame)

    def test_one_row_per_label(self):
        seg, intensity = self._make_data_2d()
        result = measure_intensities(seg, intensity)
        self.assertEqual(len(result), 2)
        self.assertSetEqual(set(result["label"]), {1, 2})

    def test_correct_mean_intensity(self):
        seg, intensity = self._make_data_2d()
        result = measure_intensities(seg, intensity)
        row1 = result[result["label"] == 1].iloc[0]
        row2 = result[result["label"] == 2].iloc[0]
        self.assertAlmostEqual(row1["mean_intensity"], 10.0, places=4)
        self.assertAlmostEqual(row2["mean_intensity"], 50.0, places=4)

    def test_required_columns_present(self):
        seg, intensity = self._make_data_2d()
        result = measure_intensities(seg, intensity)
        for col in [
            "label", "mean_intensity", "median_intensity",
            "max_intensity", "min_intensity", "std_intensity",
            "percentile_10", "percentile_25", "percentile_75", "percentile_90",
        ]:
            self.assertIn(col, result.columns)

    def test_uniform_region_has_zero_std(self):
        seg, intensity = self._make_data_2d()
        result = measure_intensities(seg, intensity)
        self.assertAlmostEqual(
            result[result["label"] == 1].iloc[0]["std_intensity"], 0.0
        )

    def test_percentiles_ordered(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[2:18, 2:18] = 1
        rng = np.random.default_rng(0)
        intensity = rng.random((20, 20)).astype(np.float32)
        result = measure_intensities(seg, intensity)
        row = result.iloc[0]
        self.assertLessEqual(row["percentile_10"], row["percentile_25"])
        self.assertLessEqual(row["percentile_25"], row["percentile_75"])
        self.assertLessEqual(row["percentile_75"], row["percentile_90"])

    def test_works_3d(self):
        seg = np.zeros((10, 10, 10), dtype=np.int32)
        seg[1:5, 1:5, 1:5] = 1
        intensity = np.full((10, 10, 10), 5.0, dtype=np.float32)
        result = measure_intensities(seg, intensity)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result.iloc[0]["mean_intensity"], 5.0)

    def test_empty_segmentation_returns_empty_dataframe(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        intensity = np.zeros((10, 10), dtype=np.float32)
        result = measure_intensities(seg, intensity)
        self.assertEqual(len(result), 0)
        self.assertIn("label", result.columns)


class TestIntensityCLI(unittest.TestCase):

    def _call_main(self, argv):
        from segmentation_measurement._cli import main
        with patch("sys.argv", ["segmentation-measurement"] + argv):
            main()

    def test_measure_intensities_cli_csv(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[2:8, 2:8] = 1
        seg[12:18, 12:18] = 2
        intensity = np.zeros((20, 20), dtype=np.float32)
        intensity[2:8, 2:8] = 10.0
        intensity[12:18, 12:18] = 50.0
        with tempfile.TemporaryDirectory() as tmpdir:
            seg_path = os.path.join(tmpdir, "seg.tif")
            int_path = os.path.join(tmpdir, "intensity.tif")
            out_path = os.path.join(tmpdir, "measurements.csv")
            tifffile.imwrite(seg_path, seg)
            tifffile.imwrite(int_path, intensity)
            self._call_main([
                "measure", "intensities",
                "--segmentation", seg_path,
                "--intensity", int_path,
                "--output", out_path,
            ])
            df = pd.read_csv(out_path)
            self.assertEqual(len(df), 2)
            self.assertIn("mean_intensity", df.columns)
            self.assertAlmostEqual(
                df[df["label"] == 1].iloc[0]["mean_intensity"], 10.0, places=2
            )
            self.assertAlmostEqual(
                df[df["label"] == 2].iloc[0]["mean_intensity"], 50.0, places=2
            )

    def test_measure_intensities_cli_tsv(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[2:8, 2:8] = 1
        intensity = np.ones((10, 10), dtype=np.float32) * 7.0
        with tempfile.TemporaryDirectory() as tmpdir:
            seg_path = os.path.join(tmpdir, "seg.tif")
            int_path = os.path.join(tmpdir, "intensity.tif")
            out_path = os.path.join(tmpdir, "measurements.tsv")
            tifffile.imwrite(seg_path, seg)
            tifffile.imwrite(int_path, intensity)
            self._call_main([
                "measure", "intensities",
                "--segmentation", seg_path,
                "--intensity", int_path,
                "--output", out_path,
            ])
            df = pd.read_csv(out_path, sep="\t")
            self.assertEqual(len(df), 1)
            self.assertAlmostEqual(df.iloc[0]["mean_intensity"], 7.0, places=2)


if __name__ == "__main__":
    unittest.main()
