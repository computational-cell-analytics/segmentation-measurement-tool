"""Tests for clustering analysis functions and CLI."""

import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import tifffile

from segmentation_measurement.analysis import cluster_measurements


def _make_measurements(n: int = 20) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "index": np.arange(1, n + 1),
        "mean_intensity": rng.uniform(0, 100, n),
        "area": rng.uniform(10, 200, n),
    })


class TestClusterMeasurements(unittest.TestCase):

    def test_adds_cluster_id_column(self):
        df = _make_measurements()
        result = cluster_measurements(df, method="kmeans", n_clusters=3)
        self.assertIn("cluster_id", result.columns)

    def test_does_not_modify_input(self):
        df = _make_measurements()
        original_cols = list(df.columns)
        cluster_measurements(df, method="kmeans", n_clusters=3)
        self.assertEqual(list(df.columns), original_cols)

    def test_kmeans_returns_n_clusters(self):
        df = _make_measurements(30)
        result = cluster_measurements(df, method="kmeans", n_clusters=4)
        unique = set(result["cluster_id"].unique())
        self.assertEqual(len(unique), 4)

    def test_dbscan_assigns_cluster_ids(self):
        df = _make_measurements(20)
        result = cluster_measurements(df, method="dbscan", eps=2.0, min_samples=2)
        self.assertIn("cluster_id", result.columns)
        self.assertEqual(len(result), len(df))

    def test_hdbscan_assigns_cluster_ids(self):
        df = _make_measurements(20)
        result = cluster_measurements(df, method="hdbscan", min_cluster_size=3)
        self.assertIn("cluster_id", result.columns)

    def test_mean_shift_assigns_cluster_ids(self):
        df = _make_measurements(20)
        result = cluster_measurements(df, method="mean_shift")
        self.assertIn("cluster_id", result.columns)

    def test_excludes_label_from_features(self):
        df = pd.DataFrame({
            "index": np.arange(1, 21),
            "mean_intensity": np.linspace(0, 100, 20),
        })
        result = cluster_measurements(df, method="kmeans", n_clusters=2)
        self.assertIn("cluster_id", result.columns)

    def test_excludes_existing_cluster_id_from_features(self):
        df = _make_measurements(20)
        result1 = cluster_measurements(df, method="kmeans", n_clusters=2)
        result2 = cluster_measurements(result1, method="kmeans", n_clusters=3)
        unique = set(result2["cluster_id"].unique())
        self.assertEqual(len(unique), 3)

    def test_raises_on_unknown_method(self):
        df = _make_measurements()
        with self.assertRaises(ValueError):
            cluster_measurements(df, method="unknown_method")

    def test_raises_when_no_feature_columns(self):
        df = pd.DataFrame({"index": [1, 2, 3]})
        with self.assertRaises(ValueError):
            cluster_measurements(df, method="kmeans")

    def test_label_column_preserved(self):
        df = _make_measurements()
        result = cluster_measurements(df, method="kmeans", n_clusters=2)
        pd.testing.assert_series_equal(result["index"], df["index"])

    def test_cluster_ids_are_integers(self):
        df = _make_measurements()
        result = cluster_measurements(df, method="kmeans", n_clusters=3)
        self.assertTrue(np.issubdtype(result["cluster_id"].dtype, np.integer))

    def test_kmeans_cluster_ids_are_one_based(self):
        df = _make_measurements(30)
        result = cluster_measurements(df, method="kmeans", n_clusters=3)
        unique = sorted(result["cluster_id"].unique())
        self.assertEqual(min(unique), 1)
        self.assertEqual(max(unique), 3)

    def test_dbscan_noise_is_minus_one(self):
        # Use settings that reliably produce noise points
        df = pd.DataFrame({
            "index": np.arange(1, 11),
            "feat": [0., 0.01, 50., 50.01, 100., 0.02, 50.02, 100.01, 200., 300.],
        })
        result = cluster_measurements(df, method="dbscan", eps=0.1, min_samples=2)
        # Noise points exist and are -1; non-noise points are >= 1
        self.assertIn(-1, result["cluster_id"].values)
        non_noise = result[result["cluster_id"] != -1]["cluster_id"].values
        self.assertTrue(np.all(non_noise >= 1))

    def test_method_aliases(self):
        df = _make_measurements(20)
        for alias in ("kmeans", "k_means", "k-means"):
            result = cluster_measurements(df, method=alias, n_clusters=2)
            self.assertIn("cluster_id", result.columns)

    def test_handles_nan_in_features(self):
        df = _make_measurements(20)
        df.loc[0, "mean_intensity"] = np.nan
        result = cluster_measurements(df, method="kmeans", n_clusters=2)
        self.assertIn("cluster_id", result.columns)
        self.assertEqual(len(result), len(df))


