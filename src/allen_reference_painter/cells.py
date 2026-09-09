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


def convert_coordinates(xyz, mode, resolution, shape):
    """Convert explicit units. Auto is a suggestion, never accepted silently."""
    xyz = np.asarray(xyz, dtype=float)
    if xyz.ndim != 2 or xyz.shape[1] != 3 or not np.isfinite(xyz).all():
        raise ValueError('Coordinates must be finite numbers in three columns.')
    if mode == 'auto':
        raise ValueError('Choose microns, millimeters, or voxel indices explicitly; small values are ambiguous.')
    factors = {'um': np.ones(3), 'mm': np.full(3, 1000.), 'voxel': np.asarray(resolution, dtype=float)}
    if mode not in factors:
        raise ValueError(f'Unknown coordinate unit: {mode}')
    return xyz * factors[mode], {'um': 'microns', 'mm': 'millimeters converted to microns x1000', 'voxel': 'voxel indices converted to microns'}[mode]


def read_cells(path):
    """Read coordinates without silently dropping invalid scientific observations."""
    from pathlib import Path
    path = Path(path)
    if path.suffix.lower() in {'.xls', '.xlsx'}:
        df = pd.read_excel(path)
    elif path.suffix.lower() == '.tsv':
        df = pd.read_csv(path, sep='\t')
    else:
        df = pd.read_csv(path, sep=None, engine='python')
    df.columns = [str(c).strip() for c in df.columns]
    cols = [find_column(list(df.columns), aliases) for aliases in (X_ALIASES, Y_ALIASES, Z_ALIASES)]
    if any(c is None for c in cols):
        raise ValueError('Use coordinate columns x/y/z or AP/DV/ML (also accepts x_um/y_um/z_um).')
    xyz = df[cols].apply(pd.to_numeric, errors='coerce').to_numpy(dtype=float)
    bad = np.flatnonzero(~np.isfinite(xyz).all(axis=1))
    if len(bad):
        raise ValueError(f'{len(bad)} rows have missing or invalid coordinates. First data rows: {(bad[:8] + 1).tolist()}. Correct the file and retry.')
    if not len(df):
        raise ValueError('The cell table contains no data rows.')
    return df.reset_index(drop=True), xyz
