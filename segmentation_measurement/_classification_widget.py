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

from segmentation_measurement._groups import (
    ROLE_SEGMENTATION,
    get_group,
    list_groups,
    subscribe,
)
from segmentation_measurement._layer_features import (
    concat_features_for_group,
    merge_features_into_layer,
    show_features_table,
    split_and_merge_back,
)

_TARGET_SINGLE = "<single layer>"
_NONE_ANN = "(none)"


class ClassificationWidget(QWidget):
    """Widget for interactive classification of segments by measurement features.

    Operates on the ``features`` table of the selected Labels layer.
    Users paint brushstroke annotations on a dedicated annotation layer.
    Clicking *Project annotations* maps per-pixel annotations to
    per-segment labels via majority vote and merges them into the source
    layer's ``features`` under an ``annotation`` column.  Training uses
    the annotated rows to fit a logistic regression or random forest
    classifier; *Apply* writes ``classification_id`` and
    ``classification_name`` columns back into the source layer's
    ``features`` and creates a new label layer for visualisation.
    Trained classifiers can be exported and reloaded.

    The *Target* combo selects what to classify:

    * ``<single layer>`` (default): operate on the layer chosen in the
      *Segmentation* combo.  Original behaviour.
    * a group name: the *Segmentation* combo is restricted to the
      group's segmentation members so the user can step through them
      (annotating each one in turn and projecting before training).
      *Train & Apply* concatenates all members' features for training
      and then applies the classifier to each member individually,
      creating one output label layer per member named
      ``{output}_{layer_name}`` (or just ``{output}`` if the group has
      a single member).
    """

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
        self._classifier = None
        # Per-member annotation cache (group mode only). Keys are
        # segmentation layer names; values are sparse-compressed
        # annotation arrays produced by ``_compress_annotation``.
        self._member_annotations: dict[str, dict] = {}
        self._current_member: str | None = None
        self._setup_ui()
        self._seg_combo.currentTextChanged.connect(self._on_seg_combo_changed)
        self._viewer.layers.events.inserted.connect(self._update_layer_combos)
        self._viewer.layers.events.removed.connect(self._update_layer_combos)
        self._unsubscribe = subscribe(self._viewer, self._update_target_combo)
        self.destroyed.connect(lambda *_: self._unsubscribe())
        self._update_target_combo()
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

        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Target:"))
        self._target_combo = QComboBox()
        self._target_combo.currentTextChanged.connect(self._on_target_changed)
        target_layout.addWidget(self._target_combo)
        layout.addLayout(target_layout)

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
        self._update_layer_combos()

    def _on_target_changed(self, target: str) -> None:
        # Save the previously-active group member's annotations before the
        # selection changes underneath us.
        if self._current_member is not None:
            self._save_member_annotations(self._current_member)
        self._update_layer_combos()
        if target == _TARGET_SINGLE:
            self._current_member = None
            return
        # Group mode: load the first member's cached annotations into the
        # currently-selected annotation layer (zeroing it if no cache exists).
        new_member = self._seg_combo.currentText() or None
        if new_member is not None:
            self._load_member_annotations(new_member)
        self._current_member = new_member

    def _on_seg_combo_changed(self, name: str) -> None:
        # Member-switch persistence applies only in group mode.
        if self._target_combo.currentText() == _TARGET_SINGLE:
            self._current_member = None
            return
        if not name or name == self._current_member:
            return
        if self._current_member is not None:
            self._save_member_annotations(self._current_member)
        self._load_member_annotations(name)
        self._current_member = name

    def _save_member_annotations(self, member_name: str) -> None:
        """Snapshot the current annotation layer's data for ``member_name``."""
        ann = self._ann_layer()
        if ann is None:
            return
        self._member_annotations[member_name] = _compress_annotation(ann.data)

    def _load_member_annotations(self, member_name: str) -> None:
        """Restore (or zero) the annotation layer for ``member_name``."""
        ann = self._ann_layer()
        if ann is None or member_name not in self._viewer.layers:
            return
        seg = self._viewer.layers[member_name]
        cached = self._member_annotations.get(member_name)
        if cached is not None and cached["shape"] == tuple(seg.data.shape):
            ann.data = _decompress_annotation(cached)
        else:
            ann.data = np.zeros(seg.data.shape, dtype=np.int32)

    def _ann_layer(self) -> object | None:
        ann_name = self._ann_combo.currentText()
        if (
            not ann_name
            or ann_name == _NONE_ANN
            or ann_name not in [l.name for l in self._viewer.layers]
        ):
            return None
        return self._viewer.layers[ann_name]

    def _update_layer_combos(self, event: object = None) -> None:
        from napari.layers import Labels
        all_label_names = [
            layer.name for layer in self._viewer.layers if isinstance(layer, Labels)
        ]
        target = self._target_combo.currentText()
        if target == _TARGET_SINGLE:
            seg_items = all_label_names
        else:
            try:
                members = get_group(self._viewer, target)
            except KeyError:
                seg_items = all_label_names
            else:
                seg_items = list(members.get(ROLE_SEGMENTATION, []))
        current_seg = self._seg_combo.currentText()
        self._seg_combo.blockSignals(True)
        self._seg_combo.clear()
        self._seg_combo.addItems(seg_items)
        if current_seg in seg_items:
            self._seg_combo.setCurrentText(current_seg)
        elif seg_items:
            self._seg_combo.setCurrentText(seg_items[0])
        self._seg_combo.blockSignals(False)

        current_ann = self._ann_combo.currentText()
        self._ann_combo.blockSignals(True)
        self._ann_combo.clear()
        # Sentinel keeps annotation selection explicit: per-member
        # persistence must not auto-clear an arbitrary label layer that
        # happened to be first in the viewer (typically a segmentation).
        self._ann_combo.addItem(_NONE_ANN)
        self._ann_combo.addItems(all_label_names)
        if current_ann == _NONE_ANN or current_ann in all_label_names:
            self._ann_combo.setCurrentText(current_ann)
        self._ann_combo.blockSignals(False)

    def _seg_layer(self) -> object | None:
        seg_name = self._seg_combo.currentText()
        if not seg_name or seg_name not in [l.name for l in self._viewer.layers]:
            return None
        return self._viewer.layers[seg_name]

    def _current_features(self) -> pd.DataFrame | None:
        """Features of the currently-selected segmentation layer (member)."""
        seg = self._seg_layer()
        if seg is None:
            return None
        feats = getattr(seg, "features", None)
        if feats is None or len(feats.columns) == 0:
            return None
        return feats

    def _features_for_classifier(self) -> pd.DataFrame | None:
        """Features used for training/applying the classifier.

        In single-layer mode this returns the current segmentation
        layer's features.  In group mode it returns the concatenation
        across the group's segmentation members (with ``_source_layer``
        column).
        """
        target = self._target_combo.currentText()
        if target == _TARGET_SINGLE:
            return self._current_features()
        try:
            return concat_features_for_group(
                self._viewer, target, ROLE_SEGMENTATION
            )
        except (ValueError, KeyError):
            return None

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
        if not ann_name or ann_name == _NONE_ANN or ann_name == seg.name:
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

        self._update_class_names_table(self._collect_annotation_ids())
        show_features_table(self._viewer, seg)

    def _collect_annotation_ids(self) -> list[int]:
        """Return all unique non-zero annotation IDs across the target.

        In single-layer mode this is the IDs in the current layer's
        ``annotation`` column.  In group mode it pools IDs across every
        member that has been annotated already.  NaN rows (the
        background-padding entries added by ``merge_features_into_layer``)
        are skipped.
        """
        ids: set[int] = set()
        frames: list[pd.DataFrame] = []
        target = self._target_combo.currentText()
        if target == _TARGET_SINGLE:
            feats = self._current_features()
            if feats is not None:
                frames.append(feats)
        else:
            try:
                members = get_group(self._viewer, target)
            except KeyError:
                return []
            for layer_name in members.get(ROLE_SEGMENTATION, []):
                if layer_name not in self._viewer.layers:
                    continue
                feats = getattr(self._viewer.layers[layer_name], "features", None)
                if feats is not None:
                    frames.append(feats)
        for feats in frames:
            if "annotation" not in feats.columns:
                continue
            values = feats["annotation"].dropna()
            ids.update(int(a) for a in values if int(a) > 0)
        return sorted(ids)

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
        feats = self._features_for_classifier()
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
        if self._classifier is None:
            return
        target = self._target_combo.currentText()
        feats = self._features_for_classifier()
        if feats is None:
            return
        class_names_dict = self._get_class_names()
        classes = sorted(int(c) for c in self._classifier.classes_)
        class_names_list = [class_names_dict.get(c, f"class_{c}") for c in classes]
        result = apply_classifier(
            feats, self._classifier, class_names=class_names_list
        )

        # Maximum class across the whole result drives the colormap choice
        # so per-member output layers share the same color → class mapping
        # even if a particular member only contains a subset of classes.
        max_class = int(result["classification_id"].max()) if len(result) else 0

        out_name = self._out_name.text() or "classification"

        if target == _TARGET_SINGLE:
            seg = self._seg_layer()
            if seg is None:
                return
            merge_features_into_layer(
                seg,
                result[["index", "classification_id", "classification_name"]],
            )
            self._create_output_layer(seg, result, out_name, max_class)
            show_features_table(self._viewer, seg)
            return

        # Group target.
        try:
            members = get_group(self._viewer, target)
        except KeyError:
            return
        seg_layers = members.get(ROLE_SEGMENTATION, [])
        if not seg_layers:
            return
        split_and_merge_back(
            self._viewer, result,
            ["classification_id", "classification_name"],
        )

        suffix_per_member = len(seg_layers) > 1
        first_layer = None
        for seg_name in seg_layers:
            if seg_name not in self._viewer.layers:
                continue
            seg_layer = self._viewer.layers[seg_name]
            sub = result[result["_source_layer"] == seg_name]
            layer_out_name = (
                f"{out_name}_{seg_name}" if suffix_per_member else out_name
            )
            self._create_output_layer(seg_layer, sub, layer_out_name, max_class)
            if first_layer is None:
                first_layer = seg_layer
        if first_layer is not None:
            show_features_table(self._viewer, first_layer)

    def _create_output_layer(
        self,
        seg_layer: object,
        result: pd.DataFrame,
        out_name: str,
        max_class: int | None = None,
    ) -> None:
        seg_data = seg_layer.data
        out = np.zeros_like(seg_data, dtype=np.int32)
        for lbl, cid in zip(
            result["index"].values,
            result["classification_id"].values,
        ):
            if int(cid) > 0:
                out[seg_data == int(lbl)] = int(cid)

        existing = [layer.name for layer in self._viewer.layers]
        if out_name in existing:
            layer = self._viewer.layers[out_name]
            layer.data = out
        else:
            layer = self._viewer.add_labels(out, name=out_name)

        unique_cids = sorted(
            int(c) for c in result["classification_id"].unique() if int(c) > 0
        )
        _apply_class_colors(layer, unique_cids, max_class)

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