class TestClusteringCLI(unittest.TestCase):

    def _call_main(self, argv):
        from segmentation_measurement._cli import main
        with patch("sys.argv", ["segmentation-measurement"] + argv):
            main()

    def test_cluster_cli_kmeans_csv(self):
        df = _make_measurements(20)
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "measurements.csv")
            out_path = os.path.join(tmpdir, "clusters.csv")
            df.to_csv(in_path, index=False)
            self._call_main([
                "analyze", "cluster",
                "--table", in_path,
                "--method", "kmeans",
                "--n-clusters", "3",
                "--output", out_path,
            ])
            result = pd.read_csv(out_path)
            self.assertIn("cluster_id", result.columns)
            self.assertEqual(len(result["cluster_id"].unique()), 3)

    def test_cluster_cli_dbscan(self):
        df = _make_measurements(20)
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "measurements.csv")
            out_path = os.path.join(tmpdir, "clusters.csv")
            df.to_csv(in_path, index=False)
            self._call_main([
                "analyze", "cluster",
                "--table", in_path,
                "--method", "dbscan",
                "--eps", "2.0",
                "--min-samples", "2",
                "--output", out_path,
            ])
            result = pd.read_csv(out_path)
            self.assertIn("cluster_id", result.columns)

    def test_cluster_cli_hdbscan(self):
        df = _make_measurements(30)
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "measurements.csv")
            out_path = os.path.join(tmpdir, "clusters.csv")
            df.to_csv(in_path, index=False)
            self._call_main([
                "analyze", "cluster",
                "--table", in_path,
                "--method", "hdbscan",
                "--min-cluster-size", "3",
                "--output", out_path,
            ])
            result = pd.read_csv(out_path)
            self.assertIn("cluster_id", result.columns)

    def test_cluster_cli_with_segmentation_output(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[1:6, 1:6] = 1
        seg[7:12, 7:12] = 2
        seg[13:18, 13:18] = 3
        df = pd.DataFrame({
            "index": [1, 2, 3],
            "mean_intensity": [10.0, 50.0, 90.0],
        })
        with tempfile.TemporaryDirectory() as tmpdir:
            seg_path = os.path.join(tmpdir, "seg.tif")
            in_path = os.path.join(tmpdir, "measurements.csv")
            out_path = os.path.join(tmpdir, "clusters.csv")
            out_seg_path = os.path.join(tmpdir, "clusters.tif")
            tifffile.imwrite(seg_path, seg)
            df.to_csv(in_path, index=False)
            self._call_main([
                "analyze", "cluster",
                "--table", in_path,
                "--method", "kmeans",
                "--n-clusters", "2",
                "--output", out_path,
                "--segmentation", seg_path,
                "--output-segmentation", out_seg_path,
            ])
            out_seg = tifffile.imread(out_seg_path)
            # Each labelled region gets cluster_id + 1 (so > 0)
            self.assertTrue(np.all(out_seg[1:6, 1:6] > 0))
            self.assertTrue(np.all(out_seg[7:12, 7:12] > 0))
            # Background stays 0
            self.assertEqual(out_seg[0, 0], 0)

    def test_cluster_cli_default_method_is_kmeans(self):
        df = _make_measurements(20)
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "measurements.csv")
            out_path = os.path.join(tmpdir, "clusters.csv")
            df.to_csv(in_path, index=False)
            self._call_main([
                "analyze", "cluster",
                "--table", in_path,
                "--output", out_path,
            ])
            result = pd.read_csv(out_path)
            self.assertIn("cluster_id", result.columns)

    def test_cluster_cli_tsv_output(self):
        df = _make_measurements(20)
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "measurements.csv")
            out_path = os.path.join(tmpdir, "clusters.tsv")
            df.to_csv(in_path, index=False)
            self._call_main([
                "analyze", "cluster",
                "--table", in_path,
                "--output", out_path,
            ])
            result = pd.read_csv(out_path, sep="\t")
            self.assertIn("cluster_id", result.columns)


if __name__ == "__main__":
    unittest.main()
