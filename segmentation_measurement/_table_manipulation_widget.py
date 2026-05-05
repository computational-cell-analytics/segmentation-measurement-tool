"""Napari widget for basic table manipulation on layer features."""

from __future__ import annotations

from pathlib import Path

import napari
import pandas as pd
from qtpy.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from segmentation_measurement._layer_features import (
    merge_features_into_layer,
    show_features_table,
)
from segmentation_measurement._utils import load_table, save_table
from segmentation_measurement.table_manipulation import (
    PROTECTED_COLUMNS,
    drop_columns,
)


class TableManipulationWidget(QWidget):
    """Widget for editing the ``features`` table of a Labels layer.

    The widget operates on the selected Labels layer's ``features``.  It can
    load an external CSV/TSV/XLSX table (which must contain an ``index``
    column) and merge it into the layer's features (overwriting columns on
    conflict), drop a column from the layer's features, and save the
    features to a CSV/TSV/XLSX file.  The napari built-in *Features Table*
    dock is opened automatically after every modification so the result is
    immediately visible.
    """

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
        self._setup_ui()
        self._viewer.layers.events.inserted.connect(self._update_layer_combo)
        self._viewer.layers.events.removed.connect(self._update_layer_combo)
        self._update_layer_combo()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)

        seg_layout = QHBoxLayout()
        seg_layout.addWidget(QLabel("Segmentation:"))
        self._seg_combo = QComboBox()
        self._seg_combo.currentTextChanged.connect(self._on_seg_changed)
        seg_layout.addWidget(self._seg_combo)
        layout.addLayout(seg_layout)

        load_group = QGroupBox("Load table from file")
        load_layout = QHBoxLayout()
        load_btn = QPushButton("Load file...")
        load_btn.clicked.connect(self._load_from_file)
        load_layout.addWidget(load_btn)
        load_group.setLayout(load_layout)
        layout.addWidget(load_group)

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

        save_btn = QPushButton("Save table")
        save_btn.clicked.connect(self._save_table)
        layout.addWidget(save_btn)

        layout.addStretch()

    # ------------------------------------------------------ Layer plumbing ---

    def _update_layer_combo(self, event: object = None) -> None:
        from napari.layers import Labels
        names = [
            layer.name for layer in self._viewer.layers if isinstance(layer, Labels)
        ]
        current = self._seg_combo.currentText()
        self._seg_combo.blockSignals(True)
        self._seg_combo.clear()
        self._seg_combo.addItems(names)
        if current in names:
            self._seg_combo.setCurrentText(current)
        self._seg_combo.blockSignals(False)
        self._refresh_drop_combo()

    def _on_seg_changed(self, name: str) -> None:
        self._refresh_drop_combo()

    def _seg_layer(self) -> object | None:
        name = self._seg_combo.currentText()
        if not name or name not in [l.name for l in self._viewer.layers]:
            return None
        return self._viewer.layers[name]

    def _current_features(self) -> pd.DataFrame | None:
        seg = self._seg_layer()
        if seg is None:
            return None
        feats = getattr(seg, "features", None)
        if feats is None or len(feats.columns) == 0:
            return None
        return feats

    def _refresh_drop_combo(self) -> None:
        self._drop_combo.blockSignals(True)
        self._drop_combo.clear()
        feats = self._current_features()
        if feats is not None:
            droppable = [c for c in feats.columns if c not in PROTECTED_COLUMNS]
            self._drop_combo.addItems(droppable)
        self._drop_combo.blockSignals(False)

    # ------------------------------------------------------------ Actions ---

    def _load_from_file(self) -> None:
        seg = self._seg_layer()
        if seg is None:
            QMessageBox.information(
                self, "No layer", "Select a Labels layer first."
            )
            return
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
        if "index" not in df.columns:
            QMessageBox.warning(
                self,
                "Missing index column",
                "The loaded table does not contain an 'index' column.",
            )
            return
        merge_features_into_layer(seg, df)
        self._refresh_drop_combo()
        show_features_table(self._viewer, seg)

    def _drop_column(self) -> None:
        seg = self._seg_layer()
        feats = self._current_features()
        if seg is None or feats is None:
            return
        column = self._drop_combo.currentText()
        if not column:
            return
        try:
            new_df = drop_columns(feats, column)
        except ValueError as exc:  # pragma: no cover - combo excludes protected
            QMessageBox.warning(self, "Drop failed", str(exc))
            return
        seg.features = new_df.reset_index(drop=True)
        self._refresh_drop_combo()
        show_features_table(self._viewer, seg)

    def _save_table(self) -> None:
        feats = self._current_features()
        if feats is None:
            return
        seg = self._seg_layer()
        suggested = f"{seg.name}_features.csv" if seg is not None else "features.csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save table",
            suggested,
            "CSV (*.csv);;TSV (*.tsv);;Excel (*.xlsx);;All Files (*)",
        )
        if not path:
            return
        # If the user typed a name without an extension, default to .csv
        if not Path(path).suffix:
            path = path + ".csv"
        save_table(feats, path)
