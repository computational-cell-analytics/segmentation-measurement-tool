"""Napari widget for morphology measurements."""

from __future__ import annotations

import napari
from qtpy.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from segmentation_measurement._layer_features import (
    merge_features_into_layer,
    show_features_table,
)

_AXIS_LABELS_2D = ("Y", "X")
_AXIS_LABELS_3D = ("Z", "Y", "X")


class MorphologyWidget(QWidget):
    """Widget for measuring per-segment morphological properties.

    The result is merged into the source layer's ``features`` and shown in
    napari's built-in *Features Table* dock, which is opened automatically.

    Scale spinboxes are populated with the selected label layer's physical
    pixel/voxel size (from its ``scale`` attribute) or 1.0 if not set.
    One spinbox per spatial dimension (2 for 2D, 3 for 3D data).
    """

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
        self._scale_spins: list[QDoubleSpinBox] = []
        self._scale_layout: QVBoxLayout | None = None
        self._setup_ui()
        self._viewer.layers.events.inserted.connect(self._update_layer_combos)
        self._viewer.layers.events.removed.connect(self._update_layer_combos)
        self._update_layer_combos()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)

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
        self._rebuild_scale_spins(2, [1.0, 1.0])

        self._measure_btn = QPushButton("Measure morphology")
        self._measure_btn.clicked.connect(self._run_measurement)
        layout.addWidget(self._measure_btn)

        layout.addStretch()

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
        if not name or name not in [layer.name for layer in self._viewer.layers]:
            return
        layer = self._viewer.layers[name]
        ndim = layer.data.ndim
        raw_scale = [float(s) for s in layer.scale[-ndim:]]
        scale_values = [s if s != 0.0 else 1.0 for s in raw_scale]
        self._rebuild_scale_spins(ndim, scale_values)

    def _run_measurement(self) -> None:
        from segmentation_measurement.morphology import measure_morphology
        seg_name = self._seg_combo.currentText()
        if not seg_name or not self._scale_spins:
            return
        seg_layer = self._viewer.layers[seg_name]
        scale = tuple(spin.value() for spin in self._scale_spins)
        df = measure_morphology(seg_layer.data, scale=scale)
        merge_features_into_layer(seg_layer, df)
        show_features_table(self._viewer, seg_layer)
