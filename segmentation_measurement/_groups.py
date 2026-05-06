"""Storage and lookup for named layer groups.

A *group* is the unit users batch over.  Each group bundles ordered lists
of layers under role names (segmentation, nucleus_segmentation,
intensity_image).  Within a group, layers are paired *by position*:
``segmentation[i]`` corresponds to ``nucleus_segmentation[i]`` and
``intensity_image[i]``.

The state is stored in a module-level :class:`WeakKeyDictionary` keyed
by :class:`napari.Viewer`, so it neither pollutes the viewer object nor
outlives it.  Each group looks like::

    {
        "experiment_1": {
            "segmentation": ["cells_01", "cells_02", "cells_03"],
            "nucleus_segmentation": ["nuclei_01", "nuclei_02", "nuclei_03"],
            "intensity_image": ["raw_01", "raw_02", "raw_03"],
        },
    }

Optional roles may be omitted or empty.  When provided, an optional role's
list must have the same length as the segmentation list — this enforces
unambiguous by-position pairing.

A rename listener keeps these references in sync when the user renames a
layer.  It is attached lazily on the first :func:`set_group` call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable
from weakref import WeakKeyDictionary

if TYPE_CHECKING:  # pragma: no cover - type hints only
    import napari


ROLE_SEGMENTATION = "segmentation"
ROLE_NUCLEUS_SEGMENTATION = "nucleus_segmentation"
ROLE_INTENSITY_IMAGE = "intensity_image"

VALID_ROLES = frozenset({
    ROLE_SEGMENTATION,
    ROLE_NUCLEUS_SEGMENTATION,
    ROLE_INTENSITY_IMAGE,
})
REQUIRED_ROLES = frozenset({ROLE_SEGMENTATION})

_viewer_state: "WeakKeyDictionary[object, dict]" = WeakKeyDictionary()


def _get_state(viewer: "napari.Viewer") -> dict:
    """Return the per-viewer state dict, initialising it on first access."""
    state = _viewer_state.get(viewer)
    if state is None:
        state = {
            "groups": {},
            "name_cache": WeakKeyDictionary(),
            "listener_attached": False,
            "subscribers": [],
        }
        _viewer_state[viewer] = state
    return state


def subscribe(
    viewer: "napari.Viewer", callback: Callable[[], None]
) -> Callable[[], None]:
    """Register ``callback`` to fire whenever the viewer's groups change.

    The callback is invoked with no arguments after :func:`set_group` and
    :func:`delete_group` complete.  Use this from widgets that mirror the
    list of defined groups (e.g. their *Target* combo).

    Args:
        viewer: napari Viewer instance.
        callback: Zero-argument callable.

    Returns:
        Callable[[], None]: An idempotent unsubscribe function.
    """
    subscribers = _get_state(viewer)["subscribers"]
    subscribers.append(callback)

    def _unsubscribe() -> None:
        try:
            subscribers.remove(callback)
        except ValueError:
            pass

    return _unsubscribe


def _notify(viewer: "napari.Viewer") -> None:
    """Fire all change subscribers for this viewer (errors swallowed)."""
    for callback in list(_get_state(viewer)["subscribers"]):
        try:
            callback()
        except Exception:  # pragma: no cover - subscriber bugs
            pass


def list_groups(viewer: "napari.Viewer") -> list[str]:
    """Return the names of all defined groups in insertion order.

    Args:
        viewer: napari Viewer instance.

    Returns:
        list[str]: Group names.  Empty if no groups have been defined.
    """
    return list(_get_state(viewer)["groups"].keys())


def get_group(viewer: "napari.Viewer", name: str) -> dict[str, list[str]]:
    """Return a deep copy of the group's role → layer-list mapping.

    Args:
        viewer: napari Viewer instance.
        name: Group name.

    Returns:
        dict[str, list[str]]: Mapping of role to current ordered layer
            names.  The lists are fresh copies safe to mutate.

    Raises:
        KeyError: If no group with this name exists.
    """
    groups = _get_state(viewer)["groups"]
    if name not in groups:
        raise KeyError(f"No group named '{name}'.")
    return {role: list(layers) for role, layers in groups[name].items()}


def iter_group_members(
    viewer: "napari.Viewer", name: str
) -> "list[dict[str, str]]":
    """Return one dict per group member with the layer at each role.

    The number of members equals the length of the segmentation list.
    Each member dict contains every role that is defined for the group
    (i.e. has at least one entry); roles whose lists are shorter than
    the segmentation list contribute ``None`` for the missing positions
    are simply absent in that member's dict — the helper assumes the
    length-consistency invariant enforced by :func:`set_group`.

    Args:
        viewer: napari Viewer instance.
        name: Group name.

    Returns:
        list[dict[str, str]]: One dict per member, in the order of the
            segmentation list.

    Raises:
        KeyError: If no group with this name exists.
    """
    members = get_group(viewer, name)
    n = len(members.get(ROLE_SEGMENTATION, []))
    return [
        {role: layers[i] for role, layers in members.items() if i < len(layers)}
        for i in range(n)
    ]


def set_group(
    viewer: "napari.Viewer",
    name: str,
    members: dict[str, list[str]],
) -> None:
    """Define or replace a group with the given name.

    Any previous definition under the same name is replaced.  All
    referenced layers must already be present in ``viewer.layers``.

    Within a group, layers across roles are paired *by position*:
    ``segmentation[i]`` corresponds to ``nucleus_segmentation[i]`` and
    ``intensity_image[i]``.  An optional role may be omitted or supplied
    as an empty list; when non-empty, its length must equal the
    segmentation list's length.

    On the first call this also wires up a rename listener that keeps
    stored layer names in sync when a layer is renamed.

    Args:
        viewer: napari Viewer instance.
        name: Non-empty group name.
        members: Mapping of role → ordered list of layer names.  Must
            contain :data:`ROLE_SEGMENTATION` with at least one entry.
            Allowed roles are listed in :data:`VALID_ROLES`.

    Raises:
        ValueError: If ``name`` is empty, ``members`` is missing the
            required role, contains an unknown role, the segmentation
            list is empty, an optional role's non-empty list has a
            different length than the segmentation list, or any list
            references a layer not currently in the viewer.  Duplicate
            entries within a single role's list are also rejected.
    """
    if not name:
        raise ValueError("Group name must be a non-empty string.")
    unknown = set(members) - VALID_ROLES
    if unknown:
        raise ValueError(
            f"Unknown role(s): {sorted(unknown)}. "
            f"Valid roles: {sorted(VALID_ROLES)}."
        )
    missing = REQUIRED_ROLES - set(members)
    if missing:
        raise ValueError(f"Missing required role(s): {sorted(missing)}.")

    normalized: dict[str, list[str]] = {}
    for role, layers in members.items():
        if not isinstance(layers, (list, tuple)):
            raise ValueError(
                f"Role '{role}' must map to a list of layer names; "
                f"got {type(layers).__name__}."
            )
        normalized[role] = list(layers)

    seg_layers = normalized.get(ROLE_SEGMENTATION, [])
    if len(seg_layers) == 0:
        raise ValueError(
            f"Group '{name}' must contain at least one segmentation layer."
        )

    n = len(seg_layers)
    for role, layers in normalized.items():
        if role == ROLE_SEGMENTATION:
            continue
        if len(layers) > 0 and len(layers) != n:
            raise ValueError(
                f"Group '{name}' role '{role}' has {len(layers)} layer(s) "
                f"but '{ROLE_SEGMENTATION}' has {n}. "
                f"Optional roles must be empty or match the segmentation "
                f"list length for by-position pairing."
            )

    layer_names = {layer.name for layer in viewer.layers}
    for role, layers in normalized.items():
        if len(set(layers)) != len(layers):
            raise ValueError(
                f"Group '{name}' role '{role}' contains duplicate entries: "
                f"{layers}."
            )
        for layer_name in layers:
            if layer_name not in layer_names:
                raise ValueError(
                    f"Group '{name}' role '{role}' references layer "
                    f"'{layer_name}', which is not in the viewer."
                )

    state = _get_state(viewer)
    state["groups"][name] = normalized
    _ensure_listener_attached(viewer)
    _notify(viewer)


def delete_group(viewer: "napari.Viewer", name: str) -> None:
    """Remove a group by name.  No-op if it does not exist.

    Args:
        viewer: napari Viewer instance.
        name: Group name.
    """
    state = _get_state(viewer)
    if state["groups"].pop(name, None) is not None:
        _notify(viewer)


def _ensure_listener_attached(viewer: "napari.Viewer") -> None:
    """Attach a layer-rename listener once per viewer (idempotent).

    napari's ``layer.events.name`` does not carry the *old* name, so we
    cache each layer's last-known name in a :class:`WeakKeyDictionary`
    and diff against ``layer.name`` on each event.  When a rename is
    detected, every group's role lists are walked and each occurrence of
    the old name replaced with the new one.
    """
    state = _get_state(viewer)
    if state["listener_attached"]:
        return
    cache: "WeakKeyDictionary[object, str]" = state["name_cache"]

    def _on_name(event: object) -> None:
        layer = getattr(event, "source", None)
        if layer is None:
            return
        old = cache.get(layer)
        new = layer.name
        cache[layer] = new
        if old is None or old == new:
            return
        for members in state["groups"].values():
            for role, layers in members.items():
                members[role] = [new if v == old else v for v in layers]

    def _on_inserted(event: object) -> None:
        layer = getattr(event, "value", None)
        if layer is None:
            return
        cache[layer] = layer.name
        try:
            layer.events.name.connect(_on_name)
        except AttributeError:
            pass

    for layer in viewer.layers:
        cache[layer] = layer.name
        try:
            layer.events.name.connect(_on_name)
        except AttributeError:
            pass
    viewer.layers.events.inserted.connect(_on_inserted)
    state["listener_attached"] = True
