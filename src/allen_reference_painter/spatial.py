"""Indexed brush queries; face numbering is never remeshed or simplified."""
from __future__ import annotations
import numpy as np
from scipy.spatial import cKDTree

class FaceIndex:
    def __init__(self, centroids):
        self.points = np.asarray(centroids, dtype=float)
        if self.points.ndim != 2 or self.points.shape[1] != 3 or not len(self.points):
            raise ValueError('A mesh must contain face centroids with shape (N, 3).')
        if not np.isfinite(self.points).all():
            raise ValueError('Mesh coordinates must be finite.')
        self.tree = cKDTree(self.points)

    def near(self, point, radius):
        ids = self.tree.query_ball_point(point, radius)
        # Match the original brush's nearest-face fallback, including ties.
        if not ids:
            distance, index = self.tree.query(point)
            tied = self.tree.query_ball_point(point, np.nextafter(distance, np.inf))
            index = min(tied, key=lambda i: (np.linalg.norm(self.points[i] - point), i))
            ids = [index]
        return set(map(int, ids))
