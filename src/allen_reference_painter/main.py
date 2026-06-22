"""Application entry point for Allen Reference Painter.

For now this launches the current modern window while the refactor branch
progressively moves logic into smaller modules.
"""

from __future__ import annotations

from . import app_modern
from .camera_preserve_patch import apply_camera_preserve_patch
from .screenshot_legend_patch import apply_screenshot_legend_patch


apply_camera_preserve_patch(app_modern.ModernMeshPainterWindow)
apply_screenshot_legend_patch(app_modern.ModernMeshPainterWindow)
main = app_modern.main


if __name__ == "__main__":
    main()