def _compress_annotation(arr: np.ndarray) -> dict:
    """Compress a sparse integer annotation array to a coordinate-list form.

    Annotation arrays are typically very sparse (background = 0 with a
    few brushstrokes), so storing the shape, the non-zero indices, and
    the corresponding values is much more compact than the dense array.

    Args:
        arr: Integer annotation array.  Will be coerced via
            :func:`numpy.asarray`.

    Returns:
        dict: Keys ``shape`` (tuple), ``dtype`` (numpy dtype), ``indices``
            (tuple of ndim 1-D int64 arrays as returned by
            :func:`numpy.nonzero`), ``values`` (1-D array of non-zero
            entries).  Pass to :func:`_decompress_annotation` to round-trip.
    """
    arr = np.asarray(arr)
    indices = np.nonzero(arr)
    return {
        "shape": tuple(arr.shape),
        "dtype": arr.dtype,
        "indices": tuple(np.asarray(c, dtype=np.int64) for c in indices),
        "values": np.asarray(arr[indices], dtype=arr.dtype),
    }


def _decompress_annotation(compressed: dict) -> np.ndarray:
    """Reconstruct the dense annotation array from a compressed dict."""
    arr = np.zeros(compressed["shape"], dtype=compressed["dtype"])
    if len(compressed["values"]) > 0:
        arr[compressed["indices"]] = compressed["values"]
    return arr


