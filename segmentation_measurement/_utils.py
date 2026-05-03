"""Shared utilities for measurement modules and widgets."""

from __future__ import annotations

from pathlib import Path

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


_TABLE_REGISTRY: dict[str, pd.DataFrame] = {}


def register_table(name: str, df: pd.DataFrame) -> None:
    """Register a measurement DataFrame in the in-memory table registry.

    Args:
        name (str): Identifier shown in the threshold widget's table combo.
        df (pd.DataFrame): Measurement table to register.
    """
    _TABLE_REGISTRY[name] = df.copy()


def get_registered_tables() -> dict[str, pd.DataFrame]:
    """Return a snapshot of all currently registered tables.

    Returns:
        dict[str, pd.DataFrame]: Mapping of name → DataFrame.
    """
    return dict(_TABLE_REGISTRY)


def clear_table_registry() -> None:
    """Remove all entries from the table registry (used in tests)."""
    _TABLE_REGISTRY.clear()


def populate_table_widget(table_widget: object, df: pd.DataFrame) -> None:
    """Fill a QTableWidget with DataFrame contents.

    Args:
        table_widget: A ``QTableWidget`` instance.
        df (pd.DataFrame): Data to display.
    """
    from qtpy.QtWidgets import QTableWidgetItem

    table_widget.setRowCount(len(df))
    table_widget.setColumnCount(len(df.columns))
    table_widget.setHorizontalHeaderLabels(list(df.columns))
    for row_idx in range(len(df)):
        for col_idx, val in enumerate(df.iloc[row_idx]):
            text = f"{val:.4f}" if isinstance(val, float) else str(val)
            table_widget.setItem(row_idx, col_idx, QTableWidgetItem(text))
    table_widget.resizeColumnsToContents()
