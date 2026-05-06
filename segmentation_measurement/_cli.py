"""Command line interface for segmentation-measurement."""

from __future__ import annotations

import argparse
import glob
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import tifffile

from segmentation_measurement._utils import load_table, save_table


@dataclass(frozen=True)
class _OpenPath:
    path: Path
    layer_name: str


def _load_segmentation(path: str) -> np.ndarray:
    return tifffile.imread(path)


def _save_segmentation(segmentation: np.ndarray, path: str) -> None:
    tifffile.imwrite(path, segmentation)


def _has_glob_magic(pattern: str) -> bool:
    return any(char in pattern for char in "*?[")


def _glob_root(pattern: str) -> Path:
    path = Path(pattern)
    parts = path.parts
    wildcard_index = next(
        i for i, part in enumerate(parts) if _has_glob_magic(part)
    )
    root_parts = parts[:wildcard_index]
    if not root_parts:
        return Path(".")
    return Path(*root_parts)


def _layer_name_for_path(path: Path, root: Path | None) -> str:
    if root is None:
        name_path = path.name
    else:
        try:
            name_path = path.relative_to(root)
        except ValueError:
            name_path = path.name
    return Path(name_path).with_suffix("").as_posix()


def _expand_open_paths(patterns: list[str], role: str) -> list[_OpenPath]:
    """Expand file paths or glob expressions for the napari ``open`` command."""
    expanded: list[_OpenPath] = []
    for pattern in patterns:
        if _has_glob_magic(pattern):
            root = _glob_root(pattern)
            matches = sorted(
                Path(path) for path in glob.glob(pattern, recursive=True)
                if Path(path).is_file()
            )
            if not matches:
                raise ValueError(
                    f"No files matched {role} glob expression: {pattern}"
                )
            expanded.extend(
                _OpenPath(path, _layer_name_for_path(path, root))
                for path in matches
            )
        else:
            path = Path(pattern)
            if not path.is_file():
                raise ValueError(f"{role.capitalize()} path is not a file: {pattern}")
            expanded.append(_OpenPath(path, _layer_name_for_path(path, None)))
    return expanded


def _validate_open_path_counts(
    segmentations: list[_OpenPath],
    intensities: list[_OpenPath] | None,
    nuclei: list[_OpenPath] | None,
) -> None:
    n_segmentations = len(segmentations)
    for role, paths in (
        ("intensity image", intensities),
        ("nucleus segmentation", nuclei),
    ):
        if paths is not None and len(paths) != n_segmentations:
            raise ValueError(
                f"Expected {n_segmentations} {role} path(s) to match the "
                f"number of segmentation paths, got {len(paths)}."
            )


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
    result = compute_ring_mask(seg, args.ring_width, keep_original=not args.remove_original)
    _save_segmentation(result, args.output)


def cmd_watershed(args: argparse.Namespace) -> None:
    """Execute the watershed sub-command."""
    from segmentation_measurement.postprocessing import apply_watershed
    seg = _load_segmentation(args.input)
    heatmap = tifffile.imread(args.heatmap)
    mask = tifffile.imread(args.mask) if args.mask else None
    result = apply_watershed(seg, heatmap, mask=mask)
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
        for label_id, cluster_id in zip(result["index"].values, result["cluster_id"].values):
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
        for label_id, cid in zip(result["index"].values, result["classification_id"].values):
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


def cmd_table_merge(args: argparse.Namespace) -> None:
    """Execute the table-merge sub-command."""
    from segmentation_measurement.table_manipulation import (
        drop_columns,
        merge_tables,
    )
    frames = [load_table(p) for p in args.inputs]
    if len(frames) == 1:
        result = frames[0]
    else:
        result = merge_tables(frames, on=args.on)
    if args.drop_columns:
        result = drop_columns(result, list(args.drop_columns))
    save_table(result, args.output)


