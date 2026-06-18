"""2D slice plotting helpers.

Planned responsibilities:
- style coronal and sagittal Matplotlib axes
- draw painted ROI overlays on slices
- draw selected cells on slices
- draw the side-panel heatmap legend
"""

from __future__ import annotations

from .theme import SCENE_BACKGROUND, SCENE_TEXT_COLOR


def style_slice_axes(ax) -> None:
    """Apply shared dark styling to a 2D slice axis."""
    ax.set_facecolor(SCENE_BACKGROUND)
    ax.xaxis.label.set_color(SCENE_TEXT_COLOR)
    ax.yaxis.label.set_color(SCENE_TEXT_COLOR)
    ax.tick_params(axis="both", colors=SCENE_TEXT_COLOR, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#7c8aa5")
