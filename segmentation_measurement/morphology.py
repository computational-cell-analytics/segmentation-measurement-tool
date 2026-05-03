"""Morphology measurement utilities for instance segmentations."""

from __future__ import annotations

import numpy as np
import pandas as pd
from skimage.measure import regionprops

_COLUMNS_2D = [
    "label", "area", "perimeter", "sphericity", "solidity",
    "axis_major_length", "axis_minor_length", "equivalent_diameter",
]
_COLUMNS_3D = [
    "label", "volume", "surface_area", "sphericity", "solidity",
    "axis_major_length", "axis_minor_length", "equivalent_diameter",
]


def measure_morphology(
    segmentation: np.ndarray,
    scale: float | tuple = 1.0,
) -> pd.DataFrame:
    """Compute per-segment morphological measurements.

    Supported dimensionality is 2D and 3D.  For 2D the measurements are area,
    perimeter, sphericity (circularity), solidity, major and minor axis
    lengths, and equivalent diameter.  For 3D the measurements are volume,
    surface area (via marching cubes), sphericity, solidity, major and minor
    axis lengths, and equivalent diameter.

    Args:
        segmentation (np.ndarray): Integer-valued label array where 0 is
            background.  Must be 2D or 3D.
        scale (float | tuple): Physical size of a pixel/voxel. A single float
            is interpreted as isotropic spacing. A tuple of length ``ndim``
            gives per-dimension spacing (e.g. ``(z, y, x)`` for 3D).
            Defaults to 1.0 (pixel units).

    Returns:
        pd.DataFrame: One row per segment.  2D columns: ``label``, ``area``,
            ``perimeter``, ``sphericity``, ``solidity``, ``axis_major_length``,
            ``axis_minor_length``, ``equivalent_diameter``.  3D columns:
            ``label``, ``volume``, ``surface_area``, ``sphericity``,
            ``solidity``, ``axis_major_length``, ``axis_minor_length``,
            ``equivalent_diameter``.

    Raises:
        ValueError: If ``segmentation`` is not 2D or 3D, or if ``scale``
            tuple length does not match ``ndim``.
    """
    ndim = segmentation.ndim
    if ndim not in (2, 3):
        raise ValueError(
            f"measure_morphology requires 2D or 3D input, got {ndim}D."
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

    props = regionprops(segmentation)
    if not props:
        columns = _COLUMNS_2D if ndim == 2 else _COLUMNS_3D
        return pd.DataFrame(columns=columns)

    pixel_measure = float(np.prod(scale_tuple))
    mean_scale = float(np.mean(scale_tuple))

    rows = []
    for region in props:
        row: dict = {"label": region.label, "solidity": float(region.solidity)}

        if ndim == 2:
            area = region.area * pixel_measure
            perimeter = region.perimeter * mean_scale
            sphericity = (
                4.0 * np.pi * area / (perimeter ** 2) if perimeter > 0 else 0.0
            )
            row["area"] = area
            row["perimeter"] = perimeter
            row["sphericity"] = sphericity
            row["axis_major_length"] = region.axis_major_length * mean_scale
            row["axis_minor_length"] = region.axis_minor_length * mean_scale
            row["equivalent_diameter"] = region.equivalent_diameter_area * mean_scale

        else:  # 3D
            volume = region.area * pixel_measure

            binary = segmentation == region.label
            padded = np.pad(binary[region.slice], 1)
            try:
                from skimage.measure import marching_cubes, mesh_surface_area
                verts, faces, _, _ = marching_cubes(
                    padded, level=0.5, spacing=scale_tuple
                )
                surface_area = float(mesh_surface_area(verts, faces))
            except (ValueError, RuntimeError):
                surface_area = 0.0

            sphericity = (
                np.pi ** (1.0 / 3.0) * (6.0 * volume) ** (2.0 / 3.0) / surface_area
                if surface_area > 0 else 0.0
            )
            row["volume"] = volume
            row["surface_area"] = surface_area
            row["sphericity"] = sphericity
            row["axis_major_length"] = region.axis_major_length * mean_scale
            row["axis_minor_length"] = region.axis_minor_length * mean_scale
            row["equivalent_diameter"] = region.equivalent_diameter_area * mean_scale

        rows.append(row)

    columns = _COLUMNS_2D if ndim == 2 else _COLUMNS_3D
    return pd.DataFrame(rows, columns=columns)
