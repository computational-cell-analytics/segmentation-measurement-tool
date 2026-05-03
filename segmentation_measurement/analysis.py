"""Analysis utilities operating on measurement DataFrames."""

from __future__ import annotations

import numpy as np
import pandas as pd

_CLUSTER_EXCLUDE = frozenset({"label", "cluster_id", "category_id", "category_name"})


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


def cluster_measurements(
    measurements: pd.DataFrame,
    method: str = "kmeans",
    **kwargs,
) -> pd.DataFrame:
    """Apply clustering to measurement features.

    Clusters segments using all numeric measurement columns, excluding
    ``label``, ``cluster_id``, ``category_id``, and ``category_name``.
    Features are z-score standardised before clustering.

    Args:
        measurements (pd.DataFrame): Measurement DataFrame as returned by
            :func:`~segmentation_measurement.measure_intensities` or similar.
        method (str): Clustering method.  One of ``'kmeans'``, ``'dbscan'``,
            ``'hdbscan'``, or ``'mean_shift'``.  Defaults to ``'kmeans'``.
        **kwargs: Keyword arguments forwarded to the underlying scikit-learn
            estimator.  Sensible defaults are used when not provided:
            k-means – ``n_clusters=3``; DBSCAN – ``eps=0.5``,
            ``min_samples=5``; HDBSCAN – ``min_cluster_size=5``; Mean Shift –
            bandwidth is estimated automatically.

    Returns:
        pd.DataFrame: Copy of ``measurements`` with an added ``cluster_id``
            column containing integer cluster labels.  ``-1`` marks noise
            points for methods that support it (DBSCAN, HDBSCAN).

    Raises:
        ValueError: If ``method`` is unrecognised or no numeric feature
            columns are found in ``measurements``.
    """
    from sklearn.preprocessing import StandardScaler

    feature_cols = [
        c for c in measurements.select_dtypes(include="number").columns
        if c not in _CLUSTER_EXCLUDE
    ]
    if not feature_cols:
        raise ValueError("No numeric feature columns found in measurements.")

    X = measurements[feature_cols].values.astype(float)
    valid_mask = ~np.isnan(X).any(axis=1)
    X_valid = StandardScaler().fit_transform(X[valid_mask])

    model = _build_clustering_model(method, kwargs)
    labels_valid = model.fit_predict(X_valid).copy()
    # Shift to 1-based; noise (-1) stays -1
    labels_valid[labels_valid >= 0] += 1

    labels = np.full(len(measurements), -1, dtype=int)
    labels[valid_mask] = labels_valid

    result = measurements.copy()
    result["cluster_id"] = labels
    return result


def _build_clustering_model(method: str, kwargs: dict) -> object:
    """Instantiate a sklearn clustering model with sensible defaults."""
    method_key = method.lower().replace("-", "_").replace(" ", "_")
    if method_key in ("kmeans", "k_means"):
        from sklearn.cluster import KMeans
        params: dict = {"n_clusters": 3}
        params.update(kwargs)
        return KMeans(**params)
    if method_key == "dbscan":
        from sklearn.cluster import DBSCAN
        params = {"eps": 0.5, "min_samples": 5}
        params.update(kwargs)
        return DBSCAN(**params)
    if method_key == "hdbscan":
        from sklearn.cluster import HDBSCAN
        params = {"min_cluster_size": 5}
        params.update(kwargs)
        return HDBSCAN(**params)
    if method_key in ("mean_shift", "meanshift"):
        from sklearn.cluster import MeanShift
        params = {}
        params.update(kwargs)
        return MeanShift(**params)
    raise ValueError(
        f"Unknown clustering method '{method}'. "
        "Choose from: 'kmeans', 'dbscan', 'hdbscan', 'mean_shift'."
    )
