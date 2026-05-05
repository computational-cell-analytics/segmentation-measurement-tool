"""Napari widget for interactive classification of segments."""

from __future__ import annotations

import numpy as np
import pandas as pd
import napari
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from segmentation_measurement._layer_features import (
    merge_features_into_layer,
    show_features_table,
)


class ClassificationWidget(QWidget):
    """Widget for interactive classification of segments by measurement features.

    Operates on the ``features`` table of the selected Labels layer.  Users
    paint brushstroke annotations on a dedicated annotation layer.  Clicking
    *Project annotations* maps per-pixel annotations to per-segment labels
    via majority vote and merges them into the source layer's ``features``
    under an ``annotation`` column.  Training uses the annotated rows to fit
    a logistic regression or random forest classifier; *Apply* writes
    ``classification_id`` and ``classification_name`` columns back into the
    source layer's ``features`` and creates a new label layer for
    visualisation.  Trained classifiers can be exported and reloaded.
    """

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
        self._classifier = None
        self._setup_ui()
        self._viewer.layers.events.inserted.connect(self._update_layer_combos)
        self._viewer.layers.events.removed.connect(self._update_layer_combos)
        self._update_layer_combos()

    # ------------------------------------------------------------------ UI ---

    def _setup_ui(self) -> None:
        outer = QVBoxLayout()
        self.setLayout(outer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)
        layout = QVBoxLayout()
        inner.setLayout(layout)

        layout.addWidget(self._build_layers_group())
        layout.addWidget(self._build_class_names_group())
        layout.addWidget(self._build_classifier_group())

    def _build_layers_group(self) -> QGroupBox:
        group = QGroupBox("Layers")
        layout = QVBoxLayout()

        seg_row = QHBoxLayout()
        seg_row.addWidget(QLabel("Segmentation:"))
        self._seg_combo = QComboBox()
        seg_row.addWidget(self._seg_combo)
        layout.addLayout(seg_row)

        ann_row = QHBoxLayout()
        ann_row.addWidget(QLabel("Annotation layer:"))
        self._ann_combo = QComboBox()
        ann_row.addWidget(self._ann_combo)
        create_btn = QPushButton("Create new")
        create_btn.clicked.connect(self._create_annotation_layer)
        ann_row.addWidget(create_btn)
        layout.addLayout(ann_row)

        project_btn = QPushButton("Project annotations to features")
        project_btn.clicked.connect(self._project_annotations)
        layout.addWidget(project_btn)

        group.setLayout(layout)
        return group

    def _build_class_names_group(self) -> QGroupBox:
        group = QGroupBox("Class names")
        layout = QVBoxLayout()

        self._class_names_table = QTableWidget()
        self._class_names_table.setColumnCount(2)
        self._class_names_table.setHorizontalHeaderLabels(["Label ID", "Class Name"])
        self._class_names_table.setMinimumHeight(80)
        layout.addWidget(self._class_names_table)

        group.setLayout(layout)
        return group

    def _build_classifier_group(self) -> QGroupBox:
        group = QGroupBox("Classifier")
        layout = QVBoxLayout()

        method_row = QHBoxLayout()
        method_row.addWidget(QLabel("Method:"))
        self._method_combo = QComboBox()
        self._method_combo.addItems(["Random Forest", "Logistic Regression"])
        self._method_combo.currentIndexChanged.connect(self._on_method_changed)
        method_row.addWidget(self._method_combo)
        layout.addLayout(method_row)

        self._params_stack = QStackedWidget()
        self._params_stack.addWidget(self._make_rf_params())
        self._params_stack.addWidget(self._make_lr_params())
        layout.addWidget(self._params_stack)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output layer:"))
        self._out_name = QLineEdit("classification")
        out_row.addWidget(self._out_name)
        layout.addLayout(out_row)

        train_btn = QPushButton("Train & Apply")
        train_btn.clicked.connect(self._train_and_apply)
        layout.addWidget(train_btn)

        file_row = QHBoxLayout()
        load_btn = QPushButton("Load classifier")
        load_btn.clicked.connect(self._load_classifier)
        file_row.addWidget(load_btn)
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply_classifier_only)
        file_row.addWidget(apply_btn)
        export_btn = QPushButton("Export classifier")
        export_btn.clicked.connect(self._export_classifier)
        file_row.addWidget(export_btn)
        layout.addLayout(file_row)

        group.setLayout(layout)
        return group

    # -------------------------------------------------- Parameter widgets ---

    def _make_lr_params(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        c_row = QHBoxLayout()
        c_row.addWidget(QLabel("C (regularization):"))
        self._lr_c_spin = QDoubleSpinBox()
        self._lr_c_spin.setRange(0.001, 1000.0)
        self._lr_c_spin.setValue(1.0)
        self._lr_c_spin.setDecimals(3)
        c_row.addWidget(self._lr_c_spin)
        layout.addLayout(c_row)

        iter_row = QHBoxLayout()
        iter_row.addWidget(QLabel("Max iterations:"))
        self._lr_iter_spin = QSpinBox()
        self._lr_iter_spin.setRange(100, 10000)
        self._lr_iter_spin.setValue(1000)
        iter_row.addWidget(self._lr_iter_spin)
        layout.addLayout(iter_row)

        w.setLayout(layout)
        return w

    def _make_rf_params(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        n_row = QHBoxLayout()
        n_row.addWidget(QLabel("N estimators:"))
        self._rf_n_spin = QSpinBox()
        self._rf_n_spin.setRange(1, 1000)
        self._rf_n_spin.setValue(100)
        n_row.addWidget(self._rf_n_spin)
        layout.addLayout(n_row)

        depth_row = QHBoxLayout()
        depth_row.addWidget(QLabel("Max depth (0=unlimited):"))
        self._rf_depth_spin = QSpinBox()
        self._rf_depth_spin.setRange(0, 100)
        self._rf_depth_spin.setValue(0)
        depth_row.addWidget(self._rf_depth_spin)
        layout.addLayout(depth_row)

        w.setLayout(layout)
        return w

    # -------------------------------------------------------- Event handlers ---

    def _on_method_changed(self, index: int) -> None:
        self._params_stack.setCurrentIndex(index)

    def _update_layer_combos(self, event: object = None) -> None:
        from napari.layers import Labels
        label_names = [
            layer.name for layer in self._viewer.layers if isinstance(layer, Labels)
        ]
        for combo in (self._seg_combo, self._ann_combo):
            current = combo.currentText()
            combo.clear()
            combo.addItems(label_names)
            if current in label_names:
                combo.setCurrentText(current)

    def _seg_layer(self) -> object | None:
        seg_name = self._seg_combo.currentText()
        if not seg_name or seg_name not in [l.name for l in self._viewer.layers]:
            return None
        return self._viewer.layers[seg_name]

    def _current_features(self) -> pd.DataFrame | None:
        seg = self._seg_layer()
        if seg is None:
            return None
        feats = getattr(seg, "features", None)
        if feats is None or len(feats.columns) == 0:
            return None
        return feats

    # ---------------------------------------------------------- Annotation ---

    def _create_annotation_layer(self) -> None:
        seg = self._seg_layer()
        if seg is None:
            return
        ann_data = np.zeros_like(seg.data, dtype=np.int32)
        layer = self._viewer.add_labels(ann_data, name="annotations")
        self._ann_combo.setCurrentText(layer.name)

    def _project_annotations(self) -> None:
        seg = self._seg_layer()
        if seg is None:
            return
        feats = self._current_features()
        if feats is None:
            return
        ann_name = self._ann_combo.currentText()
        if not ann_name or ann_name == seg.name:
            return
        ann_data = self._viewer.layers[ann_name].data
        if seg.data.shape != ann_data.shape:
            return

        projection = _project_annotations_to_segments(seg.data, ann_data)
        annotations = [
            projection.get(int(lbl), 0)
            for lbl in feats["index"].values
        ]
        ann_df = pd.DataFrame({
            "index": feats["index"].values,
            "annotation": annotations,
        })
        merge_features_into_layer(seg, ann_df)

        detected_ids = sorted(set(a for a in annotations if a > 0))
        self._update_class_names_table(detected_ids)
        show_features_table(self._viewer, seg)

    def _update_class_names_table(self, annotation_ids: list[int]) -> None:
        existing = self._get_class_names()
        self._class_names_table.setRowCount(len(annotation_ids))
        for row, ann_id in enumerate(annotation_ids):
            id_item = QTableWidgetItem(str(ann_id))
            id_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._class_names_table.setItem(row, 0, id_item)
            name = existing.get(ann_id, f"class_{ann_id}")
            self._class_names_table.setItem(row, 1, QTableWidgetItem(name))

    def _get_class_names(self) -> dict[int, str]:
        names: dict[int, str] = {}
        for row in range(self._class_names_table.rowCount()):
            id_item = self._class_names_table.item(row, 0)
            name_item = self._class_names_table.item(row, 1)
            if id_item and name_item:
                try:
                    names[int(id_item.text())] = name_item.text()
                except (ValueError, AttributeError):
                    pass
        return names

    # ---------------------------------------------------------- Classifier ---

    def _get_method_and_kwargs(self) -> tuple[str, dict]:
        method = self._method_combo.currentText()
        if method == "Random Forest":
            kwargs: dict = {"n_estimators": self._rf_n_spin.value()}
            depth = self._rf_depth_spin.value()
            if depth > 0:
                kwargs["max_depth"] = depth
            return "random_forest", kwargs
        return "logistic_regression", {
            "C": self._lr_c_spin.value(),
            "max_iter": self._lr_iter_spin.value(),
        }

    def _train_and_apply(self) -> None:
        from segmentation_measurement.analysis import train_classifier
        feats = self._current_features()
        if feats is None or "annotation" not in feats.columns:
            return
        method, kwargs = self._get_method_and_kwargs()
        try:
            self._classifier = train_classifier(feats, method=method, **kwargs)
        except ValueError:
            return
        self._apply_classifier_only()

    def _apply_classifier_only(self) -> None:
        from segmentation_measurement.analysis import apply_classifier
        seg = self._seg_layer()
        feats = self._current_features()
        if seg is None or feats is None or self._classifier is None:
            return
        class_names_dict = self._get_class_names()
        classes = sorted(int(c) for c in self._classifier.classes_)
        class_names_list = [class_names_dict.get(c, f"class_{c}") for c in classes]
        result = apply_classifier(
            feats, self._classifier, class_names=class_names_list
        )
        merge_features_into_layer(
            seg,
            result[["index", "classification_id", "classification_name"]],
        )
        self._create_output_layer(result)
        show_features_table(self._viewer, seg)

    def _create_output_layer(self, result: pd.DataFrame) -> None:
        seg = self._seg_layer()
        if seg is None:
            return
        seg_data = seg.data
        out = np.zeros_like(seg_data, dtype=np.int32)
        for lbl, cid in zip(
            result["index"].values,
            result["classification_id"].values,
        ):
            if int(cid) > 0:
                out[seg_data == int(lbl)] = int(cid)

        out_name = self._out_name.text() or "classification"
        existing = [layer.name for layer in self._viewer.layers]
        if out_name in existing:
            layer = self._viewer.layers[out_name]
            layer.data = out
        else:
            layer = self._viewer.add_labels(out, name=out_name)

        unique_cids = sorted(
            int(c) for c in result["classification_id"].unique() if int(c) > 0
        )
        _apply_class_colors(layer, unique_cids)

    def _export_classifier(self) -> None:
        if self._classifier is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export classifier", "",
            "Joblib (*.joblib);;All Files (*)",
        )
        if path:
            import joblib
            joblib.dump(self._classifier, path)

    def _load_classifier(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load classifier", "",
            "Joblib (*.joblib);;All Files (*)",
        )
        if path:
            import joblib
            self._classifier = joblib.load(path)


# ------------------------------------------------------------------ helpers ---

def _project_annotations_to_segments(
    segmentation: np.ndarray,
    annotation_data: np.ndarray,
) -> dict[int, int]:
    """Majority-vote project per-pixel annotations onto segment labels.

    Args:
        segmentation (np.ndarray): Integer label array; 0 is background.
        annotation_data (np.ndarray): Integer annotation array with the same
            shape. 0 means unannotated.

    Returns:
        dict[int, int]: Mapping of each segment label to its majority
            annotation label (0 when no annotation overlaps that segment).
    """
    seg_flat = segmentation.ravel()
    ann_flat = annotation_data.ravel()

    unique_segs = np.unique(seg_flat)
    unique_segs = unique_segs[unique_segs > 0]
    result: dict[int, int] = {int(lbl): 0 for lbl in unique_segs}

    annotated_mask = ann_flat > 0
    if not annotated_mask.any():
        return result

    seg_ann = seg_flat[annotated_mask]
    ann_ann = ann_flat[annotated_mask]
    for seg_id in unique_segs:
        ann_for_seg = ann_ann[seg_ann == seg_id]
        if len(ann_for_seg) > 0:
            values, counts = np.unique(ann_for_seg, return_counts=True)
            result[int(seg_id)] = int(values[np.argmax(counts)])

    return result


def _apply_class_colors(layer: object, class_ids: list[int]) -> None:
    """Apply distinct colours to a classification label layer.

    Uses ``DirectLabelColormap`` (napari >= 0.5).  Silently skips if the API
    is unavailable or no class IDs are provided.
    """
    if not class_ids:
        return
    try:
        from napari.utils.colormaps import DirectLabelColormap
        try:
            import matplotlib
            n = len(class_ids)
            cmap = matplotlib.colormaps["tab10" if n <= 10 else "tab20"]
        except AttributeError:
            import matplotlib.pyplot as plt
            n = len(class_ids)
            cmap = plt.cm.get_cmap("tab10" if n <= 10 else "tab20")
        color_dict: dict = {None: np.zeros(4)}
        for i, cid in enumerate(sorted(class_ids)):
            color_dict[cid] = np.array(cmap(i % cmap.N), dtype=float)
        layer.colormap = DirectLabelColormap(color_dict=color_dict)
    except Exception:
        pass
