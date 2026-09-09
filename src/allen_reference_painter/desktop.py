"""Responsive desktop coordinator using the original atlas-coordinate contracts."""
from __future__ import annotations
from collections import OrderedDict
import logging
from pathlib import Path
import time
import numpy as np
import pyvista as pv
import trimesh
from qtpy import QtCore, QtWidgets
from qtpy.QtGui import QDesktopServices

from .app import MeshPainterWindow, RegionMesh, CellLayer, CELL_UNIT_OPTIONS, OUTPUT_DIR, hex_to_rgb01
from .app_modern import ModernMeshPainterWindow
from .cell_table import CellTableDialog
from .cells import convert_coordinates, read_cells
from .exporting import export_snapshot
from .jobs import Job
from .meshes import load_atlas_mesh
from .runtime import data_dir
from .spatial import FaceIndex
from .workspace_ui import build_workspace, STYLE
from .screenshot_legend_patch import _save_figure_with_heat_legend

log = logging.getLogger(__name__)

class PainterWindow(ModernMeshPainterWindow):
    def __init__(self, atlas, reference_mesh=None):
        self.cell_selection_mask = None
        self.visible_cell_indices = None
        self.cell_label_actor = None
        self._reference_mesh = reference_mesh
        self._face_indices = {}
        self._slice_cache = OrderedDict()
        self._slice_artists = {}
        self._jobs = {}
        self._undo_stack = []
        self._redo_stack = []
        self._stroke_before = None
        self._dirty = False
        self._paint_clock = 0.
        self._hover_clock = 0.
        self._plane_actors = {}
        self._marker_actors = {}
        self._color_cache = None
        self._color_cache_key = None
        self._selection_revision = 0
        self._scene_revision = 0
        self._is_demo = getattr(atlas, 'is_demo', False)
        MeshPainterWindow.__init__(self, atlas=atlas)
        self.setWindowTitle('Allen Reference Painter' + (' — DEMO · synthetic anatomy' if self._is_demo else ''))
        self.setMinimumSize(1080, 760)
        self.resize(1440, 980)
        self.setStyleSheet(STYLE)
        self._slice_timer = QtCore.QTimer(self)
        self._slice_timer.setSingleShot(True)
        self._slice_timer.setInterval(45)
        self._slice_timer.timeout.connect(self._flush_slices)
        self._set_mode('navigate')
        self._update_cell_colorbar()
        self._refresh_controls()
        self._connect_action_logs()
        self._update_status('Ready. Start by loading a region or importing a cell table.' + (' DEMO uses synthetic geometry, not the Allen atlas.' if self._is_demo else ''))

    def _connect_action_logs(self):
        # Log named control changes, not imported row values or hover text.
        for name, widget in vars(self).copy().items():
            if isinstance(widget, QtWidgets.QSlider):
                widget.valueChanged.connect(lambda value, n=name: log.info('ui.slider control=%s value=%s', n, value))
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.toggled.connect(lambda value, n=name: log.info('ui.toggle control=%s value=%s', n, value))
            elif isinstance(widget, QtWidgets.QPushButton):
                widget.clicked.connect(lambda _=False, n=name: log.info('ui.click control=%s', n))
            elif isinstance(widget, QtWidgets.QComboBox):
                widget.currentIndexChanged.connect(lambda value, n=name: log.info('ui.choice control=%s index=%s', n, value))

    def _build_ui(self):
        build_workspace(self)

    def _load_reference_brain_shell(self):
        self.plotter.set_background('#0b1020')
        if self._reference_mesh is not None:
            self.reference_actor = self.plotter.add_mesh(pv.wrap(self._reference_mesh), color='#b7c9e2', opacity=.08, pickable=False, name='reference_brain', reset_camera=False, render=False)
        self.plotter.add_axes(color='#b7c9e2')
        if self._is_demo:
            self.plotter.add_text('DEMO · Synthetic anatomy', position='upper_left', font_size=10, color='#7ce9d6')
        self.plotter.show_grid(color='#64748b', font_size=8, xlabel='AP (µm)', ylabel='DV (µm)', zlabel='ML (µm)')
        self.plotter.view_isometric()
        self.plotter.reset_camera()

    def _style_3d_scene_text(self):
        # Static scene decoration is installed once, never per brush/cell update.
        pass

    def _run_job(self, name, operation, callback):
        if name in self._jobs:
            self._update_status(f'{name} is already running.')
            return
        job = Job(operation, name, self)
        self._jobs[name] = (job, callback)
        job.succeeded.connect(self._job_result)
        job.failed.connect(self._job_error)
        job.finished.connect(self._job_finished)
        self._update_status(f'{name}… You can continue navigating.')
        job.start()

    @QtCore.Slot(object)
    def _job_result(self, result):
        job = self.sender()
        try:
            self._jobs[job.name][1](result)
        except Exception as exc:
            log.exception('job.result_failed operation=%s', job.name)
            self._error(str(exc))

    @QtCore.Slot(str)
    def _job_error(self, message):
        self._error(message)

    @QtCore.Slot()
    def _job_finished(self):
        job = self.sender()
        self._jobs.pop(job.name, None)
        job.deleteLater()
        self.load_region_button.setEnabled(True)
        self.load_cells_button.setEnabled(True)

    def _error(self, message):
        self._update_status(f'Could not complete action: {message}')
        QtWidgets.QMessageBox.warning(self, 'Action needs attention', message)

    def _load_selected_region(self):
        acronym = self._resolve_region_from_text(self.region_search.text())
        if acronym is None:
            acronym = self.region_picker.currentText().split(' - ', 1)[0]
        if not acronym:
            self._update_status('No matching region. Try an acronym such as ENT or CA1.')
            return
        if acronym in self.regions:
            self.active_combo.setCurrentText(acronym)
            self.tabs.setCurrentIndex(1)
            return
        self.load_region_button.setEnabled(False)
        def load():
            mesh = load_atlas_mesh(self.atlas, acronym)
            centers = np.asarray(mesh.triangles_center)
            return acronym, mesh, centers, FaceIndex(centers)
        self._run_job('Loading region', load, self._region_loaded)

    def _region_loaded(self, result):
        acronym, mesh, centers, index = result
        sid = self._structure_id(acronym)
        region = RegionMesh(acronym, self._structure_name(acronym), sid, self._descendant_ids(sid), mesh, pv.wrap(mesh), centers, self._structure_color(acronym))
        region.actor = self.plotter.add_mesh(region.pyvista_mesh, color=region.color, opacity=.6, show_edges=False, pickable=True, name=acronym, reset_camera=False, render=False)
        self.regions[acronym] = region
        self._face_indices[acronym] = index
        self.active_area = acronym
        self._scene_revision += 1
        self._dirty = True
        self._refresh_controls()
        self._refresh_scene()
        self.tabs.setCurrentIndex(1)
        self._update_status(f'{acronym} loaded · {len(centers):,} faces. Choose Paint to annotate.')

    def _refresh_controls(self):
        super()._refresh_controls()
        active = self.active_area in self.regions
        for b in (self.remove_region_button, self.clear_button, self.save_roi_button, self.paint_button, self.erase_button):
            b.setEnabled(active)
        self.undo_button.setEnabled(bool(self._undo_stack))
        self.redo_button.setEnabled(bool(self._redo_stack))

    def _remove_active_region(self):
        if self.active_area not in self.regions:
            return
        region = self.regions[self.active_area]
        if region.painted_faces and QtWidgets.QMessageBox.question(self, 'Remove painted region?', 'This removes its paint from the workspace. Export it first if you need to keep it.') != QtWidgets.QMessageBox.Yes:
            return
        self._face_indices.pop(self.active_area, None)
        self._undo_stack = [s for s in self._undo_stack if s[0] != self.active_area]
        self._redo_stack.clear()
        self._scene_revision += 1
        super()._remove_active_region()
        self._dirty = True
        if not self.regions:
            self._set_mode('navigate')

    def _set_mode(self, mode):
        self.paint_mode = mode
        for key, b in self.mode_buttons.items():
            b.setChecked(key == mode)
        self.mode_hint.setText('Navigate · Drag to rotate · Wheel to zoom' if mode == 'navigate' else f'{mode.title()} · Left click / drag · Right drag to zoom · Esc to navigate')
        self._update_status(f'Mode: {mode}')

    def _setup_picking(self):
        import vtk
        self.cell_picker = vtk.vtkCellPicker()
        self.cell_picker.SetTolerance(.0008)
        self.point_picker = vtk.vtkPointPicker()
        self.point_picker.SetTolerance(.03)
        self.point_picker.PickFromListOn()
        self._interaction_style = vtk.vtkInteractorStyleTrackballCamera()
        style = self._interaction_style
        style.SetDefaultRenderer(self.plotter.renderer)
        self.plotter.iren.interactor.SetInteractorStyle(style)
        def press(obj, event):
            if self.paint_mode == 'navigate':
                style.OnLeftButtonDown()
            self._on_left_press(obj, event)
        def release(obj, event):
            style.OnLeftButtonUp()
            self._on_left_release(obj, event)
        def move(obj, event):
            if not self.mouse_down:
                style.OnMouseMove()
            self._on_mouse_move(obj, event)
        style.AddObserver('LeftButtonPressEvent', press)
        style.AddObserver('LeftButtonReleaseEvent', release)
        style.AddObserver('MouseMoveEvent', move)

    def _on_left_press(self, obj, event):
        if self.paint_mode == 'navigate':
            self._show_nearest_cell_from_mouse(quiet=True)
            return
        if self.active_area not in self.regions or not self.regions[self.active_area].visible:
            return
        self.mouse_down = True
        self._stroke_before = (self.active_area, set(self.regions[self.active_area].painted_faces))
        self._paint_from_mouse()

    def _on_left_release(self, obj, event):
        self.mouse_down = False
        if self._stroke_before:
            area, before = self._stroke_before
            if area in self.regions:
                self._record_change(area, before, self.regions[area].painted_faces)
            self._stroke_before = None
        self._flush_slices()

    def _on_mouse_move(self, obj, event):
        now = time.perf_counter()
        if self.mouse_down and self.continuous_checkbox.isChecked():
            if now - self._paint_clock >= 1/60:
                self._paint_clock = now
                self._paint_from_mouse()
        elif now - self._hover_clock >= .08:
            self._hover_clock = now
            self._show_nearest_cell_from_mouse(quiet=True)

    def _paint_from_mouse(self):
        if self.active_area not in self.regions:
            return
        region = self.regions[self.active_area]
        if not region.visible:
            return
        self.cell_picker.InitializePickList()
        self.cell_picker.AddPickList(region.actor)
        self.cell_picker.PickFromListOn()
        super()._paint_from_mouse()

    def _face_ids_near_point(self, region, point):
        index = self._face_indices.get(region.acronym)
        if index is None:
            index = self._face_indices[region.acronym] = FaceIndex(region.face_centroids)
        return index.near(point, self.brush_slider.value())

    def _paint_at_points(self, points):
        started = time.perf_counter()
        region = self.regions[self.active_area]
        before = set(region.painted_faces)
        ids = set().union(*(self._face_ids_near_point(region, point) for point in points))
        if self.paint_mode == 'paint':
            region.painted_faces.update(ids)
        elif self.paint_mode == 'erase':
            region.painted_faces.difference_update(ids)
        if before != region.painted_faces:
            self._dirty = True
            self._update_painted_overlay(region)
            self._update_slice_views()
        self._update_pick_markers()
        self.plotter.render()
        self.status.showMessage(f'{region.acronym} · {len(region.painted_faces):,} painted faces · {self.paint_mode}')
        log.debug('paint.sample region=%s faces=%d elapsed_ms=%.2f', region.acronym, len(ids), (time.perf_counter()-started)*1000)

    def _record_change(self, area, before, after):
        added, removed = set(after)-before, before-set(after)
        if added or removed:
            self._undo_stack.append((area, added, removed))
            self._undo_stack = self._undo_stack[-100:]
            self._redo_stack.clear()
            self._dirty = True
            log.info('paint.stroke region=%s added=%d removed=%d', area, len(added), len(removed))
            self._refresh_controls()

    def _undo(self):
        self._history(self._undo_stack, self._redo_stack, True)

    def _redo(self):
        self._history(self._redo_stack, self._undo_stack, False)

    def _history(self, source, target, undo):
        if not source:
            return
        area, added, removed = source.pop()
        if area not in self.regions:
            return
        region = self.regions[area]
        region.painted_faces.difference_update(added if undo else removed)
        region.painted_faces.update(removed if undo else added)
        target.append((area, added, removed))
        self._update_painted_overlay(region)
        self._refresh_controls()
        self._update_slice_views()
        self.plotter.render()
        self._dirty = True
        self._update_status(f'{"Undo" if undo else "Redo"} · {area}')

    def _clear_active_paint(self):
        if self.active_area in self.regions:
            region = self.regions[self.active_area]
            before = set(region.painted_faces)
            region.painted_faces.clear()
            self._record_change(region.acronym, before, region.painted_faces)
            self._update_painted_overlay(region)
            self._update_slice_views()
            self.plotter.render()

    def _update_painted_overlay(self, region):
        # Keep one actor/mapper; replace only its selected triangle connectivity.
        if not region.painted_faces:
            if region.painted_actor is not None:
                region.painted_actor.SetVisibility(False)
            return
        faces = region.trimesh_mesh.faces[sorted(region.painted_faces)]
        connectivity = np.column_stack((np.full(len(faces), 3), faces)).ravel()
        overlay = pv.PolyData(region.trimesh_mesh.vertices, connectivity, deep=False)
        if region.painted_actor is None:
            region.painted_actor = self.plotter.add_mesh(overlay, color=self.paint_color, opacity=self.paint_opacity_slider.value()/100, pickable=False, name=f'painted_{region.acronym}', reset_camera=False, render=False)
        else:
            region.painted_actor.mapper.SetInputData(overlay)
        region.painted_actor.SetVisibility(region.visible)
        region.painted_actor.GetProperty().SetColor(*hex_to_rgb01(self.paint_color))
        region.painted_actor.GetProperty().SetOpacity(self.paint_opacity_slider.value()/100)

    def _refresh_scene(self):
        if not hasattr(self, 'plotter'):
            return
        if self.reference_actor is not None:
            self.reference_actor.SetVisibility(self.reference_checkbox.isChecked())
            self.reference_actor.GetProperty().SetOpacity(self.brain_opacity_slider.value()/100)
        for area, region in self.regions.items():
            region.actor.SetVisibility(region.visible)
            region.actor.GetProperty().SetColor(*hex_to_rgb01(region.color))
            region.actor.GetProperty().SetOpacity(self._mesh_opacity(area))
            if region.painted_actor is not None:
                region.painted_actor.SetVisibility(region.visible and bool(region.painted_faces))
                region.painted_actor.GetProperty().SetColor(*hex_to_rgb01(self.paint_color))
                region.painted_actor.GetProperty().SetOpacity(self.paint_opacity_slider.value()/100)
        self.plotter.render()
        self._update_slice_views()

    def _update_pick_markers(self):
        if not hasattr(self, 'plotter'):
            return
        for name, point, color in [('last_pick', self.last_picked_point, '#ffd400'), ('last_mirror', self.last_mirror_point if self.symmetry_checkbox.isChecked() else None, self.mirror_color)]:
            actor = self._marker_actors.get(name)
            if point is not None:
                if actor is None:
                    actor = self.plotter.add_mesh(pv.Sphere(radius=1), color=color, pickable=False, name=name, reset_camera=False, render=False)
                    self._marker_actors[name] = actor
                actor.SetPosition(*point)
                actor.SetScale(self.brush_slider.value())
                actor.GetProperty().SetColor(*hex_to_rgb01(color))
                actor.GetProperty().SetOpacity(.35)
            if actor is not None:
                actor.SetVisibility(point is not None)
        self.plotter.render()

    def _update_slice_planes(self):
        if not hasattr(self, 'plotter'):
            return
        for plane, axis, direction, color in [('coronal',0,(1,0,0),'#ffd400'), ('sagittal',2,(0,0,1),'#00d7ff')]:
            enabled = getattr(self, f'show_{plane}_plane_checkbox').isChecked()
            actor = self._plane_actors.get(plane)
            center = np.asarray(self.size_um)/2
            center[axis] = self._index_to_um(getattr(self, f'{plane}_slider').value(), axis)
            if enabled and actor is None:
                mesh = pv.Plane(center=(0,0,0), direction=direction, i_size=self.size_um[2 if axis==0 else 0], j_size=self.size_um[1])
                actor = self.plotter.add_mesh(mesh, color=color, pickable=False, name=f'{plane}_slice_plane', reset_camera=False, render=False)
                self._plane_actors[plane] = actor
            if actor is not None:
                actor.SetVisibility(enabled)
                actor.SetPosition(*center)
                actor.GetProperty().SetOpacity(self.plane_opacity_slider.value()/100)
        self.plotter.render()

    def _on_slice_changed(self, *args):
        self._update_slice_views()
        self._update_slice_planes()

    def _update_slice_views(self):
        if hasattr(self, '_slice_timer'):
            # Coalesce a burst without starving updates during continuous movement.
            if not self._slice_timer.isActive():
                self._slice_timer.start()
        elif hasattr(self, 'coronal_fig'):
            self._flush_slices()

    def _flush_slices(self):
        if hasattr(self, '_slice_timer'):
            self._slice_timer.stop()
        if not hasattr(self, 'coronal_fig'):
            return
        for plane, axis in [('coronal',0),('sagittal',2)]:
            self._draw_slice(plane,axis)

    def _draw_slice(self, plane, axis):
        index = getattr(self, f'{plane}_slider').value()
        coord = self._index_to_um(index, axis)
        getattr(self, f'{plane}_label').setText(f'{plane.title()} · {"AP" if axis==0 else "ML"} {coord:,.0f} µm · slice {index}')
        style_key = tuple((r.acronym,r.visible,r.color) for r in self.regions.values())
        key = (plane,index,style_key)
        rgb = self._slice_cache.get(key)
        if rgb is None:
            ann = self.annotation[index,:,:] if axis==0 else self.annotation[:,:,index]
            rgb = self._annotation_rgb(ann)
            if axis==2:
                rgb = rgb.transpose(1,0,2)
            self._slice_cache[key] = rgb
            while len(self._slice_cache)>24:
                self._slice_cache.popitem(last=False)
        else:
            self._slice_cache.move_to_end(key)
        fig = getattr(self,f'{plane}_fig')
        artists = self._slice_artists.get(plane)
        if artists is None:
            fig.patch.set_facecolor('#0b1020')
            ax = fig.add_subplot(111)
            extent = [0,self.size_um[2 if axis==0 else 0],self.size_um[1],0]
            im = ax.imshow(rgb,extent=extent,origin='upper',interpolation='nearest')
            ax.set_xlabel('ML (µm)' if axis==0 else 'AP (µm)',fontsize=8)
            ax.set_ylabel('DV (µm)',fontsize=8)
            self._style_slice_axes(ax)
            fig.subplots_adjust(left=.19,right=.98,top=.96,bottom=.20)
            self._slice_artists[plane] = (ax,im,key)
        else:
            ax,im,previous = artists
            if previous != key:
                im.set_data(rgb)
            for collection in list(ax.collections):
                collection.remove()
            self._slice_artists[plane] = (ax,im,key)
        self._overlay_points(ax,plane,coord)
        getattr(self,f'{plane}_canvas').draw_idle()

    def _heatmap_changed(self):
        self._update_cell_colorbar()
        self._update_slice_views()

    def _cell_color_values(self, idx):
        key = (id(self.cell_layer), self._selection_revision, self.cell_colorby_combo.currentText())
        if key != self._color_cache_key:
            self._color_cache = super()._cell_color_values(idx)
            self._color_cache_key = key
        return self._color_cache

    def _resize_cells(self):
        if self.cell_layer is not None and self.cell_layer.actor is not None:
            self.cell_layer.actor.GetProperty().SetPointSize(self.cell_size_slider.value())
            self.plotter.render()

    def _refresh_cell_actor(self, update_existing_only=False):
        if update_existing_only:
            self._resize_cells()
            return
        self._color_cache_key = None
        # A cell actor rebuild is allowed only when the data/selection/color changes.
        super()._refresh_cell_actor(False)
        self.plotter.render()

    def _cell_metadata_options_changed(self, *args):
        self._color_cache_key = None
        if self.cell_layer is not None:
            self.cell_layer.label_column = self.cell_label_combo.currentText()
            self.cell_layer.color_column = self.cell_colorby_combo.currentText()
            self._refresh_cell_actor(False)
            self._dirty = True

    def _show_cell_table_dialog(self):
        if self.cell_layer is None:
            return
        dialog = CellTableDialog(self.cell_layer.dataframe, self.cell_selection_mask, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.cell_selection_mask = dialog.selection_mask.copy()
            self._selection_revision += 1
            self._refresh_cell_actor(False)
            self._dirty = True
            self._update_status(f'{self.cell_selection_mask.sum():,} of {len(self.cell_selection_mask):,} cells visible.')

    def _resolve_units(self):
        mode = self._selected_cell_unit_code()
        if mode == 'auto':
            labels = list(CELL_UNIT_OPTIONS)[:3]
            label, ok = QtWidgets.QInputDialog.getItem(self,'Confirm coordinate units','Small values are ambiguous. What units did the source export?',labels,0,False)
            if not ok:
                return None
            self.cell_units_combo.blockSignals(True)
            self.cell_units_combo.setCurrentText(label)
            self.cell_units_combo.blockSignals(False)
            mode = CELL_UNIT_OPTIONS[label]
        return mode

    def _convert_cell_coordinates(self, xyz):
        mode = self._resolve_units()
        if mode is None:
            raise ValueError('Coordinate conversion cancelled.')
        return convert_coordinates(xyz,mode,self.resolution_um,self.shape)

    def _load_cells_dialog(self):
        mode = self._resolve_units()
        if mode is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self,'Import cell coordinates',str(Path.home()),'Cell tables (*.csv *.tsv *.txt *.xlsx *.xls)')
        if not path:
            return
        resolution, shape = self.resolution_um, self.shape
        def load():
            frame, original = read_cells(path)
            xyz, description = convert_coordinates(original,mode,resolution,shape)
            return path,frame,original,xyz,description,mode
        self.load_cells_button.setEnabled(False)
        self._run_job('Importing cells',load,self._cells_loaded)

    def _cells_loaded(self, result):
        path,frame,original,xyz,description,mode = result
        outside = int(np.any((xyz<0)|(xyz>=np.asarray(self.size_um)),axis=1).sum())
        if outside and QtWidgets.QMessageBox.question(self,'Check coordinate units',f'{outside:,} of {len(xyz):,} cells lie outside the atlas. Import anyway? Check units and coordinate origin if unexpected.') != QtWidgets.QMessageBox.Yes:
            return
        self._clear_cells()
        self.cell_units_combo.blockSignals(True)
        self.cell_units_combo.setCurrentText(next(label for label,code in CELL_UNIT_OPTIONS.items() if code==mode))
        self.cell_units_combo.blockSignals(False)
        self.cell_layer = CellLayer(path,frame,original,xyz,description)
        self.cell_selection_mask = np.ones(len(frame),dtype=bool)
        self._selection_revision += 1
        self._populate_cell_metadata_controls(frame)
        self._refresh_cell_actor(False)
        self._center_view_on_cells()
        self.view_cell_table_button.setEnabled(True)
        self.cell_summary.setText(f'{len(frame):,} cells · {Path(path).name}\n{description}\n{outside:,} outside atlas bounds')
        self._dirty = True
        self._update_status(f'Imported {len(frame):,} cells · {description}')

    def _apply_cell_units_to_loaded_cells(self, *args):
        if self.cell_layer is None:
            return
        mode = self._resolve_units()
        if mode is None:
            return
        xyz, description = convert_coordinates(self.cell_layer.original_xyz,mode,self.resolution_um,self.shape)
        outside = int(np.any((xyz<0)|(xyz>=np.asarray(self.size_um)),axis=1).sum())
        if outside and QtWidgets.QMessageBox.question(self,'Check coordinate units',f'{outside:,} cells will lie outside the atlas. Apply these units?') != QtWidgets.QMessageBox.Yes:
            return
        self.cell_layer.xyz, self.cell_layer.coordinate_mode = xyz,description
        self._refresh_cell_actor(False)
        self._center_view_on_cells()
        self.cell_summary.setText(f'{len(xyz):,} cells · {description}\n{outside:,} outside atlas bounds')
        self._dirty = True
        self._update_status(f'Applied units: {description}; selection preserved.')

    def _clear_cells(self):
        self._selection_revision += 1
        self._color_cache_key = None
        super()._clear_cells()
        self.point_picker.InitializePickList()
        self.point_picker.PickFromListOn()
        self.cell_summary.setText('No cells loaded.')
        self._dirty = True

    def _show_nearest_cell_from_mouse(self, max_distance_um=500, quiet=False):
        if self.cell_layer is None or self.cell_layer.actor is None:
            return
        x,y = self.plotter.iren.interactor.GetEventPosition()
        if self.point_picker.Pick(x,y,0,self.plotter.renderer):
            point_id = int(self.point_picker.GetPointId())
            if self.visible_cell_indices is not None and 0 <= point_id < len(self.visible_cell_indices):
                # Hover is ephemeral; never log imported cell metadata.
                self.status.showMessage(self._cell_status_text(point_id))

    def _snapshot(self, active_only=False):
        regions = [self.regions[self.active_area]] if active_only else list(self.regions.values())
        snapshot = dict(atlas='synthetic_demo' if self._is_demo else 'allen_mouse_25um', atlas_resolution_um=self.resolution_um,atlas_shape=self.shape,paint_color=self.paint_color,mirror_color=self.mirror_color,regions=[],cells=None)
        for r in regions:
            snapshot['regions'].append(dict(area=r.acronym,name=r.name,structure_id=r.structure_id,color=r.color,visible=r.visible,vertices=np.asarray(r.trimesh_mesh.vertices).copy(),faces=np.asarray(r.trimesh_mesh.faces).copy(),centroids=r.face_centroids.copy(),painted_faces=sorted(r.painted_faces)))
        if self.cell_layer is not None:
            snapshot['cells'] = dict(dataframe=self.cell_layer.dataframe.copy(deep=True),xyz=self.cell_layer.xyz.copy(),selection=self.cell_selection_mask.copy(),mode=self.cell_layer.coordinate_mode,label=self.cell_label_combo.currentText(),color=self.cell_colorby_combo.currentText())
        return snapshot

    def _export(self, active_only):
        if active_only and (self.active_area not in self.regions or not self.regions[self.active_area].painted_faces):
            self._update_status('Paint a region before exporting an ROI.')
            return
        if not self.regions and self.cell_layer is None:
            self._update_status('Load a region or cells before exporting a scene.')
            return
        folder = QtWidgets.QFileDialog.getExistingDirectory(self,'Choose export destination',str(OUTPUT_DIR))
        if not folder:
            return
        snapshot = self._snapshot(active_only)
        self._run_job('Exporting ROI' if active_only else 'Exporting scene',lambda:export_snapshot(snapshot,folder,active_only),lambda path:self._update_status(f'Export complete: {path}'))

    def _save_active_roi(self):
        self._export(True)

    def _save_scene_outputs(self):
        self._export(False)

    def _screenshot_path(self, stem):
        from datetime import datetime
        return str(OUTPUT_DIR / f'{stem}_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.png')

    def _save_coronal_screenshot(self):
        self._flush_slices()
        self._update_cell_colorbar()
        path = _save_figure_with_heat_legend(self,self.coronal_fig,'coronal_with_legend')
        self._update_status(f'Saved coronal screenshot: {path}')
        return path

    def _save_sagittal_screenshot(self):
        self._flush_slices()
        self._update_cell_colorbar()
        path = _save_figure_with_heat_legend(self,self.sagittal_fig,'sagittal_with_legend')
        self._update_status(f'Saved sagittal screenshot: {path}')
        return path

    def _open_outputs(self):
        QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(OUTPUT_DIR)))

    def _open_logs(self):
        QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(data_dir()/'logs')))

    def _show_guide(self):
        QtWidgets.QMessageBox.information(self,'Quick guide','1  REGIONS — Search a name or acronym, then load a mesh.\n\n2  PAINT — Choose Paint or Erase. Click / drag on the active mesh. Navigate rotates safely; Esc returns to Navigate. Undo: Ctrl+Z.\n\n3  CELLS — Choose source units, import a table, then choose labels, colors, and visible rows. X/AP, Y/DV, Z/ML are measured from the BrainGlobe atlas origin.\n\n4  EXPORT — Save meshes, face IDs, centroid coordinates and metadata. Screenshots include current selections.\n\nROI painting selects surface faces; it does not create a volumetric segmentation. Exports are analysis outputs, not reloadable projects.')

    def _update_status(self, text):
        self.status.showMessage(text)
        log.info('status %s',text)

    def closeEvent(self,event):
        if self._jobs:
            QtWidgets.QMessageBox.information(self,'Operation in progress','Please let the current load or export finish before closing.')
            event.ignore()
            return
        if self._dirty and QtWidgets.QMessageBox.question(self,'Close workspace?','Workspace changes are not saved as a project. Export any ROI or scene you need before closing. Close now?',QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No,QtWidgets.QMessageBox.No) != QtWidgets.QMessageBox.Yes:
            event.ignore()
            return
        log.info('session.close')
        self._slice_timer.stop()
        self.plotter.close()
        event.accept()