def cmd_open(args: argparse.Namespace) -> None:
    """Open segmentations and optional matched images in napari."""
    import napari
    from segmentation_measurement._groups import (
        ROLE_INTENSITY_IMAGE,
        ROLE_NUCLEUS_SEGMENTATION,
        ROLE_SEGMENTATION,
        set_group,
    )

    segmentations = _expand_open_paths(args.segmentations, "segmentation")
    intensities = (
        _expand_open_paths(args.intensities, "intensity image")
        if args.intensities
        else None
    )
    nuclei = (
        _expand_open_paths(args.nuclei, "nucleus segmentation")
        if args.nuclei
        else None
    )
    _validate_open_path_counts(segmentations, intensities, nuclei)

    viewer = napari.Viewer()
    seg_layers = [
        viewer.add_labels(tifffile.imread(item.path), name=item.layer_name)
        for item in segmentations
    ]
    nucleus_layers = []
    if nuclei is not None:
        nucleus_layers = [
            viewer.add_labels(tifffile.imread(item.path), name=item.layer_name)
            for item in nuclei
        ]
    intensity_layers = []
    if intensities is not None:
        intensity_layers = [
            viewer.add_image(tifffile.imread(item.path), name=item.layer_name)
            for item in intensities
        ]

    if len(seg_layers) > 1 and not args.no_group:
        members = {ROLE_SEGMENTATION: [layer.name for layer in seg_layers]}
        if nucleus_layers:
            members[ROLE_NUCLEUS_SEGMENTATION] = [
                layer.name for layer in nucleus_layers
            ]
        if intensity_layers:
            members[ROLE_INTENSITY_IMAGE] = [
                layer.name for layer in intensity_layers
            ]
        group_name = args.group_name
        set_group(viewer, group_name, members)
        if not args.no_grid:
            from segmentation_measurement._groups_widget import GroupManagerWidget
            arranger = GroupManagerWidget(viewer)
            arranger._arrange_group_as_grid(members)
            arranger.deleteLater()

    napari.run()


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
        for label_id, cat_id in zip(result["index"].values, result["category_id"].values):
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

    open_parser = subparsers.add_parser(
        "open",
        help="Open segmentations and optional matched images in napari.",
    )
    open_parser.add_argument(
        "--segmentations",
        nargs="+",
        required=True,
        help=(
            "Segmentation file path(s) or glob expression(s). Glob patterns "
            "are expanded recursively when they include **."
        ),
    )
    open_parser.add_argument(
        "--intensities",
        nargs="+",
        default=None,
        help=(
            "Optional intensity image file path(s) or glob expression(s). "
            "The expanded count must match --segmentations."
        ),
    )
    open_parser.add_argument(
        "--nuclei",
        "--nucleus-segmentations",
        nargs="+",
        default=None,
        help=(
            "Optional nucleus segmentation file path(s) or glob expression(s). "
            "The expanded count must match --segmentations."
        ),
    )
    open_parser.add_argument(
        "--no-group",
        action="store_true",
        default=False,
        help="Do not create a group when opening multiple segmentations.",
    )
    open_parser.add_argument(
        "--no-grid",
        action="store_true",
        default=False,
        help="Create the group but do not arrange it as a grid.",
    )
    open_parser.add_argument(
        "--group-name",
        default="opened_files",
        help="Name for the automatically created group.",
    )
    open_parser.set_defaults(func=cmd_open)

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
    rm.add_argument(
        "--remove-original", action="store_true", default=False,
        help="Remove original segment pixels from the output, keeping only the ring pixels.",
    )
    rm.set_defaults(func=cmd_ring_mask)

    ws = pp_subparsers.add_parser(
        "watershed",
        help="Refine segmentation using the watershed algorithm.",
    )
    ws.add_argument("--input", required=True, help="Input segmentation file (TIFF) used as seed markers.")
    ws.add_argument("--heatmap", required=True, help="Heatmap image file (TIFF) used as the watershed landscape.")
    ws.add_argument("--output", required=True, help="Output segmentation file (TIFF).")
    ws.add_argument("--mask", default=None, help="Optional binary mask file (TIFF); only masked pixels are processed.")
    ws.set_defaults(func=cmd_watershed)

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

    # --- table ---
    table_parser = subparsers.add_parser("table", help="Table manipulation utilities.")
    table_subparsers = table_parser.add_subparsers(dest="subcommand")
    table_subparsers.required = True

    merge_parser = table_subparsers.add_parser(
        "merge",
        help="Merge multiple measurement tables and optionally drop columns.",
    )
    merge_parser.add_argument(
        "--inputs", nargs="+", required=True,
        help="Input table files (CSV, TSV, or XLSX). At least one required.",
    )
    merge_parser.add_argument(
        "--output", required=True,
        help="Output table file (CSV by default; TSV or XLSX by extension).",
    )
    merge_parser.add_argument(
        "--on", default="index",
        help="Key column shared between input tables (default: index).",
    )
    merge_parser.add_argument(
        "--drop-columns", nargs="+", default=None,
        help="Optional list of column names to drop from the merged table.",
    )
    merge_parser.set_defaults(func=cmd_table_merge)

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
    try:
        args.func(args)
    except ValueError as exc:
        if args.command == "open":
            parser.error(str(exc))
        raise


if __name__ == "__main__":
    main()
