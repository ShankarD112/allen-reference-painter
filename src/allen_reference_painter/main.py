"""Application entry point for Allen Reference Painter.

For now this launches the current modern window while the refactor branch
progressively moves logic into smaller modules.
"""

from __future__ import annotations

from .app_modern import main


if __name__ == "__main__":
    main()
