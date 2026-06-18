"""Patch screenshot exports so 2D images include the side-panel heat legend."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .theme import SCENE_BACKGROUND


def _stack_pngs_vertically(top_path: str, bottom_path: str, out_path: str) -> bool:
    """Stack two PNG files vertically using Pillow when available."""
    try:
        from PIL import Image
    except Exception:
        return False

    top = Image.open(top_path).convert("RGBA")
    bottom = Image.open(bottom_path).convert("RGBA")
    width = max(top.width, bottom.width)
    background = Image.new("RGBA", (width, top.height + bottom.height), (11, 16, 32, 255))
    background.paste(top, ((width - top.width) // 2, 0), top)
    background.paste(bottom, ((width - bottom.width) // 2, top.height), bottom)
    background.save(out_path)
    return True


def _save_figure_with_heat_legend(self, fig, stem: str) -> str:
    """Save a 2D Matplotlib figure with the current heat legend underneath."""
    path = self._screenshot_path(stem)
    has_legend = hasattr(self, "cell_colorbar_fig") and self.cell_colorbar_fig is not None
    heat_on = not hasattr(self, "cell_heatmap_2d_checkbox") or self.cell_heatmap_2d_checkbox.isChecked()

    if not has_legend or not heat_on:
        fig.savefig(path, dpi=220, facecolor=SCENE_BACKGROUND, bbox_inches="tight")
        return path

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        fig_path = str(tmpdir_path / "view.png")
        legend_path = str(tmpdir_path / "legend.png")
        fig.savefig(fig_path, dpi=220, facecolor=SCENE_BACKGROUND, bbox_inches="tight")
        self.cell_colorbar_fig.savefig(legend_path, dpi=220, facecolor=SCENE_BACKGROUND, bbox_inches="tight")
        if not _stack_pngs_vertically(fig_path, legend_path, path):
            fig.savefig(path, dpi=220, facecolor=SCENE_BACKGROUND, bbox_inches="tight")
    return path


def apply_screenshot_legend_patch(window_class) -> None:
    """Patch screenshot methods on the provided window class."""

    def _save_coronal_screenshot(self) -> str:
        path = _save_figure_with_heat_legend(self, self.coronal_fig, "coronal_2D_with_legend")
        self._update_status(f"Saved coronal screenshot with legend: {path}")
        return path

    def _save_sagittal_screenshot(self) -> str:
        path = _save_figure_with_heat_legend(self, self.sagittal_fig, "sagittal_2D_with_legend")
        self._update_status(f"Saved sagittal screenshot with legend: {path}")
        return path

    def _save_both_2d_screenshots(self) -> tuple[str, str]:
        coronal_path = self._save_coronal_screenshot()
        sagittal_path = self._save_sagittal_screenshot()
        self._update_status(f"Saved both 2D screenshots with legends: {coronal_path} and {sagittal_path}")
        return coronal_path, sagittal_path

    def _save_all_view_screenshots(self) -> None:
        scene_path = self._save_3d_screenshot()
        coronal_path, sagittal_path = self._save_both_2d_screenshots()
        self._update_status(f"Saved all views: {scene_path}, {coronal_path}, {sagittal_path}")

    window_class._save_coronal_screenshot = _save_coronal_screenshot
    window_class._save_sagittal_screenshot = _save_sagittal_screenshot
    window_class._save_both_2d_screenshots = _save_both_2d_screenshots
    window_class._save_all_view_screenshots = _save_all_view_screenshots
