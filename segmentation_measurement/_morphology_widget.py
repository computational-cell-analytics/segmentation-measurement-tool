"""Napari widget for morphology measurements."""

from __future__ import annotations

import pandas as pd
import napari
from qtpy.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from segmentation_measurement._utils import populate_table_widget, save_table


class MorphologyWidget(QWidget):
    """Widget for measuring per-segment morphological properties."""

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
        self._measurements: pd.DataFrame | None = None
        self._setup_ui()
        self._viewer.layers.events.inserted.connect(self._update_layer_combos)
        self._viewer.layers.events.removed.connect(self._update_layer_combos)
        self._update_layer_combos()

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

        seg_layout = QHBoxLayout()
        seg_layout.addWidget(QLabel("Segmentation:"))
        self._seg_combo = QComboBox()
        self._seg_combo.currentTextChanged.connect(self._on_seg_changed)
        seg_layout.addWidget(self._seg_combo)
        layout.addLayout(seg_layout)

        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Pixel/voxel size:"))
        self._scale_spin = QDoubleSpinBox()
        self._scale_spin.setRange(1e-9, 1e9)
        self._scale_spin.setDecimals(6)
        self._scale_spin.setValue(1.0)
        scale_layout.addWidget(self._scale_spin)
        layout.addLayout(scale_layout)

        self._measure_btn = QPushButton("Measure morphology")
        self._measure_btn.clicked.connect(self._run_measurement)
        layout.addWidget(self._measure_btn)

        table_group = QGroupBox("Measurements")
        table_layout = QVBoxLayout()
        self._table = QTableWidget()
        self._table.setMinimumHeight(150)
        table_layout.addWidget(self._table)
        save_btn = QPushButton("Save table")
        save_btn.clicked.connect(self._save_table)
        table_layout.addWidget(save_btn)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

    def _update_layer_combos(self, event: object = None) -> None:
        from napari.layers import Labels
        label_layers = [
            layer.name for layer in self._viewer.layers if isinstance(layer, Labels)
        ]
        current = self._seg_combo.currentText()
        self._seg_combo.clear()
        self._seg_combo.addItems(label_layers)
        if current in label_layers:
            self._seg_combo.setCurrentText(current)

    def _on_seg_changed(self, name: str) -> None:
        """Update scale spinbox from the selected label layer's scale."""
        if not name or name not in [l.name for l in self._viewer.layers]:
            return
        layer = self._viewer.layers[name]
        scale_values = [s for s in layer.scale if s != 0]
        if scale_values:
            # Use the mean of non-trivial (non-1) scale values if available
            import numpy as np
            self._scale_spin.setValue(float(np.mean(scale_values)))

    def _run_measurement(self) -> None:
        from segmentation_measurement.morphology import measure_morphology
        seg_name = self._seg_combo.currentText()
        if not seg_name:
            return
        segmentation = self._viewer.layers[seg_name].data
        scale = self._scale_spin.value()
        self._measurements = measure_morphology(segmentation, scale=scale)
        populate_table_widget(self._table, self._measurements)

    def _save_table(self) -> None:
        if self._measurements is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save measurements",
            "",
            "CSV (*.csv);;TSV (*.tsv);;Excel (*.xlsx);;All Files (*)",
        )
        if path:
            save_table(self._measurements, path)
