"""Napari dock widget for managing layer groups.

A *group* is the unit users batch over.  Each group bundles ordered
lists of layers under role names (segmentation, nucleus_segmentation,
intensity_image).  Within a group, layers across roles are paired by
position: ``segmentation[i]`` corresponds to
``nucleus_segmentation[i]`` and ``intensity_image[i]``.

The Group Manager UI lets the user populate each role's list from the
napari layer selection, reorder entries, and preview the resulting
pairing as a table before saving.
"""

from __future__ import annotations

from math import ceil, sqrt

import napari
from qtpy.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from segmentation_measurement._groups import (
    ROLE_INTENSITY_IMAGE,
    ROLE_NUCLEUS_SEGMENTATION,
    ROLE_SEGMENTATION,
    delete_group,
    get_group,
    list_groups,
    set_group,
    subscribe,
)

_NAME_ROLE = 0x0100  # Qt.UserRole — store raw group name on list items.
_GRID_LINK_EXCLUDED_ATTRIBUTES = frozenset({
    "affine",
    "axis_labels",
    "data",
    "extent",
    "features",
    "loaded",
    "metadata",
    "mode",
    "name",
    "properties",
    "rotate",
    "scale",
    "shear",
    "status",
    "thumbnail",
    "translate",
    "units",
})


