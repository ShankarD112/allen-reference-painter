import unittest
from unittest.mock import Mock
import numpy as np
import meshio
from allen_reference_painter.meshes import load_atlas_mesh

class AtlasMeshTests(unittest.TestCase):
    def test_public_api_preserves_normalized_coordinates_and_face_order(self):
        points=np.array([[1.,2.,3.],[4.,5.,6.],[7.,8.,9.],[10.,11.,12.]])
        faces=np.array([[3,1,0],[1,2,3]])
        atlas=Mock()
        atlas.mesh_from_structure.return_value=meshio.Mesh(points=points,cells=[('triangle',faces)])
        result=load_atlas_mesh(atlas,'ENT')
        atlas.mesh_from_structure.assert_called_once_with('ENT')
        atlas.meshfile_from_structure.assert_not_called()
        np.testing.assert_array_equal(result.vertices,points)
        np.testing.assert_array_equal(result.faces,faces)

    def test_missing_mesh_fails_visibly(self):
        atlas=Mock()
        atlas.mesh_from_structure.return_value=None
        with self.assertRaisesRegex(ValueError,'No mesh'):
            load_atlas_mesh(atlas,'ENT')
