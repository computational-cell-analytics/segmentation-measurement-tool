"""Napari widget for intensity measurements."""

from __future__ import annotations

import napari
from qtpy.QtWidgets import (
    QComboBox,
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


class IntensityWidget(QWidget):
    """Widget for measuring per-segment intensities.

    The result is merged into the source layer's ``features`` and shown in
    napari's built-in *Features Table* dock, which is opened automatically.
    """

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
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

        layout.addStretch()

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
        seg_layer = self._viewer.layers[seg_name]
        intensity_image = self._viewer.layers[img_name].data
        df = measure_intensities(seg_layer.data, intensity_image)
        merge_features_into_layer(seg_layer, df)
        show_features_table(self._viewer, seg_layer)
