"""Napari widget for threshold-based categorization of measurement results."""

from __future__ import annotations

import numpy as np
import pandas as pd
import napari
from qtpy.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from segmentation_measurement._layer_features import (
    merge_features_into_layer,
    show_features_table,
)


class ThresholdWidget(QWidget):
    """Widget for categorizing segments based on measurement thresholds.

    Operates on the ``features`` table of the selected Labels layer (as
    populated by the measurement widgets or loaded into the layer via the
    Table Manipulation widget).  Picking the layer triggers a refresh of the
    available numeric columns and the histogram.

    On *Categorize*, the chosen thresholds are applied to the selected column
    and the resulting ``category_id`` / ``category_name`` columns are merged
    back into the source layer's ``features``.  A new label layer is created
    that colours each segment by its category for visualization.
    """

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
        self._threshold_spins: list[QDoubleSpinBox] = []
        self._name_edits: list[QLineEdit] = []
        self._hist_fig = None
        self._hist_ax = None
        self._hist_canvas = None
        self._setup_ui()
        self._viewer.layers.events.inserted.connect(self._update_seg_combo)
        self._viewer.layers.events.removed.connect(self._update_seg_combo)
        self._update_seg_combo()

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
        self._seg_combo.currentTextChanged.connect(self._on_seg_selected)
        seg_layout.addWidget(self._seg_combo)
        layout.addLayout(seg_layout)

        hist_group = QGroupBox("Column histogram")
        hist_layout = QVBoxLayout()
        col_layout = QHBoxLayout()
        col_layout.addWidget(QLabel("Column:"))
        self._col_combo = QComboBox()
        self._col_combo.currentTextChanged.connect(self._update_histogram)
        col_layout.addWidget(self._col_combo)
        hist_layout.addLayout(col_layout)
        hist_layout.addWidget(self._make_histogram_canvas())
        hist_group.setLayout(hist_layout)
        layout.addWidget(hist_group)

        cat_group = QGroupBox("Categorization")
        cat_layout = QVBoxLayout()

        n_layout = QHBoxLayout()
        n_layout.addWidget(QLabel("Number of categories:"))
        self._n_spin = QSpinBox()
        self._n_spin.setRange(2, 10)
        self._n_spin.setValue(3)
        self._n_spin.valueChanged.connect(self._rebuild_threshold_widgets)
        n_layout.addWidget(self._n_spin)
        cat_layout.addLayout(n_layout)

        self._threshold_container = QWidget()
        self._threshold_layout = QVBoxLayout()
        self._threshold_layout.setContentsMargins(0, 0, 0, 0)
        self._threshold_container.setLayout(self._threshold_layout)
        cat_layout.addWidget(self._threshold_container)

        self._suggest_btn = QPushButton("Suggest thresholds")
        self._suggest_btn.clicked.connect(self._suggest_thresholds)
        cat_layout.addWidget(self._suggest_btn)

        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("Output layer:"))
        self._out_name = QLineEdit("categories")
        out_layout.addWidget(self._out_name)
        cat_layout.addLayout(out_layout)

        self._categorize_btn = QPushButton("Categorize")
        self._categorize_btn.clicked.connect(self._run_categorization)
        cat_layout.addWidget(self._categorize_btn)

        cat_group.setLayout(cat_layout)
        layout.addWidget(cat_group)

        self._rebuild_threshold_widgets()

    def _make_histogram_canvas(self) -> QWidget:
        try:
            from matplotlib.figure import Figure
            try:
                from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            except ImportError:
                from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
            self._hist_fig = Figure()
            self._hist_ax = self._hist_fig.add_subplot(111)
            self._hist_canvas = FigureCanvasQTAgg(self._hist_fig)
            self._hist_canvas.setMinimumHeight(150)
            return self._hist_canvas
        except ImportError:
            return QLabel("Install matplotlib for histogram display.")

    def _rebuild_threshold_widgets(self) -> None:
        while self._threshold_layout.count():
            item = self._threshold_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._threshold_spins = []
        self._name_edits = []

        n = self._n_spin.value()
        for i in range(n - 1):
            row_widget = QWidget()
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(f"Threshold {i + 1}:"))
            spin = QDoubleSpinBox()
            spin.setRange(-1e9, 1e9)
            spin.setDecimals(4)
            spin.valueChanged.connect(self._update_histogram)
            self._threshold_spins.append(spin)
            row.addWidget(spin)
            row_widget.setLayout(row)
            self._threshold_layout.addWidget(row_widget)

        for i in range(n):
            row_widget = QWidget()
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(f"Name {i + 1}:"))
            edit = QLineEdit(f"category_{i + 1}")
            self._name_edits.append(edit)
            row.addWidget(edit)
            row_widget.setLayout(row)
            self._threshold_layout.addWidget(row_widget)

    def _update_seg_combo(self, event: object = None) -> None:
        from napari.layers import Labels
        label_layers = [
            layer.name for layer in self._viewer.layers if isinstance(layer, Labels)
        ]
        current = self._seg_combo.currentText()
        self._seg_combo.clear()
        self._seg_combo.addItems(label_layers)
        if current in label_layers:
            self._seg_combo.setCurrentText(current)

    def _current_features(self) -> pd.DataFrame | None:
        seg_name = self._seg_combo.currentText()
        if not seg_name or seg_name not in [l.name for l in self._viewer.layers]:
            return None
        layer = self._viewer.layers[seg_name]
        feats = getattr(layer, "features", None)
        if feats is None or len(feats.columns) == 0:
            return None
        return feats

    def _on_seg_selected(self, name: str) -> None:
        self._update_col_combo()

    def _update_col_combo(self) -> None:
        feats = self._current_features()
        self._col_combo.blockSignals(True)
        self._col_combo.clear()
        if feats is not None:
            numeric_cols = [
                c for c in feats.select_dtypes(include="number").columns
                if c not in ("index", "category_id")
            ]
            self._col_combo.addItems(numeric_cols)
        self._col_combo.blockSignals(False)
        self._update_histogram()

    def _update_histogram(self) -> None:
        if self._hist_ax is None:
            return
        feats = self._current_features()
        ax = self._hist_ax
        ax.clear()
        if feats is None:
            self._hist_canvas.draw()
            return
        col = self._col_combo.currentText()
        if not col or col not in feats.columns:
            self._hist_canvas.draw()
            return
        values = feats[col].values
        ax.hist(values, bins=20, color="steelblue", alpha=0.7)
        ax.set_xlabel(col)
        ax.set_ylabel("count")
        for spin in self._threshold_spins:
            ax.axvline(spin.value(), color="red", linestyle="--", linewidth=1.5)
        self._hist_fig.tight_layout()
        self._hist_canvas.draw()

    def _suggest_thresholds(self) -> None:
        from segmentation_measurement.analysis import suggest_thresholds
        feats = self._current_features()
        if feats is None:
            return
        col = self._col_combo.currentText()
        if not col:
            return
        n = self._n_spin.value()
        thresholds = suggest_thresholds(feats, col, n)
        for spin, val in zip(self._threshold_spins, thresholds):
            spin.blockSignals(True)
            spin.setValue(val)
            spin.blockSignals(False)
        self._update_histogram()

    def _run_categorization(self) -> None:
        from segmentation_measurement.analysis import categorize_by_threshold
        seg_name = self._seg_combo.currentText()
        if not seg_name:
            return
        seg_layer = self._viewer.layers[seg_name]
        feats = getattr(seg_layer, "features", None)
        if feats is None or len(feats.columns) == 0:
            return
        col = self._col_combo.currentText()
        if not col:
            return
        thresholds = [spin.value() for spin in self._threshold_spins]
        names = [edit.text() for edit in self._name_edits]
        categorized = categorize_by_threshold(feats, col, thresholds, names)
        # Only push back the new columns (avoid round-tripping unchanged ones).
        new_cols = categorized[["index", "category_id", "category_name"]]
        merge_features_into_layer(seg_layer, new_cols)

        segmentation = seg_layer.data
        result = np.zeros_like(segmentation)
        for label_id, cat_id in zip(
            categorized["index"].values,
            categorized["category_id"].values,
        ):
            result[segmentation == int(label_id)] = int(cat_id)
        out_name = self._out_name.text() or "categories"
        existing = [layer.name for layer in self._viewer.layers]
        if out_name in existing:
            self._viewer.layers[out_name].data = result
        else:
            self._viewer.add_labels(result, name=out_name)

        show_features_table(self._viewer, seg_layer)
