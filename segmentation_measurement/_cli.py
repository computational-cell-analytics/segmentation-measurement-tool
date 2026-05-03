"""Command line interface for segmentation-measurement."""

from __future__ import annotations

import argparse

import numpy as np
import tifffile

from segmentation_measurement._utils import load_table, save_table


def _load_segmentation(path: str) -> np.ndarray:
    return tifffile.imread(path)


def _save_segmentation(segmentation: np.ndarray, path: str) -> None:
    tifffile.imwrite(path, segmentation)


def cmd_filter_small_segments(args: argparse.Namespace) -> None:
    """Execute the filter-small-segments sub-command."""
    from segmentation_measurement.postprocessing import filter_small_segments
    seg = _load_segmentation(args.input)
    result = filter_small_segments(seg, args.min_size)
    _save_segmentation(result, args.output)


def cmd_remove_small_holes(args: argparse.Namespace) -> None:
    """Execute the remove-small-holes sub-command."""
    from segmentation_measurement.postprocessing import remove_small_holes
    seg = _load_segmentation(args.input)
    result = remove_small_holes(seg, args.max_hole_size)
    _save_segmentation(result, args.output)


def cmd_ring_mask(args: argparse.Namespace) -> None:
    """Execute the ring-mask sub-command."""
    from segmentation_measurement.postprocessing import compute_ring_mask
    seg = _load_segmentation(args.input)
    result = compute_ring_mask(seg, args.ring_width)
    _save_segmentation(result, args.output)


def cmd_measure_intensities(args: argparse.Namespace) -> None:
    """Execute the measure-intensities sub-command."""
    from segmentation_measurement.intensity import measure_intensities
    seg = _load_segmentation(args.segmentation)
    intensity = tifffile.imread(args.intensity)
    df = measure_intensities(seg, intensity)
    save_table(df, args.output)


def cmd_measure_morphology(args: argparse.Namespace) -> None:
    """Execute the measure-morphology sub-command."""
    from segmentation_measurement.morphology import measure_morphology
    seg = _load_segmentation(args.segmentation)
    scale = tuple(args.scale) if len(args.scale) > 1 else args.scale[0]
    df = measure_morphology(seg, scale=scale)
    save_table(df, args.output)


def cmd_measure_cell_nucleus(args: argparse.Namespace) -> None:
    """Execute the measure-cell-nucleus sub-command."""
    from segmentation_measurement.cell_nucleus import measure_cell_nucleus
    cell_seg = _load_segmentation(args.cell_segmentation)
    nuc_seg = _load_segmentation(args.nucleus_segmentation)
    intensity = tifffile.imread(args.intensity) if args.intensity else None
    scale = tuple(args.scale) if len(args.scale) > 1 else args.scale[0]
    df = measure_cell_nucleus(cell_seg, nuc_seg, scale=scale, intensity_image=intensity)
    save_table(df, args.output)


def cmd_analyze_threshold(args: argparse.Namespace) -> None:
    """Execute the analyze-threshold sub-command."""
    from segmentation_measurement.analysis import (
        categorize_by_threshold,
        suggest_thresholds,
    )
    df = load_table(args.table)
    thresholds = (
        list(args.thresholds)
        if args.thresholds
        else suggest_thresholds(df, args.column, args.n_categories)
    )
    names = list(args.category_names) if args.category_names else None
    result = categorize_by_threshold(df, args.column, thresholds, names)
    save_table(result, args.output)

    if args.segmentation and args.output_segmentation:
        seg = _load_segmentation(args.segmentation)
        out = np.zeros_like(seg)
        for label_id, cat_id in zip(result["label"].values, result["category_id"].values):
            out[seg == int(label_id)] = int(cat_id)
        _save_segmentation(out, args.output_segmentation)


