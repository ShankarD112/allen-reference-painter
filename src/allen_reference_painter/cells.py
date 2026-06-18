"""Cell coordinate utilities for loading, unit conversion, and selection."""

from __future__ import annotations

import numpy as np
import pandas as pd

CELL_UNIT_OPTIONS = {
    "Microns / atlas space (um)": "um",
    "Millimeters (mm -> um x1000)": "mm",
    "Voxel indices (index -> um using atlas resolution)": "voxel",
    "Auto detect": "auto",
}

X_ALIASES = ["x", "x_um", "atlas_x", "ap", "ap_um"]
Y_ALIASES = ["y", "y_um", "atlas_y", "dv", "dv_um"]
Z_ALIASES = ["z", "z_um", "atlas_z", "ml", "ml_um"]


def selected_indices(mask: np.ndarray | None, n_rows: int) -> np.ndarray:
    """Return selected row indices, defaulting to all rows."""
    if mask is None or len(mask) != n_rows:
        return np.arange(n_rows, dtype=int)
    return np.where(mask.astype(bool))[0]


def numeric_values(dataframe: pd.DataFrame, indices: np.ndarray, column: str) -> tuple[np.ndarray | None, float | None, float | None]:
    """Return finite numeric values for a selected dataframe column."""
    if column not in dataframe.columns or len(indices) == 0:
        return None, None, None
    values = pd.to_numeric(dataframe.iloc[indices][column], errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(values)
    if not np.any(finite):
        return None, None, None
    values = np.where(finite, values, float(np.nanmedian(values[finite])))
    return values, float(np.min(values)), float(np.max(values))


def find_column(columns: list[str], aliases: list[str]) -> str | None:
    """Find a coordinate column by case-insensitive aliases."""
    lookup = {str(c).lower(): str(c) for c in columns}
    for alias in aliases:
        if alias.lower() in lookup:
            return lookup[alias.lower()]
    return None
