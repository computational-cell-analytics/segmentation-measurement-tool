"""Napari widget for cell-nucleus measurements."""

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

from segmentation_measurement._groups import (
    ROLE_INTENSITY_IMAGE,
    ROLE_NUCLEUS_SEGMENTATION,
    ROLE_SEGMENTATION,
    iter_group_members,
    list_groups,
    subscribe,
)
from segmentation_measurement._layer_features import (
    merge_features_into_layer,
    show_features_table,
)

_AXIS_LABELS_2D = ("Y", "X")
_AXIS_LABELS_3D = ("Z", "Y", "X")
_NO_IMAGE = "(none)"
_TARGET_SINGLE = "<single layer>"


class CellNucleusWidget(QWidget):
    """Widget for measuring per-cell properties combining cell and nucleus segmentations.

    The result is merged into each cell-segmentation layer's ``features``
    and shown in napari's built-in *Features Table* dock.

    Scale spinboxes are populated from the resolved cell-segmentation
    layer's physical pixel/voxel size or 1.0 if not set.  One spinbox per
    spatial dimension (2 for 2D, 3 for 3D data).  The intensity image is
    optional.

    The *Target* combo selects what to measure:

    * ``<single layer>`` (default): operate on the layers chosen via the
      cell, nucleus, and (optional) intensity-image combos.  Original
      behaviour.
    * a group name: iterate over the group's positions, pairing
      ``segmentation[i]`` with ``nucleus_segmentation[i]`` and
      (optionally) ``intensity_image[i]``.  The group must define a
      non-empty ``nucleus_segmentation`` role; ``intensity_image`` is
      used when present.
    """

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
        self._scale_spins: list[QDoubleSpinBox] = []
        self._scale_layout: QVBoxLayout | None = None
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

        layout.addStretch()

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

        self._cell_combo.blockSignals(True)
        self._cell_combo.clear()
        self._cell_combo.addItems(label_layers)
        if current_cell in label_layers:
            self._cell_combo.setCurrentText(current_cell)
        self._cell_combo.blockSignals(False)

        self._nuc_combo.blockSignals(True)
        self._nuc_combo.clear()
        self._nuc_combo.addItems(label_layers)
        if current_nuc in label_layers:
            self._nuc_combo.setCurrentText(current_nuc)
        self._nuc_combo.blockSignals(False)

        self._img_combo.blockSignals(True)
        self._img_combo.clear()
        self._img_combo.addItem(_NO_IMAGE)
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
        if current in items:
            self._target_combo.setCurrentText(current)
        else:
            self._target_combo.setCurrentText(_TARGET_SINGLE)
        self._target_combo.blockSignals(False)
        self._on_target_changed(self._target_combo.currentText())

    def _on_target_changed(self, target: str) -> None:
        is_group = target != _TARGET_SINGLE
        self._cell_combo.setEnabled(not is_group)
        self._nuc_combo.setEnabled(not is_group)
        self._img_combo.setEnabled(not is_group)
        if not is_group:
            self._on_cell_seg_changed(self._cell_combo.currentText())
            return
        try:
            members = iter_group_members(self._viewer, target)
        except KeyError:
            return
        if not members:
            return
        first = members[0]
        cell = first.get(ROLE_SEGMENTATION)
        nuc = first.get(ROLE_NUCLEUS_SEGMENTATION)
        img = first.get(ROLE_INTENSITY_IMAGE)
        if cell and cell in self._viewer.layers:
            self._cell_combo.blockSignals(True)
            self._cell_combo.setCurrentText(cell)
            self._cell_combo.blockSignals(False)
            self._populate_scale_from_layer(cell)
        if nuc and nuc in self._viewer.layers:
            self._nuc_combo.blockSignals(True)
            self._nuc_combo.setCurrentText(nuc)
            self._nuc_combo.blockSignals(False)
        self._img_combo.blockSignals(True)
        if img and img in self._viewer.layers:
            self._img_combo.setCurrentText(img)
        else:
            self._img_combo.setCurrentText(_NO_IMAGE)
        self._img_combo.blockSignals(False)

    def _on_cell_seg_changed(self, name: str) -> None:
        if not name or name not in [layer.name for layer in self._viewer.layers]:
            return
        self._populate_scale_from_layer(name)

    def _populate_scale_from_layer(self, name: str) -> None:
        layer = self._viewer.layers[name]
        ndim = layer.data.ndim
        raw_scale = [float(s) for s in layer.scale[-ndim:]]
        scale_values = [s if s != 0.0 else 1.0 for s in raw_scale]
        self._rebuild_scale_spins(ndim, scale_values)

    def _resolve_targets(self) -> list[tuple[str, str, str | None]]:
        """Return list of (cell, nucleus, image-or-None) triples."""
        target = self._target_combo.currentText()
        if target == _TARGET_SINGLE:
            cell = self._cell_combo.currentText()
            nuc = self._nuc_combo.currentText()
            img_name = self._img_combo.currentText()
            img = (
                img_name
                if img_name and img_name != _NO_IMAGE
                else None
            )
            if not cell or not nuc:
                return []
            return [(cell, nuc, img)]
        try:
            members = iter_group_members(self._viewer, target)
        except KeyError:
            return []
        triples = []
        for member in members:
            cell = member.get(ROLE_SEGMENTATION)
            nuc = member.get(ROLE_NUCLEUS_SEGMENTATION)
            img = member.get(ROLE_INTENSITY_IMAGE)
            if cell is None or nuc is None:
                raise ValueError(
                    f"Group '{target}' member with cell '{cell}' has no "
                    f"nucleus segmentation. Add nucleus layers to the group "
                    f"definition for batch cell-nucleus measurement."
                )
            triples.append((cell, nuc, img))
        return triples

    def _run_measurement(self) -> None:
        from segmentation_measurement.cell_nucleus import measure_cell_nucleus
        triples = self._resolve_targets()
        if not triples or not self._scale_spins:
            return
        spin_scale = tuple(spin.value() for spin in self._scale_spins)
        first_layer = None
        for cell_name, nuc_name, img_name in triples:
            if cell_name not in self._viewer.layers:
                raise ValueError(
                    f"Target cell layer '{cell_name}' is not in the viewer."
                )
            if nuc_name not in self._viewer.layers:
                raise ValueError(
                    f"Target nucleus layer '{nuc_name}' is not in the viewer."
                )
            cell_layer = self._viewer.layers[cell_name]
            nuc_data = self._viewer.layers[nuc_name].data
            intensity = (
                self._viewer.layers[img_name].data
                if img_name and img_name in self._viewer.layers
                else None
            )
            ndim = cell_layer.data.ndim
            if len(spin_scale) >= ndim:
                layer_scale = tuple(spin_scale[-ndim:])
            else:
                layer_scale = tuple(
                    list(spin_scale) + [1.0] * (ndim - len(spin_scale))
                )
            df = measure_cell_nucleus(
                cell_layer.data, nuc_data, scale=layer_scale,
                intensity_image=intensity,
            )
            merge_features_into_layer(cell_layer, df)
            if first_layer is None:
                first_layer = cell_layer
        if first_layer is not None:
            show_features_table(self._viewer, first_layer)
