"""Command line interface for segmentation-measurement."""

import argparse

import numpy as np
import tifffile


def _load_segmentation(path):
    return tifffile.imread(path)


def _save_segmentation(segmentation, path):
    tifffile.imwrite(path, segmentation)


def cmd_filter_small_segments(args):
    from segmentation_measurement.postprocessing import filter_small_segments
    seg = _load_segmentation(args.input)
    result = filter_small_segments(seg, args.min_size)
    _save_segmentation(result, args.output)


def cmd_remove_small_holes(args):
    from segmentation_measurement.postprocessing import remove_small_holes
    seg = _load_segmentation(args.input)
    result = remove_small_holes(seg, args.max_hole_size)
    _save_segmentation(result, args.output)


def cmd_ring_mask(args):
    from segmentation_measurement.postprocessing import compute_ring_mask
    seg = _load_segmentation(args.input)
    result = compute_ring_mask(seg, args.ring_width)
    _save_segmentation(result, args.output)


def main():
    parser = argparse.ArgumentParser(
        prog="segmentation-measurement",
        description="Post-processing and measurement utilities for instance segmentations.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    pp_parser = subparsers.add_parser("postprocess", help="Post-processing utilities.")
    pp_subparsers = pp_parser.add_subparsers(dest="subcommand")
    pp_subparsers.required = True

    fss = pp_subparsers.add_parser(
        "filter-small-segments",
        help="Remove segments below a size threshold.",
    )
    fss.add_argument("--input", required=True, help="Input segmentation file (TIFF).")
    fss.add_argument("--output", required=True, help="Output segmentation file (TIFF).")
    fss.add_argument(
        "--min-size", type=int, required=True,
        help="Minimum segment size in pixels/voxels. Segments smaller than this are removed.",
    )
    fss.set_defaults(func=cmd_filter_small_segments)

    rsh = pp_subparsers.add_parser(
        "remove-small-holes",
        help="Fill holes smaller than a size threshold.",
    )
    rsh.add_argument("--input", required=True, help="Input segmentation file (TIFF).")
    rsh.add_argument("--output", required=True, help="Output segmentation file (TIFF).")
    rsh.add_argument(
        "--max-hole-size", type=int, required=True,
        help="Maximum hole size in pixels/voxels to fill.",
    )
    rsh.set_defaults(func=cmd_remove_small_holes)

    rm = pp_subparsers.add_parser(
        "ring-mask",
        help="Compute ring mask around each segment.",
    )
    rm.add_argument("--input", required=True, help="Input segmentation file (TIFF).")
    rm.add_argument("--output", required=True, help="Output segmentation file (TIFF).")
    rm.add_argument(
        "--ring-width", type=int, required=True,
        help="Width of the ring in pixels/voxels.",
    )
    rm.set_defaults(func=cmd_ring_mask)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
