"""Interaction tools patch: camera panning plus paint undo/redo.

This module keeps the changes isolated from the large UI file.  It patches the
window class at launch time to add:

- Undo/redo stacks for painted face edits.
- Toolbar/status-bar buttons for Undo, Redo, and camera panning.
- Keyboard shortcuts: Ctrl+Z, Ctrl+Y, Ctrl+Shift+Z, and Alt+Arrow panning.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

import numpy as np
from qtpy import QtCore, QtWidgets
from qtpy.QtGui import QKeySequence, QShortcut


def _ensure_interaction_state(window: Any) -> None:
    if not hasattr(window, "_paint_undo_stack"):
        window._paint_undo_stack = []
    if not hasattr(window, "_paint_redo_stack"):
        window._paint_redo_stack = []


def _current_region(window: Any):
    active = getattr(window, "active_area", None)
    regions = getattr(window, "regions", {})
    if not active or active not in regions:
        return None
    return regions[active]


def _history_entry(area: str, before: set[int], after: set[int], action: str) -> dict[str, Any]:
    return {
        "area": area,
        "before": set(before),
        "after": set(after),
        "action": action,
    }


def _update_undo_redo_buttons(window: Any) -> None:
    try:
        undo_button = getattr(window, "undo_paint_button", None)
        redo_button = getattr(window, "redo_paint_button", None)
        if undo_button is not None:
            undo_button.setEnabled(bool(window._paint_undo_stack))
        if redo_button is not None:
            redo_button.setEnabled(bool(window._paint_redo_stack))
    except Exception:
        pass


def _restore_painted_faces(window: Any, area: str, faces: set[int], status_text: str) -> None:
    regions = getattr(window, "regions", {})
    if area not in regions:
        try:
            window._update_status(f"Cannot restore paint history: {area} is not loaded")
        except Exception:
            pass
        return

    region = regions[area]
    region.painted_faces = set(faces)
    try:
        window.active_area = area
        if hasattr(window, "active_combo"):
            window.active_combo.setCurrentText(area)
    except Exception:
        pass
    window._update_painted_overlay(region)
    window._refresh_scene()
    window._update_status(status_text)


def _undo_paint(window: Any) -> None:
    _ensure_interaction_state(window)
    if not window._paint_undo_stack:
        window._update_status("Nothing to undo")
        return
    entry = window._paint_undo_stack.pop()
    window._paint_redo_stack.append(entry)
    _restore_painted_faces(
        window,
        entry["area"],
        entry["before"],
        f"Undo {entry['action']} for {entry['area']}: {len(entry['before'])} painted faces",
    )
    _update_undo_redo_buttons(window)


def _redo_paint(window: Any) -> None:
    _ensure_interaction_state(window)
    if not window._paint_redo_stack:
        window._update_status("Nothing to redo")
        return
    entry = window._paint_redo_stack.pop()
    window._paint_undo_stack.append(entry)
    _restore_painted_faces(
        window,
        entry["area"],
        entry["after"],
        f"Redo {entry['action']} for {entry['area']}: {len(entry['after'])} painted faces",
    )
    _update_undo_redo_buttons(window)


def _camera_vectors(window: Any):
    camera = window.plotter.camera
    pos = np.asarray(camera.GetPosition(), dtype=float)
    focal = np.asarray(camera.GetFocalPoint(), dtype=float)
    view_up = np.asarray(camera.GetViewUp(), dtype=float)

    forward = focal - pos
    norm = np.linalg.norm(forward)
    if norm == 0:
        return None
    forward = forward / norm

    right = np.cross(forward, view_up)
    right_norm = np.linalg.norm(right)
    if right_norm == 0:
        return None
    right = right / right_norm

    up = np.cross(right, forward)
    up_norm = np.linalg.norm(up)
    if up_norm == 0:
        return None
    up = up / up_norm
    return camera, pos, focal, right, up


def _pan_view(window: Any, dx: float, dy: float) -> None:
    """Pan camera/focal point in the current screen plane.

    dx/dy are relative units. Positive dx moves the scene to the right; positive
    dy moves the scene upward from the user's current screen view.
    """

    try:
        values = _camera_vectors(window)
        if values is None:
            return
        camera, pos, focal, right, up = values
        if camera.GetParallelProjection():
            step = max(float(camera.GetParallelScale()) * 0.20, 10.0)
        else:
            step = max(float(camera.GetDistance()) * 0.08, 10.0)
        shift = (right * dx + up * dy) * step
        camera.SetPosition(*(pos + shift))
        camera.SetFocalPoint(*(focal + shift))
        try:
            window.plotter.renderer.SetActiveCamera(camera)
        except Exception:
            pass
        window.plotter.render()
        window._update_status("Panned 3D view. Shortcuts: Alt+Arrow keys")
    except Exception as exc:
        try:
            window._update_status(f"Could not pan view: {exc}")
        except Exception:
            pass


def _add_interaction_controls(window: Any) -> None:
    if getattr(window, "_interaction_controls_added", False):
        return
    _ensure_interaction_state(window)

    # Undo/redo buttons live in the status bar to avoid disturbing the dense top UI.
    undo_button = QtWidgets.QPushButton("Undo paint")
    undo_button.setToolTip("Undo last paint/erase/clear action (Ctrl+Z)")
    undo_button.clicked.connect(lambda: _undo_paint(window))
    window.statusBar().addPermanentWidget(undo_button)
    window.undo_paint_button = undo_button

    redo_button = QtWidgets.QPushButton("Redo paint")
    redo_button.setToolTip("Redo paint action (Ctrl+Y or Ctrl+Shift+Z)")
    redo_button.clicked.connect(lambda: _redo_paint(window))
    window.statusBar().addPermanentWidget(redo_button)
    window.redo_paint_button = redo_button

    pan_label = QtWidgets.QLabel("Pan:")
    window.statusBar().addPermanentWidget(pan_label)

    for text, dx, dy, tip in [
        ("←", -1, 0, "Pan left (Alt+Left)"),
        ("→", 1, 0, "Pan right (Alt+Right)"),
        ("↑", 0, 1, "Pan up (Alt+Up)"),
        ("↓", 0, -1, "Pan down (Alt+Down)"),
    ]:
        button = QtWidgets.QPushButton(text)
        button.setFixedWidth(34)
        button.setToolTip(tip)
        button.clicked.connect(lambda _=False, x=dx, y=dy: _pan_view(window, x, y))
        window.statusBar().addPermanentWidget(button)

    shortcuts = [
        ("Ctrl+Z", lambda: _undo_paint(window)),
        ("Ctrl+Y", lambda: _redo_paint(window)),
        ("Ctrl+Shift+Z", lambda: _redo_paint(window)),
        ("Alt+Left", lambda: _pan_view(window, -1, 0)),
        ("Alt+Right", lambda: _pan_view(window, 1, 0)),
        ("Alt+Up", lambda: _pan_view(window, 0, 1)),
        ("Alt+Down", lambda: _pan_view(window, 0, -1)),
    ]
    window._interaction_shortcuts = []
    for key, callback in shortcuts:
        shortcut = QShortcut(QKeySequence(key), window)
        shortcut.setContext(QtCore.Qt.ApplicationShortcut)
        shortcut.activated.connect(callback)
        window._interaction_shortcuts.append(shortcut)

    _update_undo_redo_buttons(window)
    window._interaction_controls_added = True


def _wrap_init(method: Callable) -> Callable:
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        _add_interaction_controls(self)
        return result

    return wrapped


def _wrap_paint_at_points(method: Callable) -> Callable:
    @wraps(method)
    def wrapped(self, points):
        _ensure_interaction_state(self)
        region = _current_region(self)
        if region is None:
            return method(self, points)
        before = set(region.painted_faces)
        action = getattr(self, "paint_mode", "paint")
        result = method(self, points)
        after = set(region.painted_faces)
        if before != after:
            self._paint_undo_stack.append(_history_entry(region.acronym, before, after, action))
            self._paint_redo_stack.clear()
            _update_undo_redo_buttons(self)
        return result

    return wrapped


def _wrap_clear_active_paint(method: Callable) -> Callable:
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        _ensure_interaction_state(self)
        region = _current_region(self)
        before = set(region.painted_faces) if region is not None else set()
        result = method(self, *args, **kwargs)
        if region is not None and before:
            after = set(region.painted_faces)
            if before != after:
                self._paint_undo_stack.append(_history_entry(region.acronym, before, after, "clear"))
                self._paint_redo_stack.clear()
                _update_undo_redo_buttons(self)
        return result

    return wrapped


def apply_interaction_tools_patch(window_cls: type) -> None:
    """Patch the painter window class with pan controls and paint undo/redo."""

    if getattr(window_cls, "_interaction_tools_patch_applied", False):
        return

    init_method = getattr(window_cls, "__init__", None)
    if init_method is not None:
        setattr(window_cls, "__init__", _wrap_init(init_method))

    paint_method = getattr(window_cls, "_paint_at_points", None)
    if paint_method is not None:
        setattr(window_cls, "_paint_at_points", _wrap_paint_at_points(paint_method))

    clear_method = getattr(window_cls, "_clear_active_paint", None)
    if clear_method is not None:
        setattr(window_cls, "_clear_active_paint", _wrap_clear_active_paint(clear_method))

    window_cls._interaction_tools_patch_applied = True
