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

from segmentation_measurement._utils import populate_table_widget, register_table, save_table

_AXIS_LABELS_2D = ("Y", "X")
_AXIS_LABELS_3D = ("Z", "Y", "X")


class MorphologyWidget(QWidget):
    """Widget for measuring per-segment morphological properties.

    Scale spinboxes are populated with the selected label layer's physical
    pixel/voxel size (from its ``scale`` attribute) or 1.0 if not set.
    One spinbox per spatial dimension (2 for 2D, 3 for 3D data).
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

        seg_layout = QHBoxLayout()
        seg_layout.addWidget(QLabel("Segmentation:"))
        self._seg_combo = QComboBox()
        self._seg_combo.currentTextChanged.connect(self._on_seg_changed)
        seg_layout.addWidget(self._seg_combo)
        layout.addLayout(seg_layout)

        scale_group = QGroupBox("Physical pixel/voxel size")
        self._scale_layout = QVBoxLayout()
        scale_group.setLayout(self._scale_layout)
        layout.addWidget(scale_group)
        self._rebuild_scale_spins(2, [1.0, 1.0])  # default before a layer is selected

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

    def _rebuild_scale_spins(self, ndim: int, scale_values: list) -> None:
        """Recreate per-axis spinboxes for the given dimensionality."""
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
        """Rebuild scale spinboxes to match the selected layer's dimensionality and scale."""
        if not name or name not in [layer.name for layer in self._viewer.layers]:
            return
        layer = self._viewer.layers[name]
        ndim = layer.data.ndim
        # layer.scale has one entry per spatial dimension; use last ndim entries
        raw_scale = [float(s) for s in layer.scale[-ndim:]]
        # Replace zeros (unset) with 1.0
        scale_values = [s if s != 0.0 else 1.0 for s in raw_scale]
        self._rebuild_scale_spins(ndim, scale_values)

    def _run_measurement(self) -> None:
        from segmentation_measurement.morphology import measure_morphology
        seg_name = self._seg_combo.currentText()
        if not seg_name or not self._scale_spins:
            return
        segmentation = self._viewer.layers[seg_name].data
        scale = tuple(spin.value() for spin in self._scale_spins)
        self._measurements = measure_morphology(segmentation, scale=scale)
        populate_table_widget(self._table, self._measurements)
        register_table(f"Morphology ({seg_name})", self._measurements)

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
