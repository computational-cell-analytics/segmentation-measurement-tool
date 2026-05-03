"""Napari widget for clustering analysis of measurement results."""

from __future__ import annotations

import numpy as np
import pandas as pd
import napari
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
    QVBoxLayout,
    QWidget,
)

from segmentation_measurement._utils import (
    get_registered_tables,
    populate_table_widget,
    save_table,
)


class ClusteringWidget(QWidget):
    """Widget for clustering segments by their measurement features.

    Operates on tables registered by measurement widgets.  Use the Refresh
    button to pick up newly produced tables, select a clustering method, then
    click *Cluster* to run clustering, colour the feature scatter plot, and
    create an output label layer.
    """

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
        self._measurements: pd.DataFrame | None = None
        self._embedding: np.ndarray | None = None
        self._cluster_ids: np.ndarray | None = None
        self._cluster_colors: dict[int, tuple] = {}
        self._fig = None
        self._ax = None
        self._canvas = None
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

        # --- Table selection ---
        table_group = QGroupBox("Measurement table")
        table_layout = QVBoxLayout()

        sel_layout = QHBoxLayout()
        sel_layout.addWidget(QLabel("Table:"))
        self._table_combo = QComboBox()
        self._table_combo.currentTextChanged.connect(self._on_table_selected)
        sel_layout.addWidget(self._table_combo)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_table_combo)
        sel_layout.addWidget(refresh_btn)
        table_layout.addLayout(sel_layout)

        self._table = QTableWidget()
        self._table.setMinimumHeight(120)
        table_layout.addWidget(self._table)

        save_btn = QPushButton("Save table")
        save_btn.clicked.connect(self._save_table)
        table_layout.addWidget(save_btn)

        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # --- Segmentation selection ---
        seg_layout = QHBoxLayout()
        seg_layout.addWidget(QLabel("Segmentation:"))
        self._seg_combo = QComboBox()
        seg_layout.addWidget(self._seg_combo)
        layout.addLayout(seg_layout)

        # --- Feature reduction plot ---
        reduction_group = QGroupBox("Feature reduction")
        reduction_layout = QVBoxLayout()

        red_method_layout = QHBoxLayout()
        red_method_layout.addWidget(QLabel("Method:"))
        self._reduction_combo = QComboBox()
        self._reduction_combo.addItems(["UMAP", "TSNE", "PCA"])
        self._reduction_combo.currentTextChanged.connect(self._on_reduction_method_changed)
        red_method_layout.addWidget(self._reduction_combo)
        reduce_btn = QPushButton("Reduce")
        reduce_btn.clicked.connect(self._run_reduction)
        red_method_layout.addWidget(reduce_btn)
        reduction_layout.addLayout(red_method_layout)

        reduction_layout.addWidget(self._make_scatter_canvas())
        reduction_group.setLayout(reduction_layout)
        layout.addWidget(reduction_group)

        # --- Clustering parameters ---
        cluster_group = QGroupBox("Clustering")
        cluster_layout = QVBoxLayout()

        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Method:"))
        self._method_combo = QComboBox()
        self._method_combo.addItems(["K-Means", "DBSCAN", "HDBSCAN", "Mean Shift"])
        self._method_combo.currentIndexChanged.connect(self._on_method_changed)
        method_layout.addWidget(self._method_combo)
        cluster_layout.addLayout(method_layout)

        self._params_stack = QStackedWidget()
        self._params_stack.addWidget(self._make_kmeans_params())
        self._params_stack.addWidget(self._make_dbscan_params())
        self._params_stack.addWidget(self._make_hdbscan_params())
        self._params_stack.addWidget(self._make_mean_shift_params())
        cluster_layout.addWidget(self._params_stack)

        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("Output layer:"))
        self._out_name = QLineEdit("clusters")
        out_layout.addWidget(self._out_name)
        cluster_layout.addLayout(out_layout)

        self._cluster_btn = QPushButton("Cluster")
        self._cluster_btn.clicked.connect(self._run_clustering)
        cluster_layout.addWidget(self._cluster_btn)

        cluster_group.setLayout(cluster_layout)
        layout.addWidget(cluster_group)

    # --- Parameter sub-widgets ---

    def _make_kmeans_params(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel("N clusters:"))
        self._kmeans_n_spin = QSpinBox()
        self._kmeans_n_spin.setRange(2, 100)
        self._kmeans_n_spin.setValue(3)
        row.addWidget(self._kmeans_n_spin)
        layout.addLayout(row)
        w.setLayout(layout)
        return w

    def _make_dbscan_params(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        eps_row = QHBoxLayout()
        eps_row.addWidget(QLabel("Eps:"))
        self._dbscan_eps_spin = QDoubleSpinBox()
        self._dbscan_eps_spin.setRange(0.001, 1000.0)
        self._dbscan_eps_spin.setValue(0.5)
        self._dbscan_eps_spin.setDecimals(3)
        eps_row.addWidget(self._dbscan_eps_spin)
        layout.addLayout(eps_row)
        ms_row = QHBoxLayout()
        ms_row.addWidget(QLabel("Min samples:"))
        self._dbscan_min_samples_spin = QSpinBox()
        self._dbscan_min_samples_spin.setRange(1, 1000)
        self._dbscan_min_samples_spin.setValue(5)
        ms_row.addWidget(self._dbscan_min_samples_spin)
        layout.addLayout(ms_row)
        w.setLayout(layout)
        return w

    def _make_hdbscan_params(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        mcs_row = QHBoxLayout()
        mcs_row.addWidget(QLabel("Min cluster size:"))
        self._hdbscan_mcs_spin = QSpinBox()
        self._hdbscan_mcs_spin.setRange(2, 1000)
        self._hdbscan_mcs_spin.setValue(5)
        mcs_row.addWidget(self._hdbscan_mcs_spin)
        layout.addLayout(mcs_row)
        w.setLayout(layout)
        return w

    def _make_mean_shift_params(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        bw_row = QHBoxLayout()
        bw_row.addWidget(QLabel("Bandwidth (0=auto):"))
        self._ms_bandwidth_spin = QDoubleSpinBox()
        self._ms_bandwidth_spin.setRange(0.0, 1000.0)
        self._ms_bandwidth_spin.setValue(0.0)
        self._ms_bandwidth_spin.setDecimals(3)
        bw_row.addWidget(self._ms_bandwidth_spin)
        layout.addLayout(bw_row)
        w.setLayout(layout)
        return w

    # --- Canvas ---

    def _make_scatter_canvas(self) -> QWidget:
        try:
            from matplotlib.figure import Figure
            try:
                from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            except ImportError:
                from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
            self._fig = Figure()
            self._ax = self._fig.add_subplot(111)
            self._canvas = FigureCanvasQTAgg(self._fig)
            self._canvas.setMinimumHeight(200)
            return self._canvas
        except ImportError:
            return QLabel("Install matplotlib for scatter plot display.")

    # --- Event handlers ---

    def _on_method_changed(self, index: int) -> None:
        self._params_stack.setCurrentIndex(index)

    def _on_reduction_method_changed(self) -> None:
        self._embedding = None

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

    def _refresh_table_combo(self) -> None:
        tables = get_registered_tables()
        current = self._table_combo.currentText()
        self._table_combo.blockSignals(True)
        self._table_combo.clear()
        self._table_combo.addItems(list(tables.keys()))
        if current in tables:
            self._table_combo.setCurrentText(current)
        self._table_combo.blockSignals(False)
        self._on_table_selected(self._table_combo.currentText())

    def _on_table_selected(self, name: str) -> None:
        if not name:
            return
        tables = get_registered_tables()
        if name not in tables:
            return
        self._measurements = tables[name].copy()
        self._embedding = None
        self._cluster_ids = None
        self._cluster_colors = {}
        populate_table_widget(self._table, self._measurements)
        self._update_scatter()

    # --- Embedding ---

    def _get_feature_matrix(self) -> np.ndarray | None:
        if self._measurements is None:
            return None
        from segmentation_measurement.analysis import _CLUSTER_EXCLUDE
        feature_cols = [
            c for c in self._measurements.select_dtypes(include="number").columns
            if c not in _CLUSTER_EXCLUDE
        ]
        if not feature_cols:
            return None
        return self._measurements[feature_cols].values.astype(float)

    def _compute_embedding(self) -> np.ndarray | None:
        X = self._get_feature_matrix()
        if X is None:
            return None
        valid_mask = ~np.isnan(X).any(axis=1)
        n_valid = int(valid_mask.sum())
        n_feat = X.shape[1]
        # Need at least 2 samples and 2 features for a 2-D embedding
        if n_valid < 2 or n_feat < 2:
            return None

        from sklearn.preprocessing import StandardScaler
        X_valid = StandardScaler().fit_transform(X[valid_mask])

        method = self._reduction_combo.currentText()
        embedding = np.full((len(X), 2), np.nan)

        if method == "UMAP":
            try:
                import umap as umap_lib
                reducer = umap_lib.UMAP(n_components=2, random_state=42)
                embedding[valid_mask] = reducer.fit_transform(X_valid)
            except ImportError:
                # fall back to PCA when umap-learn is not installed
                from sklearn.decomposition import PCA
                embedding[valid_mask] = PCA(n_components=2).fit_transform(X_valid)
        elif method == "TSNE":
            from sklearn.manifold import TSNE
            perplexity = min(30.0, max(5.0, n_valid / 5.0))
            reducer = TSNE(n_components=2, random_state=42, perplexity=perplexity)
            embedding[valid_mask] = reducer.fit_transform(X_valid)
        else:
            from sklearn.decomposition import PCA
            embedding[valid_mask] = PCA(n_components=2).fit_transform(X_valid)

        return embedding

    def _run_reduction(self) -> None:
        self._embedding = None
        self._embedding = self._compute_embedding()
        self._update_scatter(self._cluster_ids)

    # --- Scatter plot ---

    def _update_scatter(self, cluster_ids: np.ndarray | None = None) -> None:
        if self._ax is None:
            return
        self._ax.clear()

        if self._measurements is None or self._embedding is None:
            self._canvas.draw()
            return

        valid_mask = ~np.isnan(self._embedding).any(axis=1)
        emb = self._embedding[valid_mask]

        if cluster_ids is None or len(cluster_ids) != len(self._measurements):
            self._ax.scatter(emb[:, 0], emb[:, 1], c="steelblue", s=10, alpha=0.7)
        else:
            c_ids = cluster_ids[valid_mask]
            unique_ids = sorted(set(int(x) for x in c_ids))
            colors = _get_cluster_colors(len(unique_ids))
            self._cluster_colors = {cid: colors[i] for i, cid in enumerate(unique_ids)}
            for cid in unique_ids:
                mask = c_ids == cid
                label = "noise" if cid == -1 else f"cluster {cid}"
                self._ax.scatter(
                    emb[mask, 0], emb[mask, 1],
                    c=[self._cluster_colors[cid]], s=10, alpha=0.7, label=label,
                )
            self._ax.legend(loc="best", fontsize=6, markerscale=2)

        self._ax.set_xlabel("dim 1")
        self._ax.set_ylabel("dim 2")
        self._fig.tight_layout()
        self._canvas.draw()

    # --- Clustering ---

    def _get_method_kwargs(self) -> dict:
        method = self._method_combo.currentText()
        if method == "K-Means":
            return {"n_clusters": self._kmeans_n_spin.value()}
        if method == "DBSCAN":
            return {
                "eps": self._dbscan_eps_spin.value(),
                "min_samples": self._dbscan_min_samples_spin.value(),
            }
        if method == "HDBSCAN":
            return {"min_cluster_size": self._hdbscan_mcs_spin.value()}
        if method == "Mean Shift":
            bw = self._ms_bandwidth_spin.value()
            return {"bandwidth": bw} if bw > 0 else {}
        return {}

    def _run_clustering(self) -> None:
        from segmentation_measurement.analysis import cluster_measurements
        if self._measurements is None:
            return

        method_map = {
            "K-Means": "kmeans",
            "DBSCAN": "dbscan",
            "HDBSCAN": "hdbscan",
            "Mean Shift": "mean_shift",
        }
        method = method_map[self._method_combo.currentText()]
        self._measurements = cluster_measurements(
            self._measurements, method=method, **self._get_method_kwargs()
        )
        populate_table_widget(self._table, self._measurements)
        self._cluster_ids = self._measurements["cluster_id"].values.copy()

        if self._embedding is None:
            self._embedding = self._compute_embedding()
        self._update_scatter(self._cluster_ids)

        seg_name = self._seg_combo.currentText()
        if not seg_name:
            return
        segmentation = self._viewer.layers[seg_name].data
        result = np.zeros_like(segmentation)
        for label_id, cluster_id in zip(
            self._measurements["label"].values,
            self._measurements["cluster_id"].values,
        ):
            # cluster_id is 1-based; noise (-1) stays as background (0)
            if int(cluster_id) > 0:
                result[segmentation == int(label_id)] = int(cluster_id)

        out_name = self._out_name.text() or "clusters"
        existing = [layer.name for layer in self._viewer.layers]
        if out_name in existing:
            layer = self._viewer.layers[out_name]
            layer.data = result
        else:
            layer = self._viewer.add_labels(result, name=out_name)

        # Apply cluster colours to label layer so they match the scatter plot
        _apply_cluster_colors(layer, self._cluster_colors)

    def _save_table(self) -> None:
        if self._measurements is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save table", "",
            "CSV (*.csv);;TSV (*.tsv);;Excel (*.xlsx);;All Files (*)",
        )
        if path:
            save_table(self._measurements, path)


def _get_cluster_colors(n: int) -> list[tuple]:
    """Return a list of n distinct RGBA colours from a categorical colormap."""
    try:
        import matplotlib
        cmap = matplotlib.colormaps["tab10" if n <= 10 else "tab20"]
    except AttributeError:
        import matplotlib.pyplot as plt
        cmap = plt.cm.get_cmap("tab10" if n <= 10 else "tab20")
    return [cmap(i % cmap.N) for i in range(n)]


def _apply_cluster_colors(layer: object, cluster_colors: dict[int, tuple]) -> None:
    """Set label layer colours to match ``cluster_colors`` (1-based cluster IDs).

    Uses ``DirectLabelColormap`` (napari >= 0.5).  Silently skips if the API
    is unavailable.
    """
    if not cluster_colors:
        return
    try:
        import numpy as np
        from napari.utils.colormaps import DirectLabelColormap
        # Background (label 0 / None) → transparent
        color_dict: dict = {None: np.zeros(4)}
        for cid, rgba in cluster_colors.items():
            if cid > 0:
                color_dict[cid] = np.array(rgba, dtype=float)
        layer.colormap = DirectLabelColormap(color_dict=color_dict)
    except Exception:
        pass
