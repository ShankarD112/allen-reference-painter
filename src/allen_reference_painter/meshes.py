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


def load_atlas_mesh(atlas, structure):
    """Load normalized atlas-space geometry through BrainGlobe's public API.

    Modern atlases lazily download Draco meshes. Their raw files are in XYZ
    nanometers, so reading meshfile_from_structure directly is incorrect.
    mesh_from_structure handles download, decoding, orientation and µm scaling.
    Do not process/reorder the returned triangles: exports retain these IDs.
    """
    import trimesh
    if hasattr(atlas, 'mesh_from_structure'):
        source = atlas.mesh_from_structure(structure)
        if source is None:
            raise ValueError(f'No mesh is available for {structure}.')
        if isinstance(source, trimesh.Trimesh):
            vertices, faces = source.vertices, source.faces
        else:
            vertices = np.asarray(source.points)
            faces = np.asarray(source.get_cells_type('triangle'))
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    else:
        # The offline demo (and older file-based adapters) expose ordinary PLY.
        mesh = trimesh.load(atlas.meshfile_from_structure(structure), force='mesh', process=False)
    if not len(mesh.vertices) or not len(mesh.faces):
        raise ValueError(f'{structure} has no triangle geometry.')
    if not np.isfinite(mesh.vertices).all():
        raise ValueError(f'{structure} contains nonfinite coordinates.')
    if mesh.faces.min() < 0 or mesh.faces.max() >= len(mesh.vertices):
        raise ValueError(f'{structure} contains invalid triangle indices.')
    return mesh
