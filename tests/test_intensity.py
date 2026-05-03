"""Tests for intensity measurement functions and CLI."""

import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import tifffile

from segmentation_measurement.intensity import (
    categorize_by_intensity,
    measure_intensities,
    suggest_thresholds,
)


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


class TestSuggestThresholds(unittest.TestCase):

    def _make_measurements(self):
        return pd.DataFrame({
            "label": np.arange(1, 11),
            "mean_intensity": np.linspace(0.0, 100.0, 10),
        })

    def test_returns_correct_count(self):
        df = self._make_measurements()
        for n in range(2, 6):
            thresholds = suggest_thresholds(df, "mean_intensity", n)
            self.assertEqual(len(thresholds), n - 1)

    def test_thresholds_are_sorted(self):
        df = self._make_measurements()
        thresholds = suggest_thresholds(df, "mean_intensity", 4)
        self.assertEqual(thresholds, sorted(thresholds))

    def test_thresholds_within_data_range(self):
        df = self._make_measurements()
        thresholds = suggest_thresholds(df, "mean_intensity", 3)
        for t in thresholds:
            self.assertGreater(t, df["mean_intensity"].min())
            self.assertLess(t, df["mean_intensity"].max())

    def test_raises_on_invalid_n_categories(self):
        df = self._make_measurements()
        with self.assertRaises(ValueError):
            suggest_thresholds(df, "mean_intensity", 1)

    def test_raises_on_missing_column(self):
        df = self._make_measurements()
        with self.assertRaises(ValueError):
            suggest_thresholds(df, "nonexistent", 3)


class TestCategorizeByIntensity(unittest.TestCase):

    def _make_measurements(self):
        return pd.DataFrame({
            "label": [1, 2, 3, 4, 5],
            "mean_intensity": [10.0, 30.0, 50.0, 70.0, 90.0],
        })

    def test_adds_category_columns(self):
        df = self._make_measurements()
        result = categorize_by_intensity(df, "mean_intensity", [40.0])
        self.assertIn("category_id", result.columns)
        self.assertIn("category_name", result.columns)

    def test_two_category_assignment(self):
        df = self._make_measurements()
        result = categorize_by_intensity(df, "mean_intensity", [40.0])
        low = result[result["mean_intensity"] < 40.0]["category_id"].values
        high = result[result["mean_intensity"] >= 40.0]["category_id"].values
        self.assertTrue(np.all(low == 1))
        self.assertTrue(np.all(high == 2))

    def test_three_category_assignment(self):
        df = self._make_measurements()
        result = categorize_by_intensity(df, "mean_intensity", [35.0, 65.0])
        self.assertEqual(
            result[result["mean_intensity"] == 10.0].iloc[0]["category_id"], 1
        )
        self.assertEqual(
            result[result["mean_intensity"] == 50.0].iloc[0]["category_id"], 2
        )
        self.assertEqual(
            result[result["mean_intensity"] == 90.0].iloc[0]["category_id"], 3
        )

    def test_custom_category_names(self):
        df = self._make_measurements()
        result = categorize_by_intensity(
            df, "mean_intensity", [40.0], ["low", "high"]
        )
        self.assertIn("low", result["category_name"].values)
        self.assertIn("high", result["category_name"].values)

    def test_default_category_names(self):
        df = self._make_measurements()
        result = categorize_by_intensity(df, "mean_intensity", [40.0])
        self.assertIn("category_1", result["category_name"].values)
        self.assertIn("category_2", result["category_name"].values)

    def test_unsorted_thresholds_handled(self):
        df = self._make_measurements()
        result_sorted = categorize_by_intensity(df, "mean_intensity", [35.0, 65.0])
        result_unsorted = categorize_by_intensity(df, "mean_intensity", [65.0, 35.0])
        np.testing.assert_array_equal(
            result_sorted["category_id"].values,
            result_unsorted["category_id"].values,
        )

    def test_does_not_modify_input(self):
        df = self._make_measurements()
        original_cols = list(df.columns)
        categorize_by_intensity(df, "mean_intensity", [40.0])
        self.assertEqual(list(df.columns), original_cols)

    def test_raises_on_missing_column(self):
        df = self._make_measurements()
        with self.assertRaises(ValueError):
            categorize_by_intensity(df, "nonexistent", [40.0])

    def test_raises_on_wrong_category_names_count(self):
        df = self._make_measurements()
        with self.assertRaises(ValueError):
            categorize_by_intensity(df, "mean_intensity", [40.0], ["only_one"])


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
