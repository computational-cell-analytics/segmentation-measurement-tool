"""Basic table manipulation utilities for measurement DataFrames."""

from __future__ import annotations

from functools import reduce
from typing import Iterable, Sequence, Union

import pandas as pd


def merge_tables(
    tables: Sequence[pd.DataFrame], on: str = "label"
) -> pd.DataFrame:
    """Merge multiple measurement tables on a shared key column.

    Performs an outer join on ``on`` so that label IDs present in some but not
    all tables are preserved (missing values become NaN).  All tables must
    contain the ``on`` column, and the *other* columns must be disjoint
    between tables — otherwise the merge would silently rename or duplicate
    measurement columns.  Use :func:`drop_columns` first to remove conflicts
    if needed.

    Args:
        tables (Sequence[pd.DataFrame]): Two or more measurement tables to
            merge.
        on (str): Name of the key column shared between tables. Defaults to
            ``"label"``.

    Returns:
        pd.DataFrame: A single table containing the union of all rows and
            columns.

    Raises:
        ValueError: If fewer than two tables are provided, if any table is
            missing the ``on`` column, or if non-``on`` columns overlap
            between tables.
    """
    tables = list(tables)
    if len(tables) < 2:
        raise ValueError("merge_tables requires at least two tables.")

    seen_columns: set[str] = set()
    for i, table in enumerate(tables):
        if on not in table.columns:
            raise ValueError(
                f"Table at index {i} is missing the key column '{on}'."
            )
        other_columns = set(table.columns) - {on}
        conflicts = seen_columns & other_columns
        if conflicts:
            raise ValueError(
                f"Column(s) {sorted(conflicts)} appear in more than one "
                f"table; drop them before merging."
            )
        seen_columns.update(other_columns)

    merged = reduce(lambda left, right: pd.merge(left, right, on=on, how="outer"), tables)
    return merged.sort_values(on).reset_index(drop=True)


PROTECTED_COLUMNS = ("label",)


def drop_columns(
    table: pd.DataFrame, columns: Union[str, Iterable[str]]
) -> pd.DataFrame:
    """Return a copy of ``table`` with the specified columns removed.

    The ``label`` column is the standard segment-identifier key throughout
    this package and may never be dropped.

    Args:
        table (pd.DataFrame): Input measurement table.
        columns (str | Iterable[str]): Single column name or an iterable of
            column names to drop.

    Returns:
        pd.DataFrame: New DataFrame without the dropped columns.

    Raises:
        ValueError: If any requested column is not present in ``table``, or
            if a protected column (``label``) is requested.
    """
    if isinstance(columns, str):
        columns_list = [columns]
    else:
        columns_list = list(columns)
    protected = [c for c in columns_list if c in PROTECTED_COLUMNS]
    if protected:
        raise ValueError(
            f"Column(s) {protected} are protected and cannot be dropped."
        )
    missing = [c for c in columns_list if c not in table.columns]
    if missing:
        raise ValueError(f"Column(s) {missing} not found in table.")
    return table.drop(columns=columns_list)
