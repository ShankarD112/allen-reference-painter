"""Screenshot/export helpers for app views."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def timestamped_png_path(output_dir: Path, stem: str) -> str:
    """Create a timestamped PNG path under the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    return str(output_dir / f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")


def save_matplotlib_figure(fig, output_dir: Path, stem: str, facecolor: str, dpi: int = 220) -> str:
    """Save a Matplotlib figure to a timestamped PNG."""
    path = timestamped_png_path(output_dir, stem)
    fig.savefig(path, dpi=dpi, facecolor=facecolor, bbox_inches="tight")
    return path


def save_pyvista_plotter(plotter, output_dir: Path, stem: str) -> str:
    """Save the current PyVista scene to a timestamped PNG."""
    path = timestamped_png_path(output_dir, stem)
    plotter.screenshot(path)
    return path
