"""Intensity measurement utilities for instance segmentations."""

from __future__ import annotations

import numpy as np
import pandas as pd
from skimage.measure import regionprops

_COLUMNS = [
    "index", "mean_intensity", "median_intensity", "max_intensity",
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
        pd.DataFrame: One row per segment with columns ``index``,
            ``mean_intensity``, ``median_intensity``, ``max_intensity``,
            ``min_intensity``, ``std_intensity``, ``percentile_10``,
            ``percentile_25``, ``percentile_75``, ``percentile_90``.
            ``index`` holds the integer label ID of each segment.
    """
    props = regionprops(segmentation, intensity_image)
    if not props:
        return pd.DataFrame(columns=_COLUMNS)

    rows = []
    for region in props:
        # ``image_intensity`` was renamed in scikit-image 0.26; keep the old
        # ``intensity_image`` name as a fallback for older versions.
        intensity_arr = getattr(region, "image_intensity", None)
        if intensity_arr is None:
            intensity_arr = region.intensity_image
        intensities = intensity_arr[region.image].astype(float)
        rows.append({
            "index": region.label,
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
