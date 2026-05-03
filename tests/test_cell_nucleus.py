"""Tests for cell-nucleus measurement function and CLI."""

import math
import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import tifffile

from segmentation_measurement.cell_nucleus import measure_cell_nucleus


def _make_2d_data(with_intensity=False):
    """Two cells; cell 1 contains nucleus 1, cell 2 has no nucleus."""
    cell_seg = np.zeros((30, 30), dtype=np.int32)
    cell_seg[2:14, 2:14] = 1   # 12x12 = 144 px
    cell_seg[16:26, 16:26] = 2  # 10x10 = 100 px

    nuc_seg = np.zeros((30, 30), dtype=np.int32)
    nuc_seg[5:10, 5:10] = 1    # 5x5 = 25 px, inside cell 1

    if not with_intensity:
        return cell_seg, nuc_seg

    intensity = np.zeros((30, 30), dtype=np.float32)
    intensity[2:14, 2:14] = 10.0   # cell 1 region (includes nucleus)
    intensity[5:10, 5:10] = 20.0   # nucleus overrides
    return cell_seg, nuc_seg, intensity


def _make_3d_data():
    cell_seg = np.zeros((20, 20, 20), dtype=np.int32)
    cell_seg[2:12, 2:12, 2:12] = 1  # 10^3 = 1000 vx
    nuc_seg = np.zeros((20, 20, 20), dtype=np.int32)
    nuc_seg[4:8, 4:8, 4:8] = 1      # 4^3 = 64 vx, inside cell 1
    return cell_seg, nuc_seg


class TestMeasureCellNucleus2D(unittest.TestCase):

    def test_returns_dataframe(self):
        cell_seg, nuc_seg = _make_2d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        self.assertIsInstance(result, pd.DataFrame)

    def test_one_row_per_cell(self):
        cell_seg, nuc_seg = _make_2d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        self.assertEqual(len(result), 2)
        self.assertSetEqual(set(result["label"]), {1, 2})

    def test_required_columns_2d_no_intensity(self):
        cell_seg, nuc_seg = _make_2d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        for col in ["label", "n_nuclei", "cell_area", "nucleus_area", "area_ratio"]:
            self.assertIn(col, result.columns)
        self.assertNotIn("cell_mean_intensity", result.columns)

    def test_required_columns_with_intensity(self):
        cell_seg, nuc_seg, intensity = _make_2d_data(with_intensity=True)
        result = measure_cell_nucleus(cell_seg, nuc_seg, intensity_image=intensity)
        for col in [
            "label", "n_nuclei", "cell_area", "nucleus_area", "area_ratio",
            "cell_mean_intensity", "nucleus_mean_intensity", "mean_intensity_ratio",
            "cell_percentile_10_intensity", "nucleus_percentile_90_intensity",
        ]:
            self.assertIn(col, result.columns)

    def test_n_nuclei_correct(self):
        cell_seg, nuc_seg = _make_2d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        row1 = result[result["label"] == 1].iloc[0]
        row2 = result[result["label"] == 2].iloc[0]
        self.assertEqual(row1["n_nuclei"], 1)
        self.assertEqual(row2["n_nuclei"], 0)

    def test_cell_area_correct(self):
        cell_seg, nuc_seg = _make_2d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        row1 = result[result["label"] == 1].iloc[0]
        self.assertAlmostEqual(row1["cell_area"], 144.0, places=1)

    def test_nucleus_area_correct(self):
        cell_seg, nuc_seg = _make_2d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        row1 = result[result["label"] == 1].iloc[0]
        self.assertAlmostEqual(row1["nucleus_area"], 25.0, places=1)

    def test_area_ratio_correct(self):
        cell_seg, nuc_seg = _make_2d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        row1 = result[result["label"] == 1].iloc[0]
        self.assertAlmostEqual(row1["area_ratio"], 144.0 / 25.0, places=4)

    def test_area_ratio_nan_when_no_nucleus(self):
        cell_seg, nuc_seg = _make_2d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        row2 = result[result["label"] == 2].iloc[0]
        self.assertTrue(math.isnan(row2["area_ratio"]))

    def test_isotropic_scale_applied(self):
        cell_seg, nuc_seg = _make_2d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg, scale=0.5)
        row1 = result[result["label"] == 1].iloc[0]
        self.assertAlmostEqual(row1["cell_area"], 144.0 * 0.25, places=4)
        self.assertAlmostEqual(row1["nucleus_area"], 25.0 * 0.25, places=4)

    def test_anisotropic_scale_applied(self):
        cell_seg, nuc_seg = _make_2d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg, scale=(2.0, 1.0))
        row1 = result[result["label"] == 1].iloc[0]
        self.assertAlmostEqual(row1["cell_area"], 144.0 * 2.0, places=4)

    def test_intensity_cell_excludes_nucleus(self):
        cell_seg, nuc_seg, intensity = _make_2d_data(with_intensity=True)
        result = measure_cell_nucleus(cell_seg, nuc_seg, intensity_image=intensity)
        row1 = result[result["label"] == 1].iloc[0]
        # Cytoplasm pixels = 144 - 25 = 119 px, all have value 10.0
        self.assertAlmostEqual(row1["cell_mean_intensity"], 10.0, places=4)

    def test_intensity_nucleus_value(self):
        cell_seg, nuc_seg, intensity = _make_2d_data(with_intensity=True)
        result = measure_cell_nucleus(cell_seg, nuc_seg, intensity_image=intensity)
        row1 = result[result["label"] == 1].iloc[0]
        # Nucleus pixels all have value 20.0
        self.assertAlmostEqual(row1["nucleus_mean_intensity"], 20.0, places=4)

    def test_intensity_ratio_correct(self):
        cell_seg, nuc_seg, intensity = _make_2d_data(with_intensity=True)
        result = measure_cell_nucleus(cell_seg, nuc_seg, intensity_image=intensity)
        row1 = result[result["label"] == 1].iloc[0]
        # 10.0 / 20.0 = 0.5
        self.assertAlmostEqual(row1["mean_intensity_ratio"], 0.5, places=4)

    def test_intensity_nan_when_no_nucleus(self):
        cell_seg, nuc_seg, intensity = _make_2d_data(with_intensity=True)
        result = measure_cell_nucleus(cell_seg, nuc_seg, intensity_image=intensity)
        row2 = result[result["label"] == 2].iloc[0]
        self.assertTrue(math.isnan(row2["nucleus_mean_intensity"]))
        self.assertTrue(math.isnan(row2["mean_intensity_ratio"]))

    def test_empty_cell_segmentation(self):
        cell_seg = np.zeros((10, 10), dtype=np.int32)
        nuc_seg = np.zeros((10, 10), dtype=np.int32)
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        self.assertEqual(len(result), 0)
        self.assertIn("label", result.columns)
        self.assertIn("n_nuclei", result.columns)


