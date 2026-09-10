import json
from pathlib import Path
import shutil
import tempfile
import unittest
import numpy as np
import pandas as pd
from allen_reference_painter.exporting import export_snapshot
from allen_reference_painter.export_validation import validate_active_roi_export, validate_metadata

class ExportTests(unittest.TestCase):
    def snapshot(self):
        vertices=np.array([[0.,0.,0.],[25.,0.,0.],[0.,25.,0.],[0.,0.,25.]])
        faces=np.array([[0,1,2],[0,1,3]])
        return dict(atlas='test_atlas',atlas_version='3.0-test',atlas_shape=(10,10,10),atlas_resolution_um=(25,25,25),paint_color='#ff3333',mirror_color='#00ffff',regions=[dict(area='TEST',name='test region',structure_id=1,color='#dddddd',visible=True,vertices=vertices,faces=faces,centroids=vertices[faces].mean(axis=1),painted_faces=[1])],cells=dict(dataframe=pd.DataFrame({'Name':['A','B']}),xyz=np.array([[1,2,3],[4,5,6]]),selection=np.array([True,False]),mode='microns',label='Name',color='(single color)'))

    def test_round_trip_after_moving_export(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            output=Path(export_snapshot(self.snapshot(),folder))
            moved=folder/'moved'
            shutil.move(output,moved)
            results=validate_active_roi_export(moved/'TEST_metadata.json')
            self.assertTrue(all(r.ok for r in results),[r.summary() for r in results])
            faces=pd.read_csv(moved/'TEST_painted_face_ids.csv')
            self.assertEqual(faces.face_id.tolist(),[1])
            np.testing.assert_allclose(faces[['center_x_um','center_y_um','center_z_um']],[[25/3,0,25/3]])
            cells=pd.read_csv(moved/'imported_cells_atlas_coordinates.csv')
            self.assertEqual(cells.app_selected.tolist(),[True,False])
            manifest=json.loads((moved/'scene_manifest.json').read_text())
            self.assertEqual(manifest['axis_order'],['AP','DV','ML'])
            self.assertEqual(manifest['selected_cell_count'],1)
            self.assertEqual(manifest['atlas_version'],'3.0-test')
            metadata=json.loads((moved/'TEST_metadata.json').read_text())
            self.assertEqual(metadata['atlas_version'],'3.0-test')
            self.assertEqual(len(metadata['mesh_geometry_sha256']),64)

    def test_same_second_exports_never_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            a=export_snapshot(self.snapshot(),folder,True)
            b=export_snapshot(self.snapshot(),folder,True)
            self.assertNotEqual(a,b)
            self.assertFalse((Path(a)/'imported_cells_atlas_coordinates.csv').exists())

    def test_partial_failure_is_not_published(self):
        with tempfile.TemporaryDirectory() as folder:
            bad=self.snapshot()
            bad['regions'][0]['painted_faces']=[100]
            with self.assertRaises(IndexError):
                export_snapshot(bad,folder)
            self.assertEqual(list(Path(folder).iterdir()),[])

    def test_nonfinite_atlas_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'metadata.json'
            path.write_text(json.dumps(dict(atlas='test',atlas_shape=[10,10,10],atlas_resolution_um=[float('nan'),25,25])))
            self.assertFalse(validate_metadata(path).ok)
