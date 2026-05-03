"""Intensity measurement utilities for instance segmentations."""

from __future__ import annotations

import numpy as np
import pandas as pd
from skimage.measure import regionprops

_COLUMNS = [
    "label", "mean_intensity", "median_intensity", "max_intensity",
    "min_intensity", "std_intensity",
    "percentile_10", "percentile_25", "percentile_75", "percentile_90",
]


def measure_intensities(segmentation: np.ndarray, intensity_image: np.ndarray) -> pd.DataFrame:
    """Compute per-segment intensity statistics.

    For each labeled segment, computes mean, median, maximum, minimum,
    standard deviation and common percentiles of pixel intensities.

    Args:
        segmentation (np.ndarray): Integer-valued label array where 0 is
            background. Supports arbitrary dimensionality.
        intensity_image (np.ndarray): Intensity image with the same shape as
            ``segmentation``.

    Returns:
        pd.DataFrame: One row per segment with columns ``label``,
            ``mean_intensity``, ``median_intensity``, ``max_intensity``,
            ``min_intensity``, ``std_intensity``, ``percentile_10``,
            ``percentile_25``, ``percentile_75``, ``percentile_90``.
    """
    props = regionprops(segmentation, intensity_image)
    if not props:
        return pd.DataFrame(columns=_COLUMNS)

    rows = []
    for region in props:
        intensities = region.intensity_image[region.image].astype(float)
        rows.append({
            "label": region.label,
            "mean_intensity": float(np.mean(intensities)),
            "median_intensity": float(np.median(intensities)),
            "max_intensity": float(np.max(intensities)),
            "min_intensity": float(np.min(intensities)),
            "std_intensity": float(np.std(intensities)),
            "percentile_10": float(np.percentile(intensities, 10)),
            "percentile_25": float(np.percentile(intensities, 25)),
            "percentile_75": float(np.percentile(intensities, 75)),
            "percentile_90": float(np.percentile(intensities, 90)),
        })
    return pd.DataFrame(rows)


def suggest_thresholds(measurements: pd.DataFrame, column: str, n_categories: int) -> list[float]:
    """Suggest intensity thresholds for categorizing segments.

    Computes ``n_categories - 1`` threshold values at equally-spaced quantiles
    of the specified column.

    Args:
        measurements (pd.DataFrame): DataFrame as returned by
            :func:`measure_intensities`.
        column (str): Column name to compute thresholds for.
        n_categories (int): Number of desired categories. Must be >= 2.

    Returns:
        list[float]: ``n_categories - 1`` threshold values in ascending order.

    Raises:
        ValueError: If ``n_categories`` < 2 or ``column`` is not in
            ``measurements``.
    """
    if n_categories < 2:
        raise ValueError("n_categories must be >= 2.")
    if column not in measurements.columns:
        raise ValueError(f"Column '{column}' not found in measurements.")
    values = measurements[column].dropna().values
    quantile_positions = np.linspace(0, 100, n_categories + 1)[1:-1]
    return [float(np.percentile(values, q)) for q in quantile_positions]


def categorize_by_intensity(
    measurements: pd.DataFrame,
    column: str,
    thresholds: list[float],
    category_names: list[str] | None = None,
) -> pd.DataFrame:
    """Assign categories to segments based on intensity thresholds.

    Segments with values below the first threshold are assigned category 1,
    between consecutive thresholds category 2, ..., N.

    Args:
        measurements (pd.DataFrame): DataFrame as returned by
            :func:`measure_intensities`.
        column (str): Column name to apply thresholds to.
        thresholds (list[float]): ``n_categories - 1`` threshold values.
            Need not be sorted; they are sorted internally.
        category_names (list[str] | None): ``n_categories`` names, one per
            category. Defaults to ``"category_1"``, ``"category_2"``, etc.

    Returns:
        pd.DataFrame: Copy of ``measurements`` with added columns
            ``category_id`` (int, 1-based) and ``category_name`` (str).

    Raises:
        ValueError: If ``column`` is not in ``measurements`` or
            ``category_names`` has the wrong length.
    """
    if column not in measurements.columns:
        raise ValueError(f"Column '{column}' not found in measurements.")
    n_categories = len(thresholds) + 1
    if category_names is None:
        category_names = [f"category_{i + 1}" for i in range(n_categories)]
    if len(category_names) != n_categories:
        raise ValueError(
            f"Expected {n_categories} category names, got {len(category_names)}."
        )
    result = measurements.copy()
    values = result[column].values
    category_ids = (np.digitize(values, sorted(thresholds)) + 1).astype(int)
    result["category_id"] = category_ids
    result["category_name"] = [category_names[cid - 1] for cid in category_ids]
    return result