def main() -> None:
    """Entry point for the segmentation-measurement CLI."""
    parser = argparse.ArgumentParser(
        prog="segmentation-measurement",
        description="Post-processing and measurement utilities for instance segmentations.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # --- postprocess ---
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
        help="Minimum segment size in pixels/voxels.",
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

    # --- measure ---
    meas_parser = subparsers.add_parser("measure", help="Measurement utilities.")
    meas_subparsers = meas_parser.add_subparsers(dest="subcommand")
    meas_subparsers.required = True

    int_meas = meas_subparsers.add_parser(
        "intensities",
        help="Compute per-segment intensity statistics.",
    )
    int_meas.add_argument("--segmentation", required=True, help="Segmentation TIFF file.")
    int_meas.add_argument("--intensity", required=True, help="Intensity image TIFF file.")
    int_meas.add_argument(
        "--output", required=True,
        help="Output table file (CSV by default; TSV or XLSX by extension).",
    )
    int_meas.set_defaults(func=cmd_measure_intensities)

    morph_meas = meas_subparsers.add_parser(
        "morphology",
        help="Compute per-segment morphological measurements.",
    )
    morph_meas.add_argument("--segmentation", required=True, help="Segmentation TIFF file.")
    morph_meas.add_argument(
        "--output", required=True,
        help="Output table file (CSV by default; TSV or XLSX by extension).",
    )
    morph_meas.add_argument(
        "--scale", type=float, nargs="+", default=[1.0],
        help=(
            "Physical pixel/voxel size. One value for isotropic spacing, "
            "or one value per dimension (e.g. --scale 0.5 0.25 0.25 for 3D)."
        ),
    )
    morph_meas.set_defaults(func=cmd_measure_morphology)

    cell_nuc_meas = meas_subparsers.add_parser(
        "cell-nucleus",
        help="Compute per-cell measurements combining cell and nucleus segmentations.",
    )
    cell_nuc_meas.add_argument(
        "--cell-segmentation", required=True, help="Cell segmentation TIFF file.",
    )
    cell_nuc_meas.add_argument(
        "--nucleus-segmentation", required=True, help="Nucleus segmentation TIFF file.",
    )
    cell_nuc_meas.add_argument(
        "--output", required=True,
        help="Output table file (CSV by default; TSV or XLSX by extension).",
    )
    cell_nuc_meas.add_argument(
        "--scale", type=float, nargs="+", default=[1.0],
        help=(
            "Physical pixel/voxel size. One value for isotropic spacing, "
            "or one value per dimension (e.g. --scale 0.5 0.25 0.25 for 3D)."
        ),
    )
    cell_nuc_meas.add_argument(
        "--intensity", default=None,
        help="Optional intensity image TIFF file.",
    )
    cell_nuc_meas.set_defaults(func=cmd_measure_cell_nucleus)

    # --- analyze ---
    analyze_parser = subparsers.add_parser("analyze", help="Analysis utilities.")
    analyze_subparsers = analyze_parser.add_subparsers(dest="subcommand")
    analyze_subparsers.required = True

    thresh = analyze_subparsers.add_parser(
        "threshold",
        help="Categorize segments by threshold on a measurement column.",
    )
    thresh.add_argument(
        "--table", required=True,
        help="Input measurement table (CSV, TSV, or XLSX).",
    )
    thresh.add_argument(
        "--column", required=True,
        help="Column name to apply thresholds to.",
    )
    thresh.add_argument(
        "--n-categories", type=int, required=True,
        help="Number of categories.",
    )
    thresh.add_argument(
        "--thresholds", type=float, nargs="+", default=None,
        help=(
            "Explicit threshold values (n_categories - 1 values). "
            "If omitted, thresholds are suggested automatically."
        ),
    )
    thresh.add_argument(
        "--category-names", nargs="+", default=None,
        help="Names for each category (n_categories values).",
    )
    thresh.add_argument(
        "--output", required=True,
        help="Output table file with category columns (CSV, TSV, or XLSX).",
    )
    thresh.add_argument(
        "--segmentation", default=None,
        help="Segmentation TIFF file (required for --output-segmentation).",
    )
    thresh.add_argument(
        "--output-segmentation", default=None,
        help="Output category segmentation TIFF file.",
    )
    thresh.set_defaults(func=cmd_analyze_threshold)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
