"""Atlas configuration and region color helpers."""

from __future__ import annotations

ATLAS_NAME = "allen_mouse_25um"
REFERENCE_SHELL_CANDIDATES = ["root", "grey", "CH", "CTX", "HPF"]

FALLBACK_REGION_COLORS = {
    "ENT": "#c8c5ff",
    "PAR": "#d4ffff",
    "POST": "#e8fbff",
    "PRE": "#eef8ff",
    "SUB": "#f2f4ff",
    "ProS": "#f3f1fb",
    "HATA": "#edfafa",
    "APr": "#f0fbff",
    "PERI": "#f5d8f7",
    "ECT": "#f2faf8",
}


def region_color(acronym: str, default: str = "#dddddd") -> str:
    """Return a friendly display color for an Allen acronym."""
    return FALLBACK_REGION_COLORS.get(acronym, default)
