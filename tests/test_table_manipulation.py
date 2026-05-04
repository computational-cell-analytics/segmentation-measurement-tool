"""Tests for table manipulation functions and CLI."""

import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from segmentation_measurement.table_manipulation import (
    drop_columns,
    merge_tables,
)
from segmentation_measurement._utils import save_table


class TestMergeTables(unittest.TestCase):

    def test_merge_two_disjoint_tables(self):
        a = pd.DataFrame({"label": [1, 2, 3], "mean_intensity": [10.0, 20.0, 30.0]})
        b = pd.DataFrame({"label": [1, 2, 3], "area": [100, 200, 300]})
        result = merge_tables([a, b])
        self.assertEqual(set(result.columns), {"label", "mean_intensity", "area"})
        self.assertEqual(len(result), 3)
        np.testing.assert_array_equal(result["label"].values, [1, 2, 3])
        np.testing.assert_array_equal(result["mean_intensity"].values, [10.0, 20.0, 30.0])
        np.testing.assert_array_equal(result["area"].values, [100, 200, 300])

    def test_outer_join_preserves_unmatched_labels(self):
        a = pd.DataFrame({"label": [1, 2], "mean_intensity": [10.0, 20.0]})
        b = pd.DataFrame({"label": [2, 3], "area": [200, 300]})
        result = merge_tables([a, b])
        self.assertEqual(len(result), 3)
        np.testing.assert_array_equal(result["label"].values, [1, 2, 3])
        # label 1 has no area, label 3 has no mean_intensity
        self.assertTrue(np.isnan(result.loc[result["label"] == 1, "area"].iloc[0]))
        self.assertTrue(
            np.isnan(result.loc[result["label"] == 3, "mean_intensity"].iloc[0])
        )

    def test_merge_three_tables(self):
        a = pd.DataFrame({"label": [1, 2], "x": [1.0, 2.0]})
        b = pd.DataFrame({"label": [1, 2], "y": [3.0, 4.0]})
        c = pd.DataFrame({"label": [1, 2], "z": [5.0, 6.0]})
        result = merge_tables([a, b, c])
        self.assertEqual(set(result.columns), {"label", "x", "y", "z"})
        self.assertEqual(len(result), 2)

    def test_overlapping_columns_raise(self):
        a = pd.DataFrame({"label": [1], "shared": [1.0]})
        b = pd.DataFrame({"label": [1], "shared": [2.0]})
        with self.assertRaises(ValueError):
            merge_tables([a, b])

    def test_missing_key_column_raises(self):
        a = pd.DataFrame({"label": [1], "x": [1.0]})
        b = pd.DataFrame({"id": [1], "y": [2.0]})
        with self.assertRaises(ValueError):
            merge_tables([a, b])

    def test_single_table_raises(self):
        a = pd.DataFrame({"label": [1], "x": [1.0]})
        with self.assertRaises(ValueError):
            merge_tables([a])

    def test_custom_key_column(self):
        a = pd.DataFrame({"id": [1, 2], "x": [1.0, 2.0]})
        b = pd.DataFrame({"id": [1, 2], "y": [3.0, 4.0]})
        result = merge_tables([a, b], on="id")
        self.assertEqual(set(result.columns), {"id", "x", "y"})


class TestDropColumns(unittest.TestCase):

    def test_drop_single_column_by_string(self):
        df = pd.DataFrame({"label": [1], "a": [1.0], "b": [2.0]})
        result = drop_columns(df, "a")
        self.assertEqual(set(result.columns), {"label", "b"})

    def test_drop_multiple_columns_by_list(self):
        df = pd.DataFrame({"label": [1], "a": [1.0], "b": [2.0], "c": [3.0]})
        result = drop_columns(df, ["a", "c"])
        self.assertEqual(set(result.columns), {"label", "b"})

    def test_drop_missing_column_raises(self):
        df = pd.DataFrame({"label": [1], "a": [1.0]})
        with self.assertRaises(ValueError):
            drop_columns(df, "nope")

    def test_drop_label_column_raises(self):
        df = pd.DataFrame({"label": [1, 2], "a": [1.0, 2.0]})
        with self.assertRaises(ValueError):
            drop_columns(df, "label")

    def test_drop_label_among_others_raises(self):
        df = pd.DataFrame({"label": [1, 2], "a": [1.0, 2.0], "b": [3.0, 4.0]})
        with self.assertRaises(ValueError):
            drop_columns(df, ["a", "label"])
        # Original frame untouched
        self.assertIn("label", df.columns)
        self.assertIn("a", df.columns)

    def test_does_not_modify_input(self):
        df = pd.DataFrame({"label": [1], "a": [1.0]})
        drop_columns(df, "a")
        self.assertIn("a", df.columns)


class TestCLI(unittest.TestCase):

    def _call_main(self, argv):
        from segmentation_measurement._cli import main
        with patch("sys.argv", ["segmentation-measurement"] + argv):
            main()

    def test_table_merge_cli(self):
        a = pd.DataFrame({"label": [1, 2], "mean_intensity": [10.0, 20.0]})
        b = pd.DataFrame({"label": [1, 2], "area": [100, 200]})
        with tempfile.TemporaryDirectory() as tmpdir:
            a_path = os.path.join(tmpdir, "a.csv")
            b_path = os.path.join(tmpdir, "b.csv")
            out_path = os.path.join(tmpdir, "out.csv")
            save_table(a, a_path)
            save_table(b, b_path)
            self._call_main([
                "table", "merge",
                "--inputs", a_path, b_path,
                "--output", out_path,
            ])
            result = pd.read_csv(out_path)
            self.assertEqual(set(result.columns), {"label", "mean_intensity", "area"})
            self.assertEqual(len(result), 2)

    def test_table_merge_cli_with_drop_columns(self):
        a = pd.DataFrame({"label": [1, 2], "mean_intensity": [10.0, 20.0], "extra": [1, 2]})
        b = pd.DataFrame({"label": [1, 2], "area": [100, 200]})
        with tempfile.TemporaryDirectory() as tmpdir:
            a_path = os.path.join(tmpdir, "a.csv")
            b_path = os.path.join(tmpdir, "b.csv")
            out_path = os.path.join(tmpdir, "out.csv")
            save_table(a, a_path)
            save_table(b, b_path)
            self._call_main([
                "table", "merge",
                "--inputs", a_path, b_path,
                "--output", out_path,
                "--drop-columns", "extra",
            ])
            result = pd.read_csv(out_path)
            self.assertEqual(set(result.columns), {"label", "mean_intensity", "area"})

    def test_table_merge_cli_single_input_with_drop(self):
        a = pd.DataFrame({"label": [1, 2], "x": [1.0, 2.0], "y": [3.0, 4.0]})
        with tempfile.TemporaryDirectory() as tmpdir:
            a_path = os.path.join(tmpdir, "a.csv")
            out_path = os.path.join(tmpdir, "out.csv")
            save_table(a, a_path)
            self._call_main([
                "table", "merge",
                "--inputs", a_path,
                "--output", out_path,
                "--drop-columns", "y",
            ])
            result = pd.read_csv(out_path)
            self.assertEqual(set(result.columns), {"label", "x"})


if __name__ == "__main__":
    unittest.main()
