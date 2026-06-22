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

    `plotter.camera_position` is not always enough to preserve zoom. Some actor
    updates can change clipping range, parallel scale, or camera distance while
    leaving the view direction mostly intact. We therefore snapshot the
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


def _patch_plotter_add_mesh(window: Any) -> None:
    """Make runtime PyVista mesh additions preserve the current camera by default.

    Many paint updates create temporary actors with ``plotter.add_mesh``. In
    PyVista, ``add_mesh`` can reset camera bounds unless ``reset_camera=False``
    is passed. This instance-level patch adds that default without touching
    explicit calls that already pass their own ``reset_camera`` value.
    """

    try:
        plotter = getattr(window, "plotter", None)
        if plotter is None or getattr(plotter, "_arp_add_mesh_patched", False):
            return
        original_add_mesh = plotter.add_mesh

        @wraps(original_add_mesh)
        def add_mesh_no_camera_reset(*args, **kwargs):
            kwargs.setdefault("reset_camera", False)
            camera_state = _camera_snapshot(window)
            result = original_add_mesh(*args, **kwargs)
            _restore_camera(window, camera_state)
            return result

        plotter.add_mesh = add_mesh_no_camera_reset
        plotter._arp_add_mesh_patched = True
    except Exception:
        return


def _wrap_init(method: Callable) -> Callable:
    """Patch the PyVista plotter immediately after the window is created."""

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        _patch_plotter_add_mesh(self)
        return result

    return wrapped


def _wrap_preserve_camera(method: Callable) -> Callable:
    """Wrap one window method so actor updates do not reset the 3D camera."""

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        _patch_plotter_add_mesh(self)
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

    init_method = getattr(window_cls, "__init__", None)
    if init_method is not None:
        setattr(window_cls, "__init__", _wrap_init(init_method))

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
