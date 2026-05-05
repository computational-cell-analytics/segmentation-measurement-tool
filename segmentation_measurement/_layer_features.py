"""Helpers for storing measurement DataFrames on Labels layers.

The package writes its measurement and analysis results into
``layer.features`` of the source segmentation layer.  napari's built-in
*Features table widget* (``Layers → Visualize → Features table widget``)
displays these tables and provides editing, sorting, copy/paste, CSV save,
and bidirectional selection sync between table rows and the viewer.

The DataFrame must contain a column named ``index`` whose values are the
segment label IDs.  napari's :class:`Labels` layer uses that column to map
table rows to label values; without it, napari falls back to row-position
indexing which silently misaligns selection for non-contiguous label sets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:  # pragma: no cover - type hints only
    import napari
    from napari.layers import Layer


def merge_features_into_layer(layer: "Layer", df: pd.DataFrame) -> pd.DataFrame:
    """Merge ``df`` into ``layer.features`` on the ``index`` column.

    If the layer already has features, the new DataFrame is outer-joined
    with the existing one on ``index``.  Columns present in both tables are
    overwritten with values from ``df`` (re-running a measurement updates
    its columns).  If the layer has no features yet, ``df`` becomes the
    new features.

    The merged DataFrame is padded with NaN rows so that **row position
    equals the ``index`` value**.  napari's built-in Features Table widget
    maps a row's position directly to the layer's ``selected_label`` for
    selection sync — it does not consult the ``index`` column.  Without
    this padding, label 0 (background, missing from
    :func:`skimage.measure.regionprops` output) would shift every label by
    one row and selection sync would be off by one in both directions.

    Args:
        layer: A napari Labels-like layer whose ``features`` attribute is
            a :class:`pandas.DataFrame`.
        df: Measurement DataFrame with an ``index`` column holding label IDs.

    Returns:
        pd.DataFrame: The merged, padded DataFrame that was written to
            ``layer.features``.

    Raises:
        ValueError: If ``df`` does not contain an ``index`` column.
    """
    if "index" not in df.columns:
        raise ValueError("DataFrame must contain an 'index' column with label IDs.")

    existing = getattr(layer, "features", None)
    if existing is None or len(getattr(existing, "columns", [])) == 0:
        merged = df.reset_index(drop=True).copy()
    else:
        existing = existing.copy()
        # Drop any columns that ``df`` overwrites (except the join key) so the
        # merge produces clean column names without ``_x`` / ``_y`` suffixes.
        overlap = [c for c in df.columns if c != "index" and c in existing.columns]
        if overlap:
            existing = existing.drop(columns=overlap)
        merged = existing.merge(df, on="index", how="outer")

    # Pad with NaN rows so that row position == index value.  This is required
    # for napari's Features Table widget, which maps row position directly to
    # ``layer.selected_label``.  Label 0 (background) is added as a NaN row;
    # gaps in the label set (e.g. after filtering) are also filled in.
    if len(merged) > 0:
        max_idx = int(merged["index"].max())
        full = pd.DataFrame({"index": range(max_idx + 1)})
        merged = full.merge(merged, on="index", how="left")
    merged = merged.sort_values("index").reset_index(drop=True)
    layer.features = merged
    return merged


def show_features_table(viewer: "napari.Viewer", layer: "Layer") -> None:
    """Open the napari built-in Features Table dock and select ``layer``.

    Idempotent: if the dock already exists it is reused; ``layer`` becomes
    the active selection so its features are displayed.  Failures are
    swallowed silently — the data has already been written to
    ``layer.features``, so the dock is purely a display aid.

    Hides the leading positional-index column that napari's Features Table
    always prepends, so the user sees only the meaningful ``index`` column
    (the segment label IDs).

    Args:
        viewer: The napari viewer instance.
        layer: The layer whose features should be displayed.
    """
    feature_widget = None
    try:
        result = viewer.window.add_plugin_dock_widget(
            plugin_name="napari", widget_name="Features table widget"
        )
        # add_plugin_dock_widget returns (dock, inner_widget)
        feature_widget = result[1] if isinstance(result, tuple) else None
    except Exception:
        return
    try:
        viewer.layers.selection.active = layer
    except Exception:
        pass
    # Hide the leading positional-index column so the user sees only our
    # ``index`` column (the segment label IDs) rather than two index-like
    # columns.  Best-effort: silently skip if the widget structure differs.
    try:
        feature_widget.table.setColumnHidden(0, True)
    except Exception:
        pass
