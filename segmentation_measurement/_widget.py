"""Napari plugin widget for post-processing."""

from __future__ import annotations

import napari
from qtpy.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class PostprocessingWidget(QWidget):
    """Widget for applying post-processing operations to segmentation layers."""

    def __init__(self, viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = viewer
        self._setup_ui()
        self._viewer.layers.events.inserted.connect(self._update_layer_combos)
        self._viewer.layers.events.removed.connect(self._update_layer_combos)
        self._update_layer_combos()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)

        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Input segmentation:"))
        self._input_combo = QComboBox()
        input_layout.addWidget(self._input_combo)
        layout.addLayout(input_layout)

        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output name:"))
        self._output_combo = QComboBox()
        self._output_combo.setEditable(True)
        output_layout.addWidget(self._output_combo)
        layout.addLayout(output_layout)

        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Method:"))
        self._method_combo = QComboBox()
        self._method_combo.addItems([
            "filter_small_segments",
            "remove_small_holes",
            "ring_mask",
        ])
        self._method_combo.currentIndexChanged.connect(self._on_method_changed)
        method_layout.addWidget(self._method_combo)
        layout.addLayout(method_layout)

        self._params_stack = QStackedWidget()

        fss_group = QGroupBox("Parameters")
        fss_layout = QHBoxLayout()
        fss_layout.addWidget(QLabel("Min size:"))
        self._min_size_spin = QSpinBox()
        self._min_size_spin.setRange(1, 10_000_000)
        self._min_size_spin.setValue(100)
        fss_layout.addWidget(self._min_size_spin)
        fss_group.setLayout(fss_layout)
        self._params_stack.addWidget(fss_group)

        rsh_group = QGroupBox("Parameters")
        rsh_layout = QHBoxLayout()
        rsh_layout.addWidget(QLabel("Max hole size:"))
        self._max_hole_size_spin = QSpinBox()
        self._max_hole_size_spin.setRange(1, 10_000_000)
        self._max_hole_size_spin.setValue(50)
        rsh_layout.addWidget(self._max_hole_size_spin)
        rsh_group.setLayout(rsh_layout)
        self._params_stack.addWidget(rsh_group)

        rm_group = QGroupBox("Parameters")
        rm_layout = QHBoxLayout()
        rm_layout.addWidget(QLabel("Ring width:"))
        self._ring_width_spin = QSpinBox()
        self._ring_width_spin.setRange(1, 1000)
        self._ring_width_spin.setValue(5)
        rm_layout.addWidget(self._ring_width_spin)
        rm_group.setLayout(rm_layout)
        self._params_stack.addWidget(rm_group)

        layout.addWidget(self._params_stack)

        self._run_btn = QPushButton("Run")
        self._run_btn.clicked.connect(self._run)
        layout.addWidget(self._run_btn)

    def _on_method_changed(self, index: int) -> None:
        self._params_stack.setCurrentIndex(index)

    def _update_layer_combos(self, event: object = None) -> None:
        from napari.layers import Labels
        label_layers = [
            layer.name for layer in self._viewer.layers if isinstance(layer, Labels)
        ]

        current_input = self._input_combo.currentText()
        current_output = self._output_combo.currentText()

        self._input_combo.clear()
        self._input_combo.addItems(label_layers)
        if current_input in label_layers:
            self._input_combo.setCurrentText(current_input)

        self._output_combo.clear()
        self._output_combo.addItems(label_layers)
        self._output_combo.addItem("postprocessed")
        if current_output:
            self._output_combo.setCurrentText(current_output)

    def _run(self) -> None:
        from segmentation_measurement.postprocessing import (
            compute_ring_mask,
            filter_small_segments,
            remove_small_holes,
        )

        input_name = self._input_combo.currentText()
        output_name = self._output_combo.currentText()
        method = self._method_combo.currentText()

        if not input_name or not output_name:
            return

        segmentation = self._viewer.layers[input_name].data.copy()

        if method == "filter_small_segments":
            result = filter_small_segments(segmentation, self._min_size_spin.value())
        elif method == "remove_small_holes":
            result = remove_small_holes(segmentation, self._max_hole_size_spin.value())
        elif method == "ring_mask":
            result = compute_ring_mask(segmentation, self._ring_width_spin.value())
        else:
            return

        existing_names = [layer.name for layer in self._viewer.layers]
        if output_name in existing_names:
            self._viewer.layers[output_name].data = result
        else:
            self._viewer.add_labels(result, name=output_name)
