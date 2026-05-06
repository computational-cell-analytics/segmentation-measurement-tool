"""Shared utilities for measurement modules and widgets."""

from __future__ import annotations

from copy import copy
from pathlib import Path

import numpy as np
import pandas as pd


def save_table(df: pd.DataFrame, path: str) -> None:
    """Save a DataFrame to CSV, TSV, or Excel based on file extension.

    Args:
        df (pd.DataFrame): Table to save.
        path (str): Destination path. Extension determines format:
            ``.xlsx`` → Excel, ``.tsv`` → tab-separated, otherwise CSV.
    """
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".xlsx":
        df.to_excel(p, index=False)
    elif ext == ".tsv":
        df.to_csv(p, sep="\t", index=False)
    else:
        df.to_csv(p, index=False)


def load_table(path: str) -> pd.DataFrame:
    """Load a DataFrame from CSV, TSV, or Excel based on file extension.

    Args:
        path (str): Source path. Extension determines format:
            ``.xlsx`` → Excel, ``.tsv`` → tab-separated, otherwise CSV.

    Returns:
        pd.DataFrame: Loaded table.
    """
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".xlsx":
        return pd.read_excel(p)
    elif ext == ".tsv":
        return pd.read_csv(p, sep="\t")
    else:
        return pd.read_csv(p)


def copy_layer_spatial_metadata(source_layer: object, target_layer: object) -> None:
    """Copy spatial display metadata from one napari layer to another.

    Args:
        source_layer: Layer whose spatial placement should be copied.
        target_layer: Layer to place in the same physical coordinates.
    """
    for attr in ("scale", "translate", "rotate", "shear"):
        if not hasattr(source_layer, attr) or not hasattr(target_layer, attr):
            continue
        value = getattr(source_layer, attr)
        if isinstance(value, np.ndarray):
            value = value.copy()
        else:
            value = copy(value)
        setattr(target_layer, attr, value)

    for attr in ("affine", "axis_labels", "units"):
        if not hasattr(source_layer, attr) or not hasattr(target_layer, attr):
            continue
        try:
            setattr(target_layer, attr, copy(getattr(source_layer, attr)))
        except Exception:
            pass


_LINK_EXCLUDED_ATTRIBUTES = frozenset({
    "affine",
    "axis_labels",
    "data",
    "extent",
    "features",
    "loaded",
    "metadata",
    "mode",
    "name",
    "properties",
    "rotate",
    "scale",
    "shear",
    "status",
    "thumbnail",
    "translate",
    "units",
})


def link_layers_preserving_grid(viewer: object, layers: list[object]) -> None:
    """Link layer display attributes without linking spatial placement."""
    if len(layers) < 2:
        return
    common = set.intersection(*(set(layer.events) for layer in layers))
    common -= _LINK_EXCLUDED_ATTRIBUTES
    attrs = []
    for attr in common:
        if attr.startswith("_"):
            continue
        if all(
            hasattr(layer, attr) and not callable(getattr(layer, attr))
            for layer in layers
        ):
            attrs.append(attr)
    if attrs:
        viewer.layers.link_layers(layers, attributes=sorted(attrs))
