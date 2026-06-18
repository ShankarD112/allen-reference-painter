"""3D scene helpers for PyVista rendering."""

from __future__ import annotations

from .theme import SCENE_BACKGROUND, SCENE_GRID_COLOR, SCENE_TEXT_COLOR


def style_3d_scene(plotter) -> None:
    """Apply shared midnight styling to a PyVista scene."""
    try:
        plotter.set_background(SCENE_BACKGROUND)
        plotter.show_grid(
            color=SCENE_GRID_COLOR,
            font_size=8,
            grid="back",
            location="outer",
            xlabel="X / AP (um)",
            ylabel="Y / DV (um)",
            zlabel="Z / ML (um)",
        )
    except Exception:
        pass
    try:
        plotter.add_axes(line_width=2, color=SCENE_TEXT_COLOR)
    except Exception:
        pass
    try:
        plotter.render()
    except Exception:
        pass


def remove_scalar_bars(plotter) -> None:
    """Remove any PyVista scalar bars from the 3D scene."""
    try:
        scalar_bars = getattr(plotter, "scalar_bars", {})
        for name in list(scalar_bars.keys()):
            try:
                plotter.remove_scalar_bar(name)
            except Exception:
                pass
    except Exception:
        pass
