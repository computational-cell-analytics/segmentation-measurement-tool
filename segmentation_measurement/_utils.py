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
