"""Napari widget for cell-nucleus measurements."""

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

from segmentation_measurement._utils import populate_table_widget, register_table, save_table

_AXIS_LABELS_2D = ("Y", "X")
_AXIS_LABELS_3D = ("Z", "Y", "X")
_NO_IMAGE = "(none)"


class CellNucleusWidget(QWidget):
    """Widget for measuring per-cell properties combining cell and nucleus segmentations.

    Scale spinboxes are populated from the cell segmentation layer's physical
    pixel/voxel size (from its ``scale`` attribute) or 1.0 if not set.  One
    spinbox per spatial dimension (2 for 2D, 3 for 3D data).  The intensity
    image selection is optional.
    """

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
        self._measurements: pd.DataFrame | None = None
        self._scale_spins: list[QDoubleSpinBox] = []
        self._scale_layout: QVBoxLayout | None = None
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

        cell_layout = QHBoxLayout()
        cell_layout.addWidget(QLabel("Cell segmentation:"))
        self._cell_combo = QComboBox()
        self._cell_combo.currentTextChanged.connect(self._on_cell_seg_changed)
        cell_layout.addWidget(self._cell_combo)
        layout.addLayout(cell_layout)

        nuc_layout = QHBoxLayout()
        nuc_layout.addWidget(QLabel("Nucleus segmentation:"))
        self._nuc_combo = QComboBox()
        nuc_layout.addWidget(self._nuc_combo)
        layout.addLayout(nuc_layout)

        img_layout = QHBoxLayout()
        img_layout.addWidget(QLabel("Intensity image (optional):"))
        self._img_combo = QComboBox()
        img_layout.addWidget(self._img_combo)
        layout.addLayout(img_layout)

        scale_group = QGroupBox("Physical pixel/voxel size")
        self._scale_layout = QVBoxLayout()
        scale_group.setLayout(self._scale_layout)
        layout.addWidget(scale_group)
        self._rebuild_scale_spins(2, [1.0, 1.0])

        self._measure_btn = QPushButton("Measure cell-nucleus")
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

    def _rebuild_scale_spins(self, ndim: int, scale_values: list) -> None:
        while self._scale_layout.count():
            item = self._scale_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._scale_spins = []

        axis_labels = _AXIS_LABELS_2D if ndim == 2 else _AXIS_LABELS_3D
        for i, axis in enumerate(axis_labels):
            row_widget = QWidget()
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(f"{axis}:"))
            spin = QDoubleSpinBox()
            spin.setRange(1e-9, 1e9)
            spin.setDecimals(6)
            spin.setValue(scale_values[i] if i < len(scale_values) else 1.0)
            self._scale_spins.append(spin)
            row.addWidget(spin)
            row_widget.setLayout(row)
            self._scale_layout.addWidget(row_widget)

    def _update_layer_combos(self, event: object = None) -> None:
        from napari.layers import Image, Labels
        label_layers = [
            layer.name for layer in self._viewer.layers if isinstance(layer, Labels)
        ]
        image_layers = [
            layer.name for layer in self._viewer.layers if isinstance(layer, Image)
        ]

        current_cell = self._cell_combo.currentText()
        current_nuc = self._nuc_combo.currentText()
        current_img = self._img_combo.currentText()

        self._cell_combo.clear()
        self._cell_combo.addItems(label_layers)
        if current_cell in label_layers:
            self._cell_combo.setCurrentText(current_cell)

        self._nuc_combo.clear()
        self._nuc_combo.addItems(label_layers)
        if current_nuc in label_layers:
            self._nuc_combo.setCurrentText(current_nuc)

        self._img_combo.clear()
        self._img_combo.addItem(_NO_IMAGE)
        self._img_combo.addItems(image_layers)
        if current_img in image_layers:
            self._img_combo.setCurrentText(current_img)

    def _on_cell_seg_changed(self, name: str) -> None:
        if not name or name not in [layer.name for layer in self._viewer.layers]:
            return
        layer = self._viewer.layers[name]
        ndim = layer.data.ndim
        raw_scale = [float(s) for s in layer.scale[-ndim:]]
        scale_values = [s if s != 0.0 else 1.0 for s in raw_scale]
        self._rebuild_scale_spins(ndim, scale_values)

    def _run_measurement(self) -> None:
        from segmentation_measurement.cell_nucleus import measure_cell_nucleus
        cell_name = self._cell_combo.currentText()
        nuc_name = self._nuc_combo.currentText()
        if not cell_name or not nuc_name or not self._scale_spins:
            return
        cell_seg = self._viewer.layers[cell_name].data
        nuc_seg = self._viewer.layers[nuc_name].data

        img_name = self._img_combo.currentText()
        intensity = (
            self._viewer.layers[img_name].data
            if img_name and img_name != _NO_IMAGE
            else None
        )

        scale = tuple(spin.value() for spin in self._scale_spins)
        self._measurements = measure_cell_nucleus(
            cell_seg, nuc_seg, scale=scale, intensity_image=intensity
        )
        populate_table_widget(self._table, self._measurements)
        register_table(f"Cell-Nucleus ({cell_name})", self._measurements)

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
