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


def cmd_analyze_cluster(args: argparse.Namespace) -> None:
    """Execute the analyze-cluster sub-command."""
    from segmentation_measurement.analysis import cluster_measurements
    df = load_table(args.table)
    kwargs: dict = {}
    if args.n_clusters is not None:
        kwargs["n_clusters"] = args.n_clusters
    if args.eps is not None:
        kwargs["eps"] = args.eps
    if args.min_samples is not None:
        kwargs["min_samples"] = args.min_samples
    if args.min_cluster_size is not None:
        kwargs["min_cluster_size"] = args.min_cluster_size
    if args.bandwidth is not None and args.bandwidth > 0:
        kwargs["bandwidth"] = args.bandwidth
    result = cluster_measurements(df, method=args.method, **kwargs)
    save_table(result, args.output)

    if args.segmentation and args.output_segmentation:
        seg = _load_segmentation(args.segmentation)
        out = np.zeros_like(seg)
        for label_id, cluster_id in zip(result["label"].values, result["cluster_id"].values):
            if int(cluster_id) > 0:  # 1-based; skip noise (-1)
                out[seg == int(label_id)] = int(cluster_id)
        _save_segmentation(out, args.output_segmentation)


def cmd_analyze_classify(args: argparse.Namespace) -> None:
    """Execute the analyze-classify sub-command."""
    from segmentation_measurement.analysis import apply_classifier
    import joblib
    df = load_table(args.table)
    classifier = joblib.load(args.classifier)
    class_names = list(args.class_names) if args.class_names else None
    result = apply_classifier(df, classifier, class_names=class_names)
    save_table(result, args.output)

    if args.segmentation and args.output_segmentation:
        seg = _load_segmentation(args.segmentation)
        out = np.zeros_like(seg)
        for label_id, cid in zip(result["label"].values, result["classification_id"].values):
            if int(cid) > 0:
                out[seg == int(label_id)] = int(cid)
        _save_segmentation(out, args.output_segmentation)


def cmd_analyze_train_classifier(args: argparse.Namespace) -> None:
    """Execute the analyze-train-classifier sub-command."""
    from segmentation_measurement.analysis import train_classifier
    import joblib
    frames = [load_table(p) for p in args.tables]
    import pandas as pd
    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    kwargs: dict = {}
    if args.max_iter is not None:
        kwargs["max_iter"] = args.max_iter
    if args.c is not None:
        kwargs["C"] = args.c
    if args.n_estimators is not None:
        kwargs["n_estimators"] = args.n_estimators
    if args.max_depth is not None and args.max_depth > 0:
        kwargs["max_depth"] = args.max_depth
    classifier = train_classifier(
        df,
        annotation_column=args.annotation_column,
        method=args.method,
        **kwargs,
    )
    joblib.dump(classifier, args.output)


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

    clust = analyze_subparsers.add_parser(
        "cluster",
        help="Cluster segments using their measurement features.",
    )
    clust.add_argument(
        "--table", required=True,
        help="Input measurement table (CSV, TSV, or XLSX).",
    )
    clust.add_argument(
        "--method",
        default="kmeans",
        choices=["kmeans", "dbscan", "hdbscan", "mean_shift"],
        help="Clustering method (default: kmeans).",
    )
    clust.add_argument("--n-clusters", type=int, default=None, help="K-Means: number of clusters.")
    clust.add_argument("--eps", type=float, default=None, help="DBSCAN: neighbourhood radius.")
    clust.add_argument(
        "--min-samples", type=int, default=None,
        help="DBSCAN/HDBSCAN: minimum samples in a neighbourhood.",
    )
    clust.add_argument(
        "--min-cluster-size", type=int, default=None,
        help="HDBSCAN: minimum cluster size.",
    )
    clust.add_argument(
        "--bandwidth", type=float, default=None,
        help="Mean Shift: bandwidth (0 or omit for automatic estimation).",
    )
    clust.add_argument(
        "--output", required=True,
        help="Output table file with cluster_id column (CSV, TSV, or XLSX).",
    )
    clust.add_argument(
        "--segmentation", default=None,
        help="Segmentation TIFF file (required for --output-segmentation).",
    )
    clust.add_argument(
        "--output-segmentation", default=None,
        help="Output cluster segmentation TIFF file.",
    )
    clust.set_defaults(func=cmd_analyze_cluster)

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

    classify = analyze_subparsers.add_parser(
        "classify",
        help="Apply a trained classifier to a measurement table.",
    )
    classify.add_argument(
        "--table", required=True,
        help="Input measurement table (CSV, TSV, or XLSX).",
    )
    classify.add_argument(
        "--classifier", required=True,
        help="Path to a trained classifier saved with joblib (.joblib).",
    )
    classify.add_argument(
        "--output", required=True,
        help="Output table file with classification columns (CSV, TSV, or XLSX).",
    )
    classify.add_argument(
        "--class-names", nargs="+", default=None,
        help=(
            "Names for each class in ascending class-label order "
            "(e.g. --class-names typeA typeB typeC)."
        ),
    )
    classify.add_argument(
        "--segmentation", default=None,
        help="Segmentation TIFF file (required for --output-segmentation).",
    )
    classify.add_argument(
        "--output-segmentation", default=None,
        help="Output classification segmentation TIFF file.",
    )
    classify.set_defaults(func=cmd_analyze_classify)

    train_clf = analyze_subparsers.add_parser(
        "train-classifier",
        help="Train a classifier from annotated measurement tables.",
    )
    train_clf.add_argument(
        "--tables", nargs="+", required=True,
        help="One or more annotated measurement tables (CSV, TSV, or XLSX).",
    )
    train_clf.add_argument(
        "--output", required=True,
        help="Output classifier file (.joblib).",
    )
    train_clf.add_argument(
        "--method",
        default="random_forest",
        choices=["logistic_regression", "random_forest"],
        help="Classifier type (default: random_forest).",
    )
    train_clf.add_argument(
        "--annotation-column", default="annotation",
        help="Column containing integer annotation labels (default: annotation).",
    )
    train_clf.add_argument("--c", type=float, default=None, help="LR: regularisation strength C.")
    train_clf.add_argument(
        "--max-iter", type=int, default=None, help="LR: maximum number of iterations.",
    )
    train_clf.add_argument(
        "--n-estimators", type=int, default=None, help="RF: number of trees.",
    )
    train_clf.add_argument(
        "--max-depth", type=int, default=None,
        help="RF: maximum tree depth (0 or omit for unlimited).",
    )
    train_clf.set_defaults(func=cmd_analyze_train_classifier)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
