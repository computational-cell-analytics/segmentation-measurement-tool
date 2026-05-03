"""Napari widget for intensity measurements."""

from __future__ import annotations

import pandas as pd
import napari
from qtpy.QtWidgets import (
    QComboBox,
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

from segmentation_measurement._utils import populate_table_widget, register_table, save_table


class IntensityWidget(QWidget):
    """Widget for measuring per-segment intensities."""

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
        seg_layout.addWidget(self._seg_combo)
        layout.addLayout(seg_layout)

        img_layout = QHBoxLayout()
        img_layout.addWidget(QLabel("Intensity image:"))
        self._img_combo = QComboBox()
        img_layout.addWidget(self._img_combo)
        layout.addLayout(img_layout)

        self._measure_btn = QPushButton("Measure intensities")
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
        from napari.layers import Image, Labels
        label_layers = [
            layer.name for layer in self._viewer.layers if isinstance(layer, Labels)
        ]
        image_layers = [
            layer.name for layer in self._viewer.layers if isinstance(layer, Image)
        ]
        current_seg = self._seg_combo.currentText()
        current_img = self._img_combo.currentText()

        self._seg_combo.clear()
        self._seg_combo.addItems(label_layers)
        if current_seg in label_layers:
            self._seg_combo.setCurrentText(current_seg)

        self._img_combo.clear()
        self._img_combo.addItems(image_layers)
        if current_img in image_layers:
            self._img_combo.setCurrentText(current_img)

    def _run_measurement(self) -> None:
        from segmentation_measurement.intensity import measure_intensities
        seg_name = self._seg_combo.currentText()
        img_name = self._img_combo.currentText()
        if not seg_name or not img_name:
            return
        segmentation = self._viewer.layers[seg_name].data
        intensity_image = self._viewer.layers[img_name].data
        self._measurements = measure_intensities(segmentation, intensity_image)
        populate_table_widget(self._table, self._measurements)
        register_table(f"Intensity ({seg_name})", self._measurements)

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
