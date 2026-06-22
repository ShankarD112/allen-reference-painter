"""Camera-preservation patch for interactive painting.

PyVista can reset the camera when actors are removed/added during painting,
pick-marker updates, slice-plane updates, or cell actor refreshes.  This patch
wraps the update methods used during painting so the user's current 3D view
angle and zoom are restored after the scene changes.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable


def _camera_snapshot(window: Any):
    """Return a copy of the current PyVista camera position, if available."""

    try:
        plotter = getattr(window, "plotter", None)
        if plotter is None:
            return None
        camera_position = getattr(plotter, "camera_position", None)
        if camera_position is None:
            return None
        return tuple(tuple(float(v) for v in point) for point in camera_position)
    except Exception:
        return None


def _restore_camera(window: Any, camera_position) -> None:
    """Restore a previously captured PyVista camera position."""

    if camera_position is None:
        return
    try:
        plotter = getattr(window, "plotter", None)
        if plotter is None:
            return
        plotter.camera_position = camera_position
    except Exception:
        return


def _wrap_preserve_camera(method: Callable) -> Callable:
    """Wrap one window method so actor updates do not reset the 3D camera."""

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        camera_position = _camera_snapshot(self)
        result = method(self, *args, **kwargs)
        _restore_camera(self, camera_position)
        try:
            self.plotter.render()
        except Exception:
            pass
        return result

    return wrapped


def apply_camera_preserve_patch(window_cls: type) -> None:
    """Apply camera-preserving wrappers to scene-update methods.

    This is intentionally idempotent so it is safe to call from the main launcher.
    """

    if getattr(window_cls, "_camera_preserve_patch_applied", False):
        return

    method_names = [
        "_update_painted_overlay",
        "_update_pick_markers",
        "_update_slice_planes",
        "_refresh_cell_actor",
        "_refresh_scene",
    ]

    for name in method_names:
        method = getattr(window_cls, name, None)
        if method is None:
            continue
        setattr(window_cls, name, _wrap_preserve_camera(method))

    window_cls._camera_preserve_patch_applied = True
