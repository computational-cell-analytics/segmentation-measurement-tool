"""Tests for post-processing functions and CLI."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import tifffile

from segmentation_measurement.postprocessing import (
    compute_ring_mask,
    filter_small_segments,
    remove_small_holes,
)


class TestFilterSmallSegments(unittest.TestCase):

    def test_removes_small_segment_2d(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[0:3, 0:3] = 1  # 9 pixels
        seg[5:6, 5:6] = 2  # 1 pixel
        result = filter_small_segments(seg, min_size=5)
        np.testing.assert_array_equal(result[0:3, 0:3], 1)
        np.testing.assert_array_equal(result[5:6, 5:6], 0)

    def test_removes_small_segment_3d(self):
        seg = np.zeros((10, 10, 10), dtype=np.int32)
        seg[0:3, 0:3, 0:3] = 1  # 27 voxels
        seg[5:6, 5:6, 5:6] = 2  # 1 voxel
        result = filter_small_segments(seg, min_size=10)
        np.testing.assert_array_equal(result[0:3, 0:3, 0:3], 1)
        np.testing.assert_array_equal(result[5:6, 5:6, 5:6], 0)

    def test_preserves_segment_at_threshold(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[0:5, 0:5] = 1  # 25 pixels
        result = filter_small_segments(seg, min_size=25)
        np.testing.assert_array_equal(result, seg)

    def test_removes_segment_below_threshold(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[0:4, 0:4] = 1  # 16 pixels
        result = filter_small_segments(seg, min_size=17)
        np.testing.assert_array_equal(result, np.zeros_like(seg))

    def test_preserves_dtype(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[0:2, 0:2] = 1
        result = filter_small_segments(seg, min_size=100)
        self.assertEqual(result.dtype, seg.dtype)

    def test_background_unchanged(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[0:2, 0:2] = 1
        result = filter_small_segments(seg, min_size=100)
        np.testing.assert_array_equal(result[2:, 2:], 0)


class TestRemoveSmallHoles(unittest.TestCase):

    def test_fills_small_hole_2d(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[1:9, 1:9] = 1
        seg[4:6, 4:6] = 0  # 4-pixel hole
        result = remove_small_holes(seg, max_hole_size=10)
        np.testing.assert_array_equal(result[4:6, 4:6], 1)

    def test_preserves_large_hole_2d(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[1:19, 1:19] = 1
        seg[3:17, 3:17] = 0  # 196-pixel hole
        result = remove_small_holes(seg, max_hole_size=10)
        self.assertTrue(np.any(result[3:17, 3:17] == 0))

    def test_fills_small_hole_3d(self):
        seg = np.zeros((10, 10, 10), dtype=np.int32)
        seg[1:9, 1:9, 1:9] = 1
        seg[4:6, 4:6, 4:6] = 0  # 8-voxel hole
        result = remove_small_holes(seg, max_hole_size=20)
        np.testing.assert_array_equal(result[4:6, 4:6, 4:6], 1)

    def test_does_not_overwrite_other_segments(self):
        seg = np.zeros((15, 15), dtype=np.int32)
        seg[1:14, 1:14] = 1
        seg[5:10, 5:10] = 2  # inner segment, not a hole
        result = remove_small_holes(seg, max_hole_size=100)
        np.testing.assert_array_equal(result[5:10, 5:10], 2)

    def test_preserves_dtype(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[1:9, 1:9] = 1
        result = remove_small_holes(seg, max_hole_size=10)
        self.assertEqual(result.dtype, seg.dtype)


class TestComputeRingMask(unittest.TestCase):

    def test_ring_exists_around_segment_2d(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[8:12, 8:12] = 1  # 4x4 segment in center
        result = compute_ring_mask(seg, ring_width=2)
        # Original segment pixels must be absent from the ring mask
        np.testing.assert_array_equal(result[8:12, 8:12], 0)
        # Ring pixels should surround the segment
        self.assertTrue(np.any(result[5:8, 8:12] == 1))
        self.assertTrue(np.any(result[12:15, 8:12] == 1))

    def test_ring_only_covers_background(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[2:8, 2:8] = 1
        seg[10:16, 10:16] = 2
        result = compute_ring_mask(seg, ring_width=3)
        # Original segment pixels must be absent (ring mask only)
        np.testing.assert_array_equal(result[2:8, 2:8], 0)
        np.testing.assert_array_equal(result[10:16, 10:16], 0)
        # Every labeled pixel in the result must have been background originally
        self.assertTrue(np.all(seg[result > 0] == 0))

    def test_ring_3d(self):
        seg = np.zeros((20, 20, 20), dtype=np.int32)
        seg[8:12, 8:12, 8:12] = 1
        result = compute_ring_mask(seg, ring_width=2)
        # Original segment pixels must be absent from the ring mask
        np.testing.assert_array_equal(result[8:12, 8:12, 8:12], 0)
        # Ring pixels should exist outside the original segment
        self.assertTrue(np.any(result == 1))

    def test_preserves_dtype(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[3:7, 3:7] = 1
        result = compute_ring_mask(seg, ring_width=1)
        self.assertEqual(result.dtype, seg.dtype)

    def test_smaller_label_takes_precedence_in_overlap(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[5:9, 9:11] = 1
        seg[11:15, 9:11] = 2
        result = compute_ring_mask(seg, ring_width=3)
        # Where ring from label 1 and ring from label 2 would overlap,
        # label 1 (smaller) should take precedence.
        overlap_zone = result[9:11, 9:11]
        self.assertTrue(np.all(overlap_zone != 2))


class TestCLI(unittest.TestCase):

    def _call_main(self, argv):
        from segmentation_measurement._cli import main
        with patch("sys.argv", ["segmentation-measurement"] + argv):
            main()

    def test_filter_small_segments_cli(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[0:3, 0:3] = 1  # 9 pixels
        seg[5:6, 5:6] = 2  # 1 pixel
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "seg.tif")
            output_path = os.path.join(tmpdir, "out.tif")
            tifffile.imwrite(input_path, seg)
            self._call_main([
                "postprocess", "filter-small-segments",
                "--input", input_path,
                "--output", output_path,
                "--min-size", "5",
            ])
            out = tifffile.imread(output_path)
            np.testing.assert_array_equal(out[0:3, 0:3], 1)
            np.testing.assert_array_equal(out[5:6, 5:6], 0)

    def test_remove_small_holes_cli(self):
        seg = np.zeros((10, 10), dtype=np.int32)
        seg[1:9, 1:9] = 1
        seg[4:6, 4:6] = 0
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "seg.tif")
            output_path = os.path.join(tmpdir, "out.tif")
            tifffile.imwrite(input_path, seg)
            self._call_main([
                "postprocess", "remove-small-holes",
                "--input", input_path,
                "--output", output_path,
                "--max-hole-size", "10",
            ])
            out = tifffile.imread(output_path)
            np.testing.assert_array_equal(out[4:6, 4:6], 1)

    def test_ring_mask_cli(self):
        seg = np.zeros((20, 20), dtype=np.int32)
        seg[8:12, 8:12] = 1
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "seg.tif")
            output_path = os.path.join(tmpdir, "out.tif")
            tifffile.imwrite(input_path, seg)
            self._call_main([
                "postprocess", "ring-mask",
                "--input", input_path,
                "--output", output_path,
                "--ring-width", "2",
            ])
            out = tifffile.imread(output_path)
            # Original segment pixels absent; ring pixels present outside them
            np.testing.assert_array_equal(out[8:12, 8:12], 0)
            self.assertTrue(np.any(out == 1))


if __name__ == "__main__":
    unittest.main()
