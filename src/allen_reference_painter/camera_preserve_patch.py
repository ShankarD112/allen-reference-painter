"""Camera-preservation patch for interactive painting.

PyVista can reset the camera when actors are removed/added during painting,
pick-marker updates, slice-plane updates, or cell actor refreshes.  This patch
wraps the update methods used during painting so the user's current 3D view
angle and zoom are restored after the scene changes.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable


def _tuple3(value) -> tuple[float, float, float]:
    return tuple(float(v) for v in value)


def _camera_snapshot(window: Any) -> dict[str, Any] | None:
    """Return a full copy of the current VTK/PyVista camera state.

    `plotter.camera_position` is not always enough to preserve zoom.  Some
    actor updates can change clipping range, parallel scale, or camera distance
    while leaving the view direction mostly intact.  We therefore snapshot the
    underlying VTK camera parameters directly.
    """

    try:
        plotter = getattr(window, "plotter", None)
        if plotter is None:
            return None
        camera = getattr(plotter, "camera", None)
        if camera is None:
            return None
        return {
            "position": _tuple3(camera.GetPosition()),
            "focal_point": _tuple3(camera.GetFocalPoint()),
            "view_up": _tuple3(camera.GetViewUp()),
            "clipping_range": tuple(float(v) for v in camera.GetClippingRange()),
            "view_angle": float(camera.GetViewAngle()),
            "parallel_scale": float(camera.GetParallelScale()),
            "parallel_projection": bool(camera.GetParallelProjection()),
            "distance": float(camera.GetDistance()),
        }
    except Exception:
        return None


def _restore_camera(window: Any, state: dict[str, Any] | None) -> None:
    """Restore a previously captured VTK/PyVista camera state."""

    if state is None:
        return
    try:
        plotter = getattr(window, "plotter", None)
        if plotter is None:
            return
        camera = getattr(plotter, "camera", None)
        if camera is None:
            return

        camera.SetPosition(*state["position"])
        camera.SetFocalPoint(*state["focal_point"])
        camera.SetViewUp(*state["view_up"])
        camera.SetClippingRange(*state["clipping_range"])
        camera.SetViewAngle(state["view_angle"])
        camera.SetParallelScale(state["parallel_scale"])
        camera.SetParallelProjection(1 if state["parallel_projection"] else 0)

        # Keep both PyVista and VTK in sync without asking PyVista to reset.
        try:
            plotter.camera = camera
        except Exception:
            pass
        try:
            plotter.renderer.SetActiveCamera(camera)
        except Exception:
            pass
    except Exception:
        return


def _wrap_preserve_camera(method: Callable) -> Callable:
    """Wrap one window method so actor updates do not reset the 3D camera."""

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        camera_state = _camera_snapshot(self)
        result = method(self, *args, **kwargs)
        _restore_camera(self, camera_state)
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
        "_paint_from_mouse",
        "_paint_at_points",
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