class GroupManagerWidget(QWidget):
    """Dock widget for creating, editing, and deleting layer groups.

    The list at the top shows every defined group.  Selecting a group
    loads its current members into the editor below.  Each role section
    displays an ordered list with *Add selected* / *Remove* / *Up* /
    *Down* controls; *Add selected* picks layers from the napari layer
    selection (filtered to the right type).  The pairing preview at the
    bottom shows the resulting per-row triples so the user can verify
    that ``segmentation[i]`` is matched with the intended
    ``nucleus_segmentation[i]`` and ``intensity_image[i]``.
    """

    def __init__(self, napari_viewer: napari.Viewer) -> None:
        super().__init__()
        self._viewer = napari_viewer
        self._role_lists: dict[str, QListWidget] = {}
        self._setup_ui()
        self._unsubscribe = subscribe(self._viewer, self._refresh_group_list)
        self.destroyed.connect(lambda *_: self._unsubscribe())
        self._refresh_group_list()

    # --------------------------------------------------------------- UI ---

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

        list_group = QGroupBox("Defined groups")
        list_layout = QVBoxLayout()
        self._group_list = QListWidget()
        self._group_list.itemSelectionChanged.connect(self._on_select)
        list_layout.addWidget(self._group_list)
        delete_btn = QPushButton("Delete selected")
        delete_btn.clicked.connect(self._delete_selected)
        list_layout.addWidget(delete_btn)
        arrange_btn = QPushButton("Arrange selected as grid")
        arrange_btn.clicked.connect(self._arrange_selected_as_grid)
        list_layout.addWidget(arrange_btn)
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        editor_group = QGroupBox("Group editor")
        editor_layout = QVBoxLayout()

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self._name_edit = QLineEdit()
        name_row.addWidget(self._name_edit)
        editor_layout.addLayout(name_row)

        editor_layout.addWidget(self._build_role_section(
            ROLE_SEGMENTATION,
            "Segmentation layers (required)",
            labels_only=True,
        ))
        editor_layout.addWidget(self._build_role_section(
            ROLE_NUCLEUS_SEGMENTATION,
            "Nucleus layers (optional)",
            labels_only=True,
        ))
        editor_layout.addWidget(self._build_role_section(
            ROLE_INTENSITY_IMAGE,
            "Intensity images (optional)",
            labels_only=False,
        ))

        preview_group = QGroupBox("Pairing preview")
        preview_layout = QVBoxLayout()
        self._preview_table = QTableWidget(0, 3)
        self._preview_table.setHorizontalHeaderLabels(
            ["Segmentation", "Nucleus", "Intensity image"]
        )
        self._preview_table.verticalHeader().setVisible(False)
        self._preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self._preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._preview_table.setSelectionMode(QAbstractItemView.NoSelection)
        preview_layout.addWidget(self._preview_table)
        preview_group.setLayout(preview_layout)
        editor_layout.addWidget(preview_group)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        editor_layout.addWidget(save_btn)

        editor_group.setLayout(editor_layout)
        layout.addWidget(editor_group)
        layout.addStretch()

    def _build_role_section(
        self, role: str, title: str, labels_only: bool
    ) -> QGroupBox:
        group = QGroupBox(title)
        section = QVBoxLayout()

        list_widget = QListWidget()
        list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        list_widget.model().rowsInserted.connect(
            lambda *_: self._update_preview()
        )
        list_widget.model().rowsRemoved.connect(
            lambda *_: self._update_preview()
        )
        self._role_lists[role] = list_widget
        section.addWidget(list_widget)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add selected")
        add_btn.clicked.connect(
            lambda _checked=False, r=role, lo=labels_only: (
                self._add_selected(r, lo)
            )
        )
        btn_row.addWidget(add_btn)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(
            lambda _checked=False, r=role: self._remove_from(r)
        )
        btn_row.addWidget(remove_btn)
        up_btn = QPushButton("Up")
        up_btn.clicked.connect(
            lambda _checked=False, r=role: self._move(r, -1)
        )
        btn_row.addWidget(up_btn)
        down_btn = QPushButton("Down")
        down_btn.clicked.connect(
            lambda _checked=False, r=role: self._move(r, +1)
        )
        btn_row.addWidget(down_btn)
        section.addLayout(btn_row)

        group.setLayout(section)
        return group

    # --------------------------------------------------------- Plumbing ---

    def _role_layer_names(self, role: str) -> set[str]:
        list_widget = self._role_lists[role]
        return {list_widget.item(i).text() for i in range(list_widget.count())}

    def _role_layers_ordered(self, role: str) -> list[str]:
        list_widget = self._role_lists[role]
        return [list_widget.item(i).text() for i in range(list_widget.count())]

    def _update_preview(self) -> None:
        seg = self._role_layers_ordered(ROLE_SEGMENTATION)
        nuc = self._role_layers_ordered(ROLE_NUCLEUS_SEGMENTATION)
        img = self._role_layers_ordered(ROLE_INTENSITY_IMAGE)
        n_rows = max(len(seg), len(nuc), len(img))
        self._preview_table.setRowCount(n_rows)
        for i in range(n_rows):
            for col, lst in enumerate([seg, nuc, img]):
                text = lst[i] if i < len(lst) else ""
                self._preview_table.setItem(i, col, QTableWidgetItem(text))

    def _refresh_group_list(self) -> None:
        current = (
            self._group_list.currentItem().data(_NAME_ROLE)
            if self._group_list.currentItem() is not None
            else None
        )
        self._group_list.blockSignals(True)
        self._group_list.clear()
        for name in list_groups(self._viewer):
            members = get_group(self._viewer, name)
            item = QListWidgetItem(self._format_group_label(name, members))
            item.setData(_NAME_ROLE, name)
            self._group_list.addItem(item)
        self._group_list.blockSignals(False)
        if current:
            for i in range(self._group_list.count()):
                if self._group_list.item(i).data(_NAME_ROLE) == current:
                    self._group_list.setCurrentRow(i)
                    break

    @staticmethod
    def _format_group_label(name: str, members: dict[str, list[str]]) -> str:
        parts = [f"{len(members.get(ROLE_SEGMENTATION, []))} seg"]
        nuc_n = len(members.get(ROLE_NUCLEUS_SEGMENTATION, []))
        if nuc_n:
            parts.append(f"{nuc_n} nuc")
        img_n = len(members.get(ROLE_INTENSITY_IMAGE, []))
        if img_n:
            parts.append(f"{img_n} img")
        return f"{name}  ({', '.join(parts)})"

    # --------------------------------------------------------- Actions ---

    def _add_selected(self, role: str, labels_only: bool) -> None:
        from napari.layers import Image, Labels
        target_class = Labels if labels_only else Image
        list_widget = self._role_lists[role]
        existing = self._role_layer_names(role)
        # Iterate over the layer list itself (not the selection) so that the
        # order in which layers are added matches the layer-panel order — the
        # selection is a set and has no defined iteration order.
        selection = self._viewer.layers.selection
        for layer in self._viewer.layers:
            if layer not in selection:
                continue
            if not isinstance(layer, target_class):
                continue
            if layer.name in existing:
                continue
            list_widget.addItem(layer.name)
            existing.add(layer.name)

    def _remove_from(self, role: str) -> None:
        list_widget = self._role_lists[role]
        for item in list_widget.selectedItems():
            list_widget.takeItem(list_widget.row(item))

    def _move(self, role: str, direction: int) -> None:
        list_widget = self._role_lists[role]
        row = list_widget.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= list_widget.count():
            return
        item = list_widget.takeItem(row)
        list_widget.insertItem(new_row, item)
        list_widget.setCurrentRow(new_row)

    def _on_select(self) -> None:
        item = self._group_list.currentItem()
        if item is None:
            return
        name = item.data(_NAME_ROLE)
        try:
            members = get_group(self._viewer, name)
        except KeyError:
            return
        self._name_edit.setText(name)
        for role, list_widget in self._role_lists.items():
            list_widget.blockSignals(True)
            list_widget.clear()
            list_widget.addItems(members.get(role, []))
            list_widget.blockSignals(False)
        self._update_preview()

    def _save(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid name", "Group name is empty.")
            return
        seg = self._role_layers_ordered(ROLE_SEGMENTATION)
        if not seg:
            QMessageBox.warning(
                self,
                "No segmentation",
                "Add at least one segmentation layer (the only required role).",
            )
            return
        members: dict[str, list[str]] = {ROLE_SEGMENTATION: seg}
        nuc = self._role_layers_ordered(ROLE_NUCLEUS_SEGMENTATION)
        if nuc:
            members[ROLE_NUCLEUS_SEGMENTATION] = nuc
        img = self._role_layers_ordered(ROLE_INTENSITY_IMAGE)
        if img:
            members[ROLE_INTENSITY_IMAGE] = img
        try:
            set_group(self._viewer, name, members)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not save group", str(exc))

    def _delete_selected(self) -> None:
        item = self._group_list.currentItem()
        if item is None:
            return
        delete_group(self._viewer, item.data(_NAME_ROLE))

    def _arrange_selected_as_grid(self) -> None:
        item = self._group_list.currentItem()
        if item is None:
            QMessageBox.warning(
                self,
                "No group selected",
                "Select a group to arrange it as a grid.",
            )
            return
        name = item.data(_NAME_ROLE)
        try:
            members = get_group(self._viewer, name)
            self._arrange_group_as_grid(members)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, "Could not arrange group", str(exc))

    def _arrange_group_as_grid(self, members: dict[str, list[str]]) -> None:
        seg_names = members.get(ROLE_SEGMENTATION, [])
        if not seg_names:
            raise ValueError("The group does not contain segmentation layers.")

        seg_layers = [self._get_layer(name) for name in seg_names]
        cell_shape = self._grid_cell_shape(seg_layers)
        n_cols = ceil(sqrt(len(seg_layers)))

        for index, seg_layer in enumerate(seg_layers):
            row, col = divmod(index, n_cols)
            offset = (row * cell_shape[0], col * cell_shape[1])
            for role in (
                ROLE_INTENSITY_IMAGE,
                ROLE_NUCLEUS_SEGMENTATION,
                ROLE_SEGMENTATION,
            ):
                layer_names = members.get(role, [])
                if index >= len(layer_names):
                    continue
                layer = self._get_layer(layer_names[index])
                self._set_layer_grid_position(layer, offset)

        for role in (
            ROLE_SEGMENTATION,
            ROLE_NUCLEUS_SEGMENTATION,
            ROLE_INTENSITY_IMAGE,
        ):
            self._link_role_layers(members.get(role, []))

        # Move arranged layers to the top in draw order for each grid cell:
        # intensity at the bottom, then nucleus labels, then segmentation.
        for index in range(len(seg_layers)):
            for role in (
                ROLE_INTENSITY_IMAGE,
                ROLE_NUCLEUS_SEGMENTATION,
                ROLE_SEGMENTATION,
            ):
                layer_names = members.get(role, [])
                if index < len(layer_names):
                    self._move_layer_to_top(layer_names[index])

    def _get_layer(self, name: str) -> napari.layers.Layer:
        try:
            return self._viewer.layers[name]
        except KeyError as exc:
            raise ValueError(
                f"Group references layer '{name}', which is not in the viewer."
            ) from exc

    @staticmethod
    def _grid_cell_shape(layers: list[napari.layers.Layer]) -> tuple[float, float]:
        sizes = []
        for layer in layers:
            shape = getattr(layer.data, "shape", ())
            if len(shape) < 2:
                raise ValueError(
                    f"Layer '{layer.name}' must have at least two dimensions "
                    "to be arranged in a grid."
                )
            scale = layer.scale
            size_y = float(shape[-2]) * float(scale[-2])
            size_x = float(shape[-1]) * float(scale[-1])
            sizes.append((size_y, size_x))
        max_y = max(size[0] for size in sizes)
        max_x = max(size[1] for size in sizes)
        return max_y, max_x

    @staticmethod
    def _set_layer_grid_position(
        layer: napari.layers.Layer, offset: tuple[float, float]
    ) -> None:
        translate = layer.translate.copy()
        translate[-2] = offset[0]
        translate[-1] = offset[1]
        layer.translate = translate

    def _link_role_layers(self, layer_names: list[str]) -> None:
        if len(layer_names) < 2:
            return
        layers = [self._get_layer(name) for name in layer_names]
        attrs = self._linkable_non_spatial_attributes(layers)
        if attrs:
            self._viewer.layers.link_layers(layers, attributes=attrs)

    @staticmethod
    def _linkable_non_spatial_attributes(
        layers: list[napari.layers.Layer],
    ) -> list[str]:
        common = set.intersection(*(set(layer.events) for layer in layers))
        common -= _GRID_LINK_EXCLUDED_ATTRIBUTES
        attrs = []
        for attr in common:
            if attr.startswith("_"):
                continue
            if all(
                hasattr(layer, attr) and not callable(getattr(layer, attr))
                for layer in layers
            ):
                attrs.append(attr)
        return sorted(attrs)

    def _move_layer_to_top(self, layer_name: str) -> None:
        layer = self._get_layer(layer_name)
        layers = self._viewer.layers
        src = layers.index(layer)
        layers.move(src, len(layers))
