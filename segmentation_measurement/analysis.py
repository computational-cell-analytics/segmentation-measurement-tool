"""Analysis utilities operating on measurement DataFrames."""

from __future__ import annotations

import numpy as np
import pandas as pd


def suggest_thresholds(measurements: pd.DataFrame, column: str, n_categories: int) -> list[float]:
    """Suggest thresholds for categorizing segments.

    Computes ``n_categories - 1`` threshold values at equally-spaced quantiles
    of the specified column.

    Args:
        measurements (pd.DataFrame): Measurement DataFrame as returned by
            :func:`~segmentation_measurement.measure_intensities` or
            :func:`~segmentation_measurement.measure_morphology`.
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


def categorize_by_threshold(
    measurements: pd.DataFrame,
    column: str,
    thresholds: list[float],
    category_names: list[str] | None = None,
) -> pd.DataFrame:
    """Assign categories to segments based on thresholds.

    Segments with values below the first threshold are assigned category 1,
    between consecutive thresholds category 2, ..., N.  Works with any
    measurement DataFrame (intensity or morphology).

    Args:
        measurements (pd.DataFrame): Measurement DataFrame as returned by
            :func:`~segmentation_measurement.measure_intensities` or
            :func:`~segmentation_measurement.measure_morphology`.
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
