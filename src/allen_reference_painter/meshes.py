"""Mesh loading and export helpers.

Planned responsibilities:
- region mesh dataclasses
- BrainGlobe mesh loading wrappers
- painted-face mesh extraction
- ROI mesh and face-ID exports
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class RegionMeshState:
    """Lightweight serializable state for a loaded anatomical region."""

    acronym: str
    name: str
    structure_id: int | None = None
    descendant_ids: list[int] = field(default_factory=list)
    color: str = "#dddddd"
    visible: bool = True
    painted_faces: set[int] = field(default_factory=set)
    trimesh_mesh: Any | None = None
    pyvista_mesh: Any | None = None
    face_centroids: np.ndarray | None = None