class TestMeasureCellNucleus3D(unittest.TestCase):

    def test_returns_dataframe_3d(self):
        cell_seg, nuc_seg = _make_3d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        self.assertIsInstance(result, pd.DataFrame)

    def test_required_columns_3d(self):
        cell_seg, nuc_seg = _make_3d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        for col in ["label", "n_nuclei", "cell_volume", "nucleus_volume", "volume_ratio"]:
            self.assertIn(col, result.columns)
        self.assertNotIn("cell_area", result.columns)

    def test_cell_volume_correct(self):
        cell_seg, nuc_seg = _make_3d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        self.assertAlmostEqual(result.iloc[0]["cell_volume"], 1000.0, places=1)

    def test_nucleus_volume_correct(self):
        cell_seg, nuc_seg = _make_3d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        self.assertAlmostEqual(result.iloc[0]["nucleus_volume"], 64.0, places=1)

    def test_volume_ratio_correct(self):
        cell_seg, nuc_seg = _make_3d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        self.assertAlmostEqual(result.iloc[0]["volume_ratio"], 1000.0 / 64.0, places=3)

    def test_3d_scale_applied(self):
        cell_seg, nuc_seg = _make_3d_data()
        result = measure_cell_nucleus(cell_seg, nuc_seg, scale=0.5)
        self.assertAlmostEqual(result.iloc[0]["cell_volume"], 1000.0 * 0.125, places=4)


