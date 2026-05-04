"""Napari widget for basic table manipulation."""

from __future__ import annotations

import pandas as pd
import napari
from qtpy.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from segmentation_measurement._utils import (
    get_registered_tables,
    load_table,
    populate_table_widget,
    register_table,
    save_table,
)
from segmentation_measurement.table_manipulation import (
    PROTECTED_COLUMNS,
    drop_columns,
    merge_tables,
)


class TableManipulationWidget(QWidget):
    """Widget for loading, merging, and editing measurement tables."""

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
        self._table_data: pd.DataFrame | None = None
        self._table_name: str = "Manipulated table"
        self._setup_ui()
        self._refresh_registry_combos()

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout()
        self.setLayout(outer_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer_layout.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)
        layout = QVBoxLayout()
        inner.setLayout(layout)

        # Source selection: registry or file
        source_group = QGroupBox("Load table")
        source_layout = QVBoxLayout()

        reg_layout = QHBoxLayout()
        reg_layout.addWidget(QLabel("From plugin:"))
        self._source_combo = QComboBox()
        reg_layout.addWidget(self._source_combo)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_registry_combos)
        reg_layout.addWidget(refresh_btn)
        load_reg_btn = QPushButton("Load")
        load_reg_btn.clicked.connect(self._load_from_registry)
        reg_layout.addWidget(load_reg_btn)
        source_layout.addLayout(reg_layout)

        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("From file:"))
        load_file_btn = QPushButton("Load file...")
        load_file_btn.clicked.connect(self._load_from_file)
        file_layout.addWidget(load_file_btn)
        source_layout.addLayout(file_layout)

        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # Current table display
        table_group = QGroupBox("Current table")
        table_layout = QVBoxLayout()
        self._table_label = QLabel("No table loaded.")
        table_layout.addWidget(self._table_label)
        self._table = QTableWidget()
        self._table.setMinimumHeight(150)
        table_layout.addWidget(self._table)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # Drop column
        drop_group = QGroupBox("Drop column")
        drop_layout = QHBoxLayout()
        drop_layout.addWidget(QLabel("Column:"))
        self._drop_combo = QComboBox()
        drop_layout.addWidget(self._drop_combo)
        drop_btn = QPushButton("Drop")
        drop_btn.clicked.connect(self._drop_column)
        drop_layout.addWidget(drop_btn)
        drop_group.setLayout(drop_layout)
        layout.addWidget(drop_group)

        # Merge with another registered table
        merge_group = QGroupBox("Merge with table")
        merge_layout = QHBoxLayout()
        merge_layout.addWidget(QLabel("Other table:"))
        self._merge_combo = QComboBox()
        merge_layout.addWidget(self._merge_combo)
        merge_btn = QPushButton("Merge")
        merge_btn.clicked.connect(self._merge_with_selected)
        merge_layout.addWidget(merge_btn)
        merge_group.setLayout(merge_layout)
        layout.addWidget(merge_group)

        # Save
        save_btn = QPushButton("Save table")
        save_btn.clicked.connect(self._save_table)
        layout.addWidget(save_btn)

    def _refresh_registry_combos(self) -> None:
        names = list(get_registered_tables().keys())
        for combo in (self._source_combo, self._merge_combo):
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            if current in names:
                combo.setCurrentText(current)
            combo.blockSignals(False)

    def _set_current_table(self, df: pd.DataFrame, name: str) -> None:
        self._table_data = df.reset_index(drop=True)
        self._table_name = name
        self._table_label.setText(f"Loaded: {name} ({len(df)} rows, {len(df.columns)} columns)")
        populate_table_widget(self._table, self._table_data)
        self._update_drop_combo()
        register_table(name, self._table_data)
        self._refresh_registry_combos()

    def _update_drop_combo(self) -> None:
        self._drop_combo.blockSignals(True)
        self._drop_combo.clear()
        if self._table_data is not None:
            droppable = [c for c in self._table_data.columns if c not in PROTECTED_COLUMNS]
            self._drop_combo.addItems(droppable)
        self._drop_combo.blockSignals(False)

    def _load_from_registry(self) -> None:
        name = self._source_combo.currentText()
        if not name:
            return
        tables = get_registered_tables()
        if name not in tables:
            return
        self._set_current_table(tables[name].copy(), name)

    def _load_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load table",
            "",
            "Tables (*.csv *.tsv *.xlsx);;All Files (*)",
        )
        if not path:
            return
        try:
            df = load_table(path)
        except Exception as exc:  # pragma: no cover - error feedback
            QMessageBox.critical(self, "Load failed", f"Could not read table:\n{exc}")
            return
        if "label" not in df.columns:
            QMessageBox.warning(
                self,
                "Missing label column",
                "The loaded table does not contain a 'label' column.",
            )
            return
        from pathlib import Path
        self._set_current_table(df, Path(path).stem)

    def _drop_column(self) -> None:
        if self._table_data is None:
            return
        column = self._drop_combo.currentText()
        if not column:
            return
        try:
            new_df = drop_columns(self._table_data, column)
        except ValueError as exc:  # pragma: no cover - defensive; combo is in sync
            QMessageBox.warning(self, "Drop failed", str(exc))
            return
        self._set_current_table(new_df, self._table_name)

    def _merge_with_selected(self) -> None:
        if self._table_data is None:
            QMessageBox.information(
                self, "No table", "Load a table first before merging."
            )
            return
        other_name = self._merge_combo.currentText()
        if not other_name:
            return
        tables = get_registered_tables()
        if other_name not in tables:
            return
        other = tables[other_name]
        try:
            merged = merge_tables([self._table_data, other])
        except ValueError as exc:
            QMessageBox.warning(self, "Merge failed", str(exc))
            return
        self._set_current_table(merged, self._table_name)

    def _save_table(self) -> None:
        if self._table_data is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save table",
            "",
            "CSV (*.csv);;TSV (*.tsv);;Excel (*.xlsx);;All Files (*)",
        )
        if path:
            save_table(self._table_data, path)
