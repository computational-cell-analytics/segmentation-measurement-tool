"""Tests for threshold analysis functions and CLI."""

import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import tifffile

from segmentation_measurement.analysis import categorize_by_threshold, suggest_thresholds


class TestSuggestThresholds(unittest.TestCase):

    def _make_measurements(self):
        return pd.DataFrame({
            "index": np.arange(1, 11),
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

    def test_works_with_morphology_columns(self):
        df = pd.DataFrame({
            "index": [1, 2, 3],
            "area": [100.0, 200.0, 300.0],
        })
        thresholds = suggest_thresholds(df, "area", 3)
        self.assertEqual(len(thresholds), 2)


class TestCategorizeByThreshold(unittest.TestCase):

    def _make_measurements(self):
        return pd.DataFrame({
            "index": [1, 2, 3, 4, 5],
            "mean_intensity": [10.0, 30.0, 50.0, 70.0, 90.0],
        })

    def test_adds_category_columns(self):
        df = self._make_measurements()
        result = categorize_by_threshold(df, "mean_intensity", [40.0])
        self.assertIn("category_id", result.columns)
        self.assertIn("category_name", result.columns)

    def test_two_category_assignment(self):
        df = self._make_measurements()
        result = categorize_by_threshold(df, "mean_intensity", [40.0])
        low = result[result["mean_intensity"] < 40.0]["category_id"].values
        high = result[result["mean_intensity"] >= 40.0]["category_id"].values
        self.assertTrue(np.all(low == 1))
        self.assertTrue(np.all(high == 2))

    def test_three_category_assignment(self):
        df = self._make_measurements()
        result = categorize_by_threshold(df, "mean_intensity", [35.0, 65.0])
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
        result = categorize_by_threshold(df, "mean_intensity", [40.0], ["low", "high"])
        self.assertIn("low", result["category_name"].values)
        self.assertIn("high", result["category_name"].values)

    def test_default_category_names(self):
        df = self._make_measurements()
        result = categorize_by_threshold(df, "mean_intensity", [40.0])
        self.assertIn("category_1", result["category_name"].values)
        self.assertIn("category_2", result["category_name"].values)

    def test_unsorted_thresholds_handled(self):
        df = self._make_measurements()
        result_sorted = categorize_by_threshold(df, "mean_intensity", [35.0, 65.0])
        result_unsorted = categorize_by_threshold(df, "mean_intensity", [65.0, 35.0])
        np.testing.assert_array_equal(
            result_sorted["category_id"].values,
            result_unsorted["category_id"].values,
        )

    def test_does_not_modify_input(self):
        df = self._make_measurements()
        original_cols = list(df.columns)
        categorize_by_threshold(df, "mean_intensity", [40.0])
        self.assertEqual(list(df.columns), original_cols)

    def test_raises_on_missing_column(self):
        df = self._make_measurements()
        with self.assertRaises(ValueError):
            categorize_by_threshold(df, "nonexistent", [40.0])

    def test_raises_on_wrong_category_names_count(self):
        df = self._make_measurements()
        with self.assertRaises(ValueError):
            categorize_by_threshold(df, "mean_intensity", [40.0], ["only_one"])

    def test_works_with_morphology_columns(self):
        df = pd.DataFrame({
            "index": [1, 2, 3],
            "area": [100.0, 200.0, 300.0],
        })
        result = categorize_by_threshold(df, "area", [150.0])
        self.assertEqual(result[result["area"] == 100.0].iloc[0]["category_id"], 1)
        self.assertEqual(result[result["area"] == 300.0].iloc[0]["category_id"], 2)

    def test_nan_rows_get_zero_category(self):
        """Rows with NaN in the chosen column (e.g. background padding) are
        not categorized: ``category_id=0`` and ``category_name=''``."""
        df = pd.DataFrame({
            "index": [0, 1, 2, 3],
            "mean_intensity": [float("nan"), 10.0, 30.0, 90.0],
        })
        result = categorize_by_threshold(df, "mean_intensity", [50.0])
        self.assertEqual(int(result.loc[0, "category_id"]), 0)
        self.assertEqual(result.loc[0, "category_name"], "")
        # Other rows are categorized normally.
        self.assertEqual(int(result.loc[1, "category_id"]), 1)
        self.assertEqual(int(result.loc[2, "category_id"]), 1)
        self.assertEqual(int(result.loc[3, "category_id"]), 2)


class TestAnalysisCLI(unittest.TestCase):

    def _call_main(self, argv):
        from segmentation_measurement._cli import main
        with patch("sys.argv", ["segmentation-measurement"] + argv):
            main()

    def test_threshold_cli_csv(self):
        df = pd.DataFrame({
            "index": [1, 2, 3, 4],
            "mean_intensity": [10.0, 30.0, 70.0, 90.0],
        })
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "measurements.csv")
            out_path = os.path.join(tmpdir, "categories.csv")
            df.to_csv(in_path, index=False)
            self._call_main([
                "analyze", "threshold",
                "--table", in_path,
                "--column", "mean_intensity",
                "--n-categories", "2",
                "--thresholds", "50.0",
                "--output", out_path,
            ])
            result = pd.read_csv(out_path)
            self.assertIn("category_id", result.columns)
            self.assertEqual(
                result[result["mean_intensity"] == 10.0].iloc[0]["category_id"], 1
            )
            self.assertEqual(
                result[result["mean_intensity"] == 90.0].iloc[0]["category_id"], 2
            )

    def test_threshold_cli_auto_suggest(self):
        df = pd.DataFrame({
            "index": [1, 2, 3, 4, 5, 6],
            "area": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
        })
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "morphology.csv")
            out_path = os.path.join(tmpdir, "categories.csv")
            df.to_csv(in_path, index=False)
            self._call_main([
                "analyze", "threshold",
                "--table", in_path,
                "--column", "area",
                "--n-categories", "3",
                "--output", out_path,
            ])
            result = pd.read_csv(out_path)
            self.assertIn("category_id", result.columns)
            self.assertEqual(len(result["category_id"].unique()), 3)

    def test_threshold_cli_with_segmentation_output(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[1:5, 1:5] = 1
        seg[5:9, 5:9] = 2
        df = pd.DataFrame({
            "index": [1, 2],
            "mean_intensity": [10.0, 90.0],
        })
        with tempfile.TemporaryDirectory() as tmpdir:
            seg_path = os.path.join(tmpdir, "seg.tif")
            in_path = os.path.join(tmpdir, "measurements.csv")
            out_path = os.path.join(tmpdir, "categories.csv")
            out_seg_path = os.path.join(tmpdir, "categories.tif")
            tifffile.imwrite(seg_path, seg)
            df.to_csv(in_path, index=False)
            self._call_main([
                "analyze", "threshold",
                "--table", in_path,
                "--column", "mean_intensity",
                "--n-categories", "2",
                "--thresholds", "50.0",
                "--output", out_path,
                "--segmentation", seg_path,
                "--output-segmentation", out_seg_path,
            ])
            import tifffile as tf
            out_seg = tf.imread(out_seg_path)
            self.assertTrue(np.all(out_seg[1:5, 1:5] == 1))
            self.assertTrue(np.all(out_seg[5:9, 5:9] == 2))


if __name__ == "__main__":
    unittest.main()
