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


def concat_features_for_group(
    viewer: "napari.Viewer",
    group_name: str,
    role: str = "segmentation",
) -> pd.DataFrame:
    """Concatenate ``features`` across one group's members for a role.

    Pulls ``layer.features`` from each layer in the group's role list and
    stacks them vertically with an added ``_source_layer`` column
    identifying the source layer name.  Used by analysis widgets to run
    a single operation (clustering, classification, thresholding) jointly
    across the members of a batch group.

    Args:
        viewer: napari Viewer instance.
        group_name: Name of the group to pull from.
        role: Role whose layer list is iterated.  Defaults to
            ``'segmentation'``.

    Returns:
        pd.DataFrame: Concatenated frame with the original feature columns
            plus a ``_source_layer`` column.

    Raises:
        KeyError: If the group does not exist or one of its layers is no
            longer present in the viewer.
        ValueError: If the role is undefined or empty for the group, a
            member layer has no features, or feature columns differ across
            members.
    """
    from segmentation_measurement._groups import get_group

    members = get_group(viewer, group_name)
    layers = members.get(role, [])
    if not layers:
        raise ValueError(
            f"Group '{group_name}' has no layers under role '{role}'."
        )

    frames: list[pd.DataFrame] = []
    column_set: set[str] | None = None
    reference_source: str | None = None
    for layer_name in layers:
        if layer_name not in viewer.layers:
            raise KeyError(
                f"Group '{group_name}' role '{role}' references layer "
                f"'{layer_name}', which is not in the viewer."
            )
        layer = viewer.layers[layer_name]
        feats = getattr(layer, "features", None)
        if feats is None or len(feats.columns) == 0:
            raise ValueError(
                f"Layer '{layer_name}' (group '{group_name}', role "
                f"'{role}') has no features. Run a measurement on it first."
            )
        cols = set(feats.columns)
        if column_set is None:
            column_set = cols
            reference_source = layer_name
        elif cols != column_set:
            missing = sorted(column_set - cols)
            extra = sorted(cols - column_set)
            raise ValueError(
                f"Feature columns of layer '{layer_name}' do not match "
                f"those of '{reference_source}'. "
                f"Missing in '{layer_name}': {missing}. "
                f"Extra in '{layer_name}': {extra}."
            )
        frame = feats.copy()
        frame["_source_layer"] = layer_name
        frames.append(frame)

    return pd.concat(frames, ignore_index=True)


def split_and_merge_back(
    viewer: "napari.Viewer",
    df: pd.DataFrame,
    columns: list[str],
) -> None:
    """Split a concatenated frame on ``_source_layer`` and merge per-layer.

    Inverse of :func:`concat_features_across_groups`.  For each unique value
    in ``df['_source_layer']``, takes the rows for that source, selects
    ``['index'] + columns``, and merges them into the corresponding viewer
    layer's ``features`` via :func:`merge_features_into_layer`.

    Args:
        viewer: napari Viewer instance.
        df: DataFrame with at least ``_source_layer`` and ``index`` columns.
        columns: New column names to merge back into each layer's features.
            ``index`` is always merged irrespective of this argument.

    Raises:
        ValueError: If ``df`` is missing ``_source_layer`` or ``index``, or
            any entry of ``columns`` is not a column of ``df``.
        KeyError: If ``df`` references a layer not present in the viewer.
    """
    if "_source_layer" not in df.columns:
        raise ValueError("DataFrame is missing the '_source_layer' column.")
    if "index" not in df.columns:
        raise ValueError("DataFrame is missing the 'index' column.")
    missing_cols = [c for c in columns if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"DataFrame is missing requested column(s): {missing_cols}."
        )
    keep = ["index"] + [c for c in columns if c != "index"]
    for source, sub in df.groupby("_source_layer", sort=False):
        if source not in viewer.layers:
            raise KeyError(
                f"DataFrame references layer '{source}', which is not in "
                f"the viewer."
            )
        layer = viewer.layers[source]
        merge_features_into_layer(layer, sub[keep].reset_index(drop=True))


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