class TestMeasureCellNucleusValidation(unittest.TestCase):

    def test_raises_on_1d(self):
        with self.assertRaises(ValueError):
            measure_cell_nucleus(
                np.zeros(10, dtype=np.int32),
                np.zeros(10, dtype=np.int32),
            )

    def test_raises_on_4d(self):
        with self.assertRaises(ValueError):
            measure_cell_nucleus(
                np.zeros((2, 2, 2, 2), dtype=np.int32),
                np.zeros((2, 2, 2, 2), dtype=np.int32),
            )

    def test_raises_on_shape_mismatch(self):
        with self.assertRaises(ValueError):
            measure_cell_nucleus(
                np.zeros((10, 10), dtype=np.int32),
                np.zeros((10, 12), dtype=np.int32),
            )

    def test_raises_on_intensity_shape_mismatch(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[2:8, 2:8] = 1
        nuc = np.zeros((10, 10), dtype=np.int32)
        with self.assertRaises(ValueError):
            measure_cell_nucleus(seg, nuc, intensity_image=np.zeros((10, 12)))

    def test_raises_on_wrong_scale_length(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        with self.assertRaises(ValueError):
            measure_cell_nucleus(seg, seg, scale=(1.0, 1.0, 1.0))

    def test_multiple_nuclei_per_cell(self):
        cell_seg = np.zeros((20, 20), dtype=np.int32)
        cell_seg[2:18, 2:18] = 1
        nuc_seg = np.zeros((20, 20), dtype=np.int32)
        nuc_seg[3:7, 3:7] = 1
        nuc_seg[10:14, 10:14] = 2
        result = measure_cell_nucleus(cell_seg, nuc_seg)
        self.assertEqual(result.iloc[0]["n_nuclei"], 2)
        # nucleus_area = 4*4 + 4*4 = 32
        self.assertAlmostEqual(result.iloc[0]["nucleus_area"], 32.0, places=1)


class TestCellNucleusCLI(unittest.TestCase):

    def _call_main(self, argv):
        from segmentation_measurement._cli import main
        with patch("sys.argv", ["segmentation-measurement"] + argv):
            main()

    def test_cli_csv_no_intensity(self):
        cell_seg, nuc_seg = _make_2d_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            cell_path = os.path.join(tmpdir, "cell.tif")
            nuc_path = os.path.join(tmpdir, "nuc.tif")
            out_path = os.path.join(tmpdir, "result.csv")
            tifffile.imwrite(cell_path, cell_seg)
            tifffile.imwrite(nuc_path, nuc_seg)
            self._call_main([
                "measure", "cell-nucleus",
                "--cell-segmentation", cell_path,
                "--nucleus-segmentation", nuc_path,
                "--output", out_path,
            ])
            df = pd.read_csv(out_path)
            self.assertEqual(len(df), 2)
            self.assertIn("n_nuclei", df.columns)
            self.assertIn("cell_area", df.columns)
            self.assertNotIn("cell_mean_intensity", df.columns)

    def test_cli_with_intensity(self):
        cell_seg, nuc_seg, intensity = _make_2d_data(with_intensity=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            cell_path = os.path.join(tmpdir, "cell.tif")
            nuc_path = os.path.join(tmpdir, "nuc.tif")
            int_path = os.path.join(tmpdir, "intensity.tif")
            out_path = os.path.join(tmpdir, "result.csv")
            tifffile.imwrite(cell_path, cell_seg)
            tifffile.imwrite(nuc_path, nuc_seg)
            tifffile.imwrite(int_path, intensity)
            self._call_main([
                "measure", "cell-nucleus",
                "--cell-segmentation", cell_path,
                "--nucleus-segmentation", nuc_path,
                "--output", out_path,
                "--intensity", int_path,
            ])
            df = pd.read_csv(out_path)
            self.assertIn("cell_mean_intensity", df.columns)
            self.assertIn("mean_intensity_ratio", df.columns)

    def test_cli_scale(self):
        cell_seg, nuc_seg = _make_2d_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            cell_path = os.path.join(tmpdir, "cell.tif")
            nuc_path = os.path.join(tmpdir, "nuc.tif")
            out_path = os.path.join(tmpdir, "result.csv")
            tifffile.imwrite(cell_path, cell_seg)
            tifffile.imwrite(nuc_path, nuc_seg)
            self._call_main([
                "measure", "cell-nucleus",
                "--cell-segmentation", cell_path,
                "--nucleus-segmentation", nuc_path,
                "--output", out_path,
                "--scale", "0.5",
            ])
            df = pd.read_csv(out_path)
            row1 = df[df["label"] == 1].iloc[0]
            self.assertAlmostEqual(row1["cell_area"], 144.0 * 0.25, places=2)

    def test_cli_tsv_output(self):
        cell_seg, nuc_seg = _make_2d_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            cell_path = os.path.join(tmpdir, "cell.tif")
            nuc_path = os.path.join(tmpdir, "nuc.tif")
            out_path = os.path.join(tmpdir, "result.tsv")
            tifffile.imwrite(cell_path, cell_seg)
            tifffile.imwrite(nuc_path, nuc_seg)
            self._call_main([
                "measure", "cell-nucleus",
                "--cell-segmentation", cell_path,
                "--nucleus-segmentation", nuc_path,
                "--output", out_path,
            ])
            df = pd.read_csv(out_path, sep="\t")
            self.assertEqual(len(df), 2)


if __name__ == "__main__":
    unittest.main()
