import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from allen_reference_painter.cells import convert_coordinates, read_cells
from allen_reference_painter.spatial import FaceIndex

class SpatialTests(unittest.TestCase):
    def test_index_matches_original_face_search(self):
        rng = np.random.default_rng(42)
        centers = rng.uniform(0,1000,(20000,3))
        index = FaceIndex(centers)
        for point in rng.uniform(-100,1100,(30,3)):
            distances = np.linalg.norm(centers-point,axis=1)
            for radius in (1,25,150,800):
                expected = set(np.flatnonzero(distances<=radius)) or {int(np.argmin(distances))}
                self.assertEqual(index.near(point,radius),expected)

    def test_nearest_ties_and_empty_mesh(self):
        self.assertEqual(FaceIndex([[0,0,0],[0,0,0]]).near([1,0,0],.1),{0})
        with self.assertRaises(ValueError):
            FaceIndex(np.empty((0,3)))

class CoordinateTests(unittest.TestCase):
    def test_explicit_units_and_anisotropic_voxels(self):
        xyz = np.array([[9.2532,5.7411,1.4887]])
        for mode,factor in [('um',1),('mm',1000),('voxel',np.array([10,25,50]))]:
            out,_ = convert_coordinates(xyz,mode,(10,25,50),(528,320,456))
            np.testing.assert_allclose(out,xyz*factor)
        np.testing.assert_allclose(xyz,[[9.2532,5.7411,1.4887]])

    def test_ambiguous_auto_requires_explicit_units(self):
        with self.assertRaisesRegex(ValueError,'explicitly'):
            convert_coordinates([[9,5,1]],'auto',(25,25,25),(528,320,456))

    def test_invalid_coordinates_are_rejected(self):
        with self.assertRaises(ValueError):
            convert_coordinates([[float('nan'),1,2]],'um',(25,25,25),(10,10,10))

    def test_import_aliases_metadata_and_invalid_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'cells.tsv'
            path.write_text('Name\t AP \tDV\tML\nA\t1\t2\t3\n')
            frame,xyz = read_cells(path)
            self.assertEqual(frame.Name.tolist(),['A'])
            np.testing.assert_array_equal(xyz,[[1,2,3]])
            path.write_text('x\ty\tz\n1\tbad\t3\n')
            with self.assertRaisesRegex(ValueError,'1 rows'):
                read_cells(path)

if __name__=='__main__':
    unittest.main()
