"""Painting and erasing helpers.

Planned responsibilities:
- brush radius face selection
- paint / erase face sets
- symmetry and mirror-point calculations
"""

from __future__ import annotations

import numpy as np


def faces_within_radius(face_centroids: np.ndarray, point: np.ndarray, radius_um: float) -> np.ndarray:
    """Return indices of mesh faces whose centroids are within a brush radius."""
    if face_centroids is None or len(face_centroids) == 0:
        return np.array([], dtype=int)
    distances = np.linalg.norm(face_centroids - point[None, :], axis=1)
    return np.where(distances <= radius_um)[0]


def mirror_point_across_z(point: np.ndarray, midline_z_um: float) -> np.ndarray:
    """Mirror an xyz point across the atlas ML/Z midline."""
    mirrored = np.asarray(point, dtype=float).copy()
    mirrored[2] = 2 * midline_z_um - mirrored[2]
    return mirrored
