"""Explicit synthetic atlas for offline demonstrations and deterministic GUI tests.

Never label this data as Allen anatomy or use it for scientific analysis.
"""
from pathlib import Path
import tempfile
import numpy as np
import trimesh

class DemoAtlas:
    is_demo = True
    resolution = (25,25,25)
    atlas_name = 'synthetic_demo'

    def __init__(self):
        self._folder = tempfile.TemporaryDirectory(prefix='allen-painter-demo-')
        self.structures = {
            1: dict(acronym='root', name='Synthetic reference shell', rgb_triplet=[150,180,210], structure_id_path=[1]),
            2: dict(acronym='DEMO', name='Synthetic practice region', rgb_triplet=[70,190,170], structure_id_path=[1,2]),
        }
        self.annotation = np.zeros((96,72,80),dtype=np.uint16)
        x,y,z = np.ogrid[:96,:72,:80]
        self.annotation[((x-48)/42)**2+((y-36)/30)**2+((z-40)/34)**2<1] = 1
        self.annotation[((x-48)/24)**2+((y-36)/19)**2+((z-40)/20)**2<1] = 2
        for acronym,radii in [('root',(1050,750,850)),('DEMO',(600,475,500))]:
            mesh = trimesh.creation.icosphere(subdivisions=4)
            mesh.vertices *= np.asarray(radii)
            mesh.vertices += np.array([1200,900,1000])
            mesh.export(Path(self._folder.name)/f'{acronym}.ply')

    def meshfile_from_structure(self, acronym):
        path = Path(self._folder.name)/f'{acronym}.ply'
        if not path.exists():
            raise ValueError('Demo mode contains only root and DEMO. Open the Allen atlas for real regions.')
        return path
