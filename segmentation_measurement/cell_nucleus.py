"""Cell-nucleus measurement utilities for instance segmentations."""

from __future__ import annotations

import numpy as np
import pandas as pd

_INTENSITY_STATS = [
    "mean", "median", "max", "min",
    "percentile_10", "percentile_25", "percentile_75", "percentile_90",
]


def _base_columns(ndim: int, has_intensity: bool) -> list[str]:
    size_col = "area" if ndim == 2 else "volume"
    cols = [
        "label", "n_nuclei",
        f"cell_{size_col}", f"nucleus_{size_col}", f"{size_col}_ratio",
    ]
    if has_intensity:
        for prefix in ("cell", "nucleus"):
            for stat in _INTENSITY_STATS:
                cols.append(f"{prefix}_{stat}_intensity")
        for stat in _INTENSITY_STATS:
            cols.append(f"{stat}_intensity_ratio")
    return cols


def _compute_intensity_stats(pixels: np.ndarray) -> dict:
    arr = pixels.astype(float)
    return {
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "max": float(np.max(arr)),
        "min": float(np.min(arr)),
        "percentile_10": float(np.percentile(arr, 10)),
        "percentile_25": float(np.percentile(arr, 25)),
        "percentile_75": float(np.percentile(arr, 75)),
        "percentile_90": float(np.percentile(arr, 90)),
    }


def _nan_intensity_stats() -> dict:
    return {stat: float("nan") for stat in _INTENSITY_STATS}


def measure_cell_nucleus(
    cell_segmentation: np.ndarray,
    nucleus_segmentation: np.ndarray,
    scale: float | tuple = 1.0,
    intensity_image: np.ndarray | None = None,
) -> pd.DataFrame:
    """Compute per-cell measurements combining cell and nucleus segmentations.

    For each cell, computes the number of nuclei it contains, the ratio of
    cell to nuclear area/volume (in physical units), and optionally the ratio
    of intensity statistics between the cytoplasmic and nuclear regions.

    The cell area/volume encompasses the nucleus (nuclear mask is **not**
    excluded).  For intensity measurements, the nuclear mask **is** excluded
    from the cellular region so that cytoplasmic and nuclear intensities are
    measured independently.

    Supported dimensionality is 2D and 3D.

    Args:
        cell_segmentation (np.ndarray): Integer-valued label array of cells
            where 0 is background.  Must be 2D or 3D.
        nucleus_segmentation (np.ndarray): Integer-valued label array of
            nuclei where 0 is background.  Must have the same shape as
            ``cell_segmentation``.
        scale (float | tuple): Physical size of a pixel/voxel.  A single
            float is interpreted as isotropic spacing.  A tuple must have one
            value per spatial dimension in ``(Y, X)`` order for 2D or
            ``(Z, Y, X)`` order for 3D.  Defaults to 1.0 (pixel/voxel units).
        intensity_image (np.ndarray | None): Optional intensity image with
            the same shape as ``cell_segmentation``.  When provided, intensity
            statistics are computed for the cytoplasmic (cell minus nucleus)
            and nuclear regions and their ratios are reported.

    Returns:
        pd.DataFrame: One row per cell with columns ``label``, ``n_nuclei``,
            ``cell_area``/``cell_volume``, ``nucleus_area``/``nucleus_volume``,
            ``area_ratio``/``volume_ratio``.  When *intensity_image* is given,
            additional columns are added for ``cell_{stat}_intensity``,
            ``nucleus_{stat}_intensity``, and ``{stat}_intensity_ratio`` for
            each stat in mean, median, max, min, percentile_10, percentile_25,
            percentile_75, percentile_90.  The ``area_ratio``/``volume_ratio``
            is ``NaN`` for cells with no detected nucleus.  Intensity ratios
            are ``NaN`` when the cytoplasm or nucleus region is empty, or when
            the nucleus value is zero.

    Raises:
        ValueError: If ``cell_segmentation`` is not 2D or 3D, if the shapes
            of ``cell_segmentation`` and ``nucleus_segmentation`` do not match,
            if ``intensity_image`` shape does not match, or if ``scale`` tuple
            length does not match ``ndim``.
    """
    ndim = cell_segmentation.ndim
    if ndim not in (2, 3):
        raise ValueError(
            f"measure_cell_nucleus requires 2D or 3D input, got {ndim}D."
        )

    if cell_segmentation.shape != nucleus_segmentation.shape:
        raise ValueError(
            "cell_segmentation and nucleus_segmentation must have the same shape, "
            f"got {cell_segmentation.shape} and {nucleus_segmentation.shape}."
        )

    if intensity_image is not None and intensity_image.shape != cell_segmentation.shape:
        raise ValueError(
            "intensity_image must have the same shape as cell_segmentation, "
            f"got {intensity_image.shape} and {cell_segmentation.shape}."
        )

    if isinstance(scale, (int, float)):
        scale_tuple = tuple([float(scale)] * ndim)
    else:
        scale_tuple = tuple(float(s) for s in scale)
        if len(scale_tuple) != ndim:
            raise ValueError(
                f"scale must have {ndim} elements for a {ndim}D segmentation, "
                f"got {len(scale_tuple)}."
            )

    voxel_size = float(np.prod(scale_tuple))
    size_col = "area" if ndim == 2 else "volume"
    has_intensity = intensity_image is not None

    cell_ids = np.unique(cell_segmentation)
    cell_ids = cell_ids[cell_ids != 0]

    if len(cell_ids) == 0:
        return pd.DataFrame(columns=_base_columns(ndim, has_intensity))

    rows = []
    for cell_id in cell_ids:
        cell_mask = cell_segmentation == cell_id
        cell_size = float(np.sum(cell_mask)) * voxel_size

        nuc_ids = np.unique(nucleus_segmentation[cell_mask])
        nuc_ids = nuc_ids[nuc_ids != 0]
        n_nuclei = int(len(nuc_ids))

        nucleus_mask = (nucleus_segmentation != 0) & cell_mask
        nucleus_size = float(np.sum(nucleus_mask)) * voxel_size

        size_ratio = cell_size / nucleus_size if nucleus_size > 0 else float("nan")

        row: dict = {
            "label": int(cell_id),
            "n_nuclei": n_nuclei,
            f"cell_{size_col}": cell_size,
            f"nucleus_{size_col}": nucleus_size,
            f"{size_col}_ratio": size_ratio,
        }

        if has_intensity:
            cyto_mask = cell_mask & ~nucleus_mask
            cell_stats = (
                _compute_intensity_stats(intensity_image[cyto_mask])
                if np.any(cyto_mask)
                else _nan_intensity_stats()
            )
            nuc_stats = (
                _compute_intensity_stats(intensity_image[nucleus_mask])
                if np.any(nucleus_mask)
                else _nan_intensity_stats()
            )

            for stat in _INTENSITY_STATS:
                row[f"cell_{stat}_intensity"] = cell_stats[stat]
            for stat in _INTENSITY_STATS:
                row[f"nucleus_{stat}_intensity"] = nuc_stats[stat]
            for stat in _INTENSITY_STATS:
                c = cell_stats[stat]
                n = nuc_stats[stat]
                if not (np.isnan(c) or np.isnan(n)) and n != 0:
                    row[f"{stat}_intensity_ratio"] = c / n
                else:
                    row[f"{stat}_intensity_ratio"] = float("nan")

        rows.append(row)

    return pd.DataFrame(rows, columns=_base_columns(ndim, has_intensity))
