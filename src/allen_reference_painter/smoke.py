"""Offline functional smoke gate for both source and frozen desktop builds."""
from pathlib import Path
import json
import tempfile
import numpy as np
import pandas as pd
import trimesh
from qtpy import QtCore, QtWidgets
from .spatial import FaceIndex
from .cells import convert_coordinates
from .cell_table import CellTableModel
from .exporting import export_snapshot
from .export_validation import validate_active_roi_export


def exercise_window(window, destination=None):
    folder = Path(destination or tempfile.mkdtemp(prefix='allen-painter-smoke-'))
    folder.mkdir(parents=True,exist_ok=True)
    app = QtWidgets.QApplication.instance()
    mesh = trimesh.load(window.atlas.meshfile_from_structure('DEMO'),force='mesh')
    centers = np.asarray(mesh.triangles_center)
    window._region_loaded(('DEMO',mesh,centers,FaceIndex(centers)))
    window._set_mode('paint')
    region = window.regions['DEMO']
    point = centers[len(centers)//3]
    mirror = point.copy()
    mirror[2] = 2*window.midline_z_um-mirror[2]
    window.symmetry_checkbox.setChecked(True)
    camera = tuple(tuple(v) for v in window.plotter.camera_position)
    before = set(region.painted_faces)
    window._paint_at_points([point,mirror])
    window._record_change('DEMO',before,region.painted_faces)
    painted = set(region.painted_faces)
    assert painted, 'Paint produced no faces'
    actor = region.painted_actor
    assert camera == tuple(tuple(v) for v in window.plotter.camera_position), 'Paint moved the camera'
    window._undo()
    assert not region.painted_faces
    window._redo()
    assert region.painted_faces == painted
    assert region.painted_actor is actor, 'Paint rebuilt its actor'
    window._set_mode('erase')
    window._paint_at_points([point])
    assert len(region.painted_faces)<len(painted)
    region.painted_faces = painted
    window._update_painted_overlay(region)
    window._clear_active_paint()
    assert not region.painted_faces
    window._undo()
    assert region.painted_faces==painted
    frame = pd.DataFrame({'Name':['cell A','cell B','cell C'],'Tau':[1.,5.,10.], 'x':[1.2,1.25,1.3],'y':[.9,.95,1.],'z':[1.,1.05,1.1]})
    xyz,description = convert_coordinates(frame[['x','y','z']].to_numpy(),'mm',window.resolution_um,window.shape)
    window._cells_loaded(('synthetic.csv',frame,frame[['x','y','z']].to_numpy(),xyz,description,'mm'))
    window.cell_colorby_combo.setCurrentText('Tau')
    window.cell_selection_mask = np.array([True,False,True])
    window._selection_revision += 1
    window._refresh_cell_actor(False)
    assert window.visible_cell_indices.tolist()==[0,2]
    cell_actor = window.cell_layer.actor
    window.brain_opacity_slider.setValue(12)
    assert window.cell_layer.actor is cell_actor, 'Opacity recreated cell geometry'
    window._apply_cell_units_to_loaded_cells()
    assert window.cell_selection_mask.tolist()==[True,False,True]
    model = CellTableModel(frame,window.cell_selection_mask)
    model.filter('cell B')
    model.select_filtered(True)
    assert model.selection.all()
    window.coronal_slider.setValue(48)
    window.sagittal_slider.setValue(40)
    window._flush_slices()
    axes = window.coronal_fig.axes[0]
    window.coronal_slider.setValue(49)
    window._flush_slices()
    assert window.coronal_fig.axes[0] is axes, 'Slice update rebuilt axes'
    window._set_mode('navigate')
    app.processEvents()
    window.grab().save(str(folder/'workspace.png'))
    window.plotter.screenshot(str(folder/'scene.png'))
    coronal = window._save_coronal_screenshot()
    sagittal = window._save_sagittal_screenshot()
    assert Path(coronal).stat().st_size>1000
    assert Path(sagittal).stat().st_size>1000
    export = Path(export_snapshot(window._snapshot(),folder))
    results = validate_active_roi_export(export/'DEMO_metadata.json')
    assert all(r.ok for r in results), [r.summary() for r in results]
    cells = pd.read_csv(export/'imported_cells_atlas_coordinates.csv')
    np.testing.assert_allclose(cells[['app_x_um','app_y_um','app_z_um']],xyz)
    assert cells['app_selected'].tolist()==[True,False,True]
    manifest = json.loads((export/'scene_manifest.json').read_text())
    assert manifest['atlas']=='synthetic_demo'
    window._clear_cells()
    assert window.cell_layer is None
    window._dirty = False
    (folder/'smoke-result.json').write_text(json.dumps({'status':'PASS','checks':['launch','region load','paint and symmetry','erase','undo/redo','camera preservation','actor reuse','cell units','cell selection','numeric heatmaps','slice axes reuse','PNG screenshots','portable ROI validation','cell export coordinates','clear cells'],'atlas':'synthetic_demo'},indent=2))
    return folder