def _class_color_dict(
    class_ids: list[int], max_class: int | None = None
) -> dict[int, tuple]:
    """Return a deterministic ``{class_id: rgba}`` mapping.

    Colours are keyed off the class ID itself (1-based), so the same
    class always gets the same colour regardless of which other classes
    happen to be present in any particular layer.  ``max_class`` (the
    largest class ID across the *whole* classification) drives the
    colormap choice so consumers can keep the assignment consistent
    across multiple per-member output layers.

    Args:
        class_ids: 1-based class IDs to colour.  Empty input yields an
            empty mapping.
        max_class: Largest class ID across the full classification.
            Defaults to ``max(class_ids)`` when omitted.

    Returns:
        dict[int, tuple]: ``{class_id: rgba}`` with RGBA tuples from
            either the ``tab10`` or ``tab20`` matplotlib colormap.
    """
    if not class_ids:
        return {}
    n = max_class if max_class is not None else max(class_ids)
    try:
        import matplotlib
        cmap = matplotlib.colormaps["tab10" if n <= 10 else "tab20"]
    except AttributeError:
        import matplotlib.pyplot as plt
        cmap = plt.cm.get_cmap("tab10" if n <= 10 else "tab20")
    return {cid: tuple(cmap((cid - 1) % cmap.N)) for cid in class_ids}


def _apply_class_colors(
    layer: object,
    class_ids: list[int],
    max_class: int | None = None,
) -> None:
    """Apply deterministic per-ID colours to a classification label layer.

    Uses ``DirectLabelColormap`` (napari >= 0.5).  Silently skips if the
    API is unavailable or no class IDs are provided.
    """
    if not class_ids:
        return
    try:
        from napari.utils.colormaps import DirectLabelColormap
        colors = _class_color_dict(class_ids, max_class)
        color_dict: dict = {None: np.zeros(4)}
        for cid, rgba in colors.items():
            color_dict[cid] = np.array(rgba, dtype=float)
        layer.colormap = DirectLabelColormap(color_dict=color_dict)
    except Exception:
        pass
