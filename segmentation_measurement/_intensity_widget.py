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

from segmentation_measurement._groups import (
    ROLE_INTENSITY_IMAGE,
    ROLE_SEGMENTATION,
    iter_group_members,
    list_groups,
    subscribe,
)
from segmentation_measurement._layer_features import (
    merge_features_into_layer,
    show_features_table,
)

_TARGET_SINGLE = "<single layer>"


class IntensityWidget(QWidget):
    """Widget for measuring per-segment intensities.

    The result is merged into each source layer's ``features`` and shown
    in napari's built-in *Features Table* dock, which is opened
    automatically on the first measured layer.

    The *Target* combo selects what to measure:

    * ``<single layer>`` (default): operate on the layer chosen in the
      *Segmentation* combo together with the *Intensity image* combo.
      Original behaviour.
    * a group name: iterate over the group's segmentation layers paired
      by position with the group's intensity images.  The group must
      define a non-empty ``intensity_image`` role.
    """

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
        self._setup_ui()
        self._viewer.layers.events.inserted.connect(self._update_layer_combos)
        self._viewer.layers.events.removed.connect(self._update_layer_combos)
        self._unsubscribe = subscribe(self._viewer, self._update_target_combo)
        self.destroyed.connect(lambda *_: self._unsubscribe())
        self._update_target_combo()
        self._update_layer_combos()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)

        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Target:"))
        self._target_combo = QComboBox()
        self._target_combo.currentTextChanged.connect(self._on_target_changed)
        target_layout.addWidget(self._target_combo)
        layout.addLayout(target_layout)

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

        self._seg_combo.blockSignals(True)
        self._seg_combo.clear()
        self._seg_combo.addItems(label_layers)
        if current_seg in label_layers:
            self._seg_combo.setCurrentText(current_seg)
        self._seg_combo.blockSignals(False)

        self._img_combo.blockSignals(True)
        self._img_combo.clear()
        self._img_combo.addItems(image_layers)
        if current_img in image_layers:
            self._img_combo.setCurrentText(current_img)
        self._img_combo.blockSignals(False)

        self._on_target_changed(self._target_combo.currentText())

    def _update_target_combo(self) -> None:
        groups = list_groups(self._viewer)
        current = self._target_combo.currentText()
        self._target_combo.blockSignals(True)
        self._target_combo.clear()
        self._target_combo.addItem(_TARGET_SINGLE)
        self._target_combo.addItems(groups)
        items = [
            self._target_combo.itemText(i)
            for i in range(self._target_combo.count())
        ]
        if current in groups:
            self._target_combo.setCurrentText(current)
        elif len(groups) == 1:
            self._target_combo.setCurrentText(groups[0])
        elif current in items:
            self._target_combo.setCurrentText(current)
        else:
            self._target_combo.setCurrentText(_TARGET_SINGLE)
        self._target_combo.blockSignals(False)
        self._on_target_changed(self._target_combo.currentText())

    def _on_target_changed(self, target: str) -> None:
        is_group = target != _TARGET_SINGLE
        self._seg_combo.setEnabled(not is_group)
        self._img_combo.setEnabled(not is_group)
        if not is_group:
            return
        try:
            members = iter_group_members(self._viewer, target)
        except KeyError:
            return
        if not members:
            return
        first = members[0]
        seg = first.get(ROLE_SEGMENTATION)
        img = first.get(ROLE_INTENSITY_IMAGE)
        if seg and seg in self._viewer.layers:
            self._seg_combo.blockSignals(True)
            self._seg_combo.setCurrentText(seg)
            self._seg_combo.blockSignals(False)
        if img and img in self._viewer.layers:
            self._img_combo.blockSignals(True)
            self._img_combo.setCurrentText(img)
            self._img_combo.blockSignals(False)

    def _resolve_targets(self) -> list[tuple[str, str]]:
        """Return list of (segmentation, intensity image) layer name pairs."""
        target = self._target_combo.currentText()
        if target == _TARGET_SINGLE:
            seg = self._seg_combo.currentText()
            img = self._img_combo.currentText()
            if not seg or not img:
                return []
            return [(seg, img)]
        try:
            members = iter_group_members(self._viewer, target)
        except KeyError:
            return []
        pairs = []
        for member in members:
            seg = member.get(ROLE_SEGMENTATION)
            img = member.get(ROLE_INTENSITY_IMAGE)
            if seg is None or img is None:
                raise ValueError(
                    f"Group '{target}' member with segmentation '{seg}' has no "
                    f"intensity image. Add intensity images to the group "
                    f"definition for batch intensity measurement."
                )
            pairs.append((seg, img))
        return pairs

    def _run_measurement(self) -> None:
        from segmentation_measurement.intensity import measure_intensities
        pairs = self._resolve_targets()
        if not pairs:
            return
        first_layer = None
        for seg_name, img_name in pairs:
            if seg_name not in self._viewer.layers:
                raise ValueError(
                    f"Target segmentation '{seg_name}' is not in the viewer."
                )
            if img_name not in self._viewer.layers:
                raise ValueError(
                    f"Target image '{img_name}' is not in the viewer."
                )
            seg_layer = self._viewer.layers[seg_name]
            intensity_image = self._viewer.layers[img_name].data
            df = measure_intensities(seg_layer.data, intensity_image)
            merge_features_into_layer(seg_layer, df)
            if first_layer is None:
                first_layer = seg_layer
        if first_layer is not None:
            show_features_table(self._viewer, first_layer)
