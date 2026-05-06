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

from segmentation_measurement._groups import (
    ROLE_SEGMENTATION,
    get_group,
    list_groups,
    subscribe,
)
from segmentation_measurement._layer_features import (
    merge_features_into_layer,
    show_features_table,
)

_AXIS_LABELS_2D = ("Y", "X")
_AXIS_LABELS_3D = ("Z", "Y", "X")
_TARGET_SINGLE = "<single layer>"


class MorphologyWidget(QWidget):
    """Widget for measuring per-segment morphological properties.

    The result is merged into each source layer's ``features`` and the
    napari built-in *Features Table* dock is opened on the first
    measured layer.

    Scale spinboxes are populated with the resolved layer's physical
    pixel/voxel size (from its ``scale`` attribute) or 1.0 if not set.
    One spinbox per spatial dimension (2 for 2D, 3 for 3D data).

    The *Target* combo selects what to measure:

    * ``<single layer>`` (default): operate on the layer chosen in the
      *Segmentation* combo.  Original behaviour.
    * a group name: iterate over every layer in that group's
      ``segmentation`` role list, applying the same scale settings to
      each.  The *Segmentation* combo becomes read-only and shows the
      first member.
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

    # --------------------------------------------------------------- UI ---

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

    # --------------------------------------------------------- Plumbing ---

    def _update_layer_combos(self, event: object = None) -> None:
        from napari.layers import Labels
        label_layers = [
            layer.name for layer in self._viewer.layers if isinstance(layer, Labels)
        ]
        current = self._seg_combo.currentText()
        self._seg_combo.blockSignals(True)
        self._seg_combo.clear()
        self._seg_combo.addItems(label_layers)
        if current in label_layers:
            self._seg_combo.setCurrentText(current)
        self._seg_combo.blockSignals(False)
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
        if target == _TARGET_SINGLE:
            self._seg_combo.setEnabled(True)
            self._on_seg_changed(self._seg_combo.currentText())
            return
        self._seg_combo.setEnabled(False)
        try:
            members = get_group(self._viewer, target)
        except KeyError:
            return
        seg_layers = members.get(ROLE_SEGMENTATION, [])
        if not seg_layers:
            return
        first = seg_layers[0]
        if first in self._viewer.layers:
            self._seg_combo.blockSignals(True)
            self._seg_combo.setCurrentText(first)
            self._seg_combo.blockSignals(False)
            self._populate_scale_from_layer(first)

    def _on_seg_changed(self, name: str) -> None:
        if not name or name not in [layer.name for layer in self._viewer.layers]:
            return
        self._populate_scale_from_layer(name)

    def _populate_scale_from_layer(self, name: str) -> None:
        layer = self._viewer.layers[name]
        ndim = layer.data.ndim
        raw_scale = [float(s) for s in layer.scale[-ndim:]]
        scale_values = [s if s != 0.0 else 1.0 for s in raw_scale]
        self._rebuild_scale_spins(ndim, scale_values)

    # --------------------------------------------------------- Targets ---

    def _resolve_targets(self) -> list[str]:
        """Return the segmentation layer names to operate on, in order."""
        target = self._target_combo.currentText()
        if target == _TARGET_SINGLE:
            name = self._seg_combo.currentText()
            return [name] if name else []
        try:
            members = get_group(self._viewer, target)
        except KeyError:
            return []
        return list(members.get(ROLE_SEGMENTATION, []))

    # ------------------------------------------------------ Measurement ---

    def _run_measurement(self) -> None:
        from segmentation_measurement.morphology import measure_morphology
        target_names = self._resolve_targets()
        if not target_names or not self._scale_spins:
            return
        spin_scale = tuple(spin.value() for spin in self._scale_spins)
        first_layer = None
        for name in target_names:
            if name not in self._viewer.layers:
                raise ValueError(
                    f"Target layer '{name}' is not present in the viewer. "
                    "Update the group definition to point at an existing layer."
                )
            layer = self._viewer.layers[name]
            ndim = layer.data.ndim
            if len(spin_scale) >= ndim:
                layer_scale = tuple(spin_scale[-ndim:])
            else:
                layer_scale = tuple(
                    list(spin_scale) + [1.0] * (ndim - len(spin_scale))
                )
            df = measure_morphology(layer.data, scale=layer_scale)
            merge_features_into_layer(layer, df)
            if first_layer is None:
                first_layer = layer
        if first_layer is not None:
            show_features_table(self._viewer, first_layer)
