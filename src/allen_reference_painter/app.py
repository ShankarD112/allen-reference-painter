"""
Allen Reference Painter - Python/Qt desktop prototype.

This is the first repo version of the app. It keeps the same overall idea as the
local prototype: BrainGlobe Allen 25um atlas -> trimesh/PyVista meshes -> Qt GUI
for viewing, painting, importing cell coordinates, and saving atlas-coordinate
outputs.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Set

import numpy as np
import pandas as pd
import pyvista as pv
import trimesh
import vtk
from brainglobe_atlasapi.bg_atlas import BrainGlobeAtlas
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from pyvistaqt import QtInteractor
from qtpy import QtCore, QtWidgets
from qtpy.QtGui import QColor

PROJECT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_DIR / "outputs"
PROJECTS_DIR = PROJECT_DIR / "projects"
OUTPUT_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)

ATLAS_NAME = "allen_mouse_25um"
STARTER_AREAS = ["ENT", "PAR", "POST", "PRE", "SUB", "ProS", "HATA", "APr", "PERI", "ECT"]
DEFAULT_PAINT_COLOR = "#ff3333"
DEFAULT_CELL_COLOR = "#00d7ff"
DEFAULT_REGION_COLOR = "#dddddd"

FALLBACK_REGION_COLORS = {
    "ENT": "#c8c5ff",
    "PAR": "#d4ffff",
    "POST": "#e8fbff",
    "PRE": "#eef8ff",
    "SUB": "#f2f4ff",
    "ProS": "#f3f1fb",
    "HATA": "#edfafa",
    "APr": "#f0fbff",
    "PERI": "#f5d8f7",
    "ECT": "#f2faf8",
}


def hex_to_rgb01(hex_color: str) -> tuple[float, float, float]:
    color = QColor(hex_color)
    return color.redF(), color.greenF(), color.blueF()


def hex_to_rgb255(hex_color: str) -> np.ndarray:
    color = QColor(hex_color)
    return np.array([color.red(), color.green(), color.blue()], dtype=np.uint8)


def rgb_triplet_to_hex(value) -> str | None:
    if value is None:
        return None
    try:
        rgb = [max(0, min(255, int(x))) for x in value]
        if len(rgb) != 3:
            return None
        return "#{:02x}{:02x}{:02x}".format(*rgb)
    except Exception:
        return None


@dataclass
class RegionMesh:
    acronym: str
    name: str
    structure_id: int | None
    descendant_ids: Set[int]
    trimesh_mesh: trimesh.Trimesh
    pyvista_mesh: pv.PolyData
    face_centroids: np.ndarray
    color: str
    actor: object | None = None
    painted_actor: object | None = None
    visible: bool = True
    painted_faces: Set[int] = field(default_factory=set)


@dataclass
class CellLayer:
    path: str
    dataframe: pd.DataFrame
    xyz: np.ndarray
    color: str = DEFAULT_CELL_COLOR
    actor: object | None = None


class MeshPainterWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Allen Reference Painter")
        self.resize(2000, 1100)

        self.atlas = BrainGlobeAtlas(ATLAS_NAME)
        self.annotation = np.asarray(self.atlas.annotation)
        self.resolution_um = tuple(float(x) for x in self.atlas.resolution)
        self.shape = self.annotation.shape
        self.size_um = tuple(self.shape[i] * self.resolution_um[i] for i in range(3))
        self.midline_z_um = self.size_um[2] / 2.0

        self.regions: Dict[str, RegionMesh] = {}
        self.active_area: str | None = None
        self.paint_mode = "paint"
        self.paint_color = DEFAULT_PAINT_COLOR
        self.cell_layer: CellLayer | None = None
        self.mouse_down = False
        self.last_picked_point: np.ndarray | None = None
        self.last_mirror_point: np.ndarray | None = None
        self.reference_actor = None

        self.structure_index = self._build_structure_index()
        self.all_region_labels = self._all_region_labels()

        self._build_ui()
        self._load_reference_brain_shell()
        for area in STARTER_AREAS:
            self._load_region(area, make_active=False, quiet=True)
        if self.regions:
            self.active_area = next(iter(self.regions))
        self._refresh_controls()
        self._setup_picking()
        self._reset_slices_to_active_region()
        self._update_slice_views()
        self._update_status("Ready. Load a region/subregion, choose active region, then paint.")

    # ---------- atlas helpers ----------
    def _build_structure_index(self) -> dict[str, dict]:
        out = {}
        for sid, info in self.atlas.structures.items():
            acronym = str(info.get("acronym", "")).strip()
            if acronym:
                out[acronym] = {
                    "id": int(sid),
                    "name": str(info.get("name", acronym)),
                    "color": rgb_triplet_to_hex(info.get("rgb_triplet"))
                    or FALLBACK_REGION_COLORS.get(acronym, DEFAULT_REGION_COLOR),
                }
        return out

    def _all_region_labels(self) -> list[str]:
        labels = []
        for acronym, info in sorted(self.structure_index.items(), key=lambda x: x[0].lower()):
            labels.append(f"{acronym} - {info['name']}")
        return labels

    def _structure_id(self, acronym: str) -> int | None:
        return self.structure_index.get(acronym, {}).get("id")

    def _structure_name(self, acronym: str) -> str:
        return self.structure_index.get(acronym, {}).get("name", acronym)

    def _structure_color(self, acronym: str) -> str:
        return self.structure_index.get(acronym, {}).get("color", DEFAULT_REGION_COLOR)

    def _descendant_ids(self, structure_id: int | None) -> Set[int]:
        if structure_id is None:
            return set()
        ids = set()
        for sid, info in self.atlas.structures.items():
            path = info.get("structure_id_path", []) or info.get("id_path", []) or []
            try:
                path = [int(x) for x in path]
            except Exception:
                path = []
            if int(sid) == structure_id or structure_id in path:
                ids.add(int(sid))
        return ids

    # ---------- UI ----------
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)

        side = QtWidgets.QWidget()
        side.setFixedWidth(430)
        side_layout = QtWidgets.QVBoxLayout(side)
        title = QtWidgets.QLabel("Allen Reference Painter")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        side_layout.addWidget(title)

        self.reference_checkbox = QtWidgets.QCheckBox("Show transparent reference brain shell")
        self.reference_checkbox.setChecked(True)
        self.reference_checkbox.stateChanged.connect(lambda _: self._refresh_scene())
        side_layout.addWidget(self.reference_checkbox)

        side_layout.addWidget(QtWidgets.QLabel("Reference brain opacity"))
        self.brain_opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.brain_opacity_slider.setMinimum(0)
        self.brain_opacity_slider.setMaximum(100)
        self.brain_opacity_slider.setValue(10)
        self.brain_opacity_slider.valueChanged.connect(lambda _: self._refresh_scene())
        side_layout.addWidget(self.brain_opacity_slider)

        side_layout.addWidget(QtWidgets.QLabel("Search/load Allen region or subregion"))
        self.region_search = QtWidgets.QLineEdit()
        self.region_search.setPlaceholderText("Search acronym/name, e.g. ENT, SUB, CA1")
        self.region_search.textChanged.connect(self._filter_region_picker)
        side_layout.addWidget(self.region_search)
        self.region_picker = QtWidgets.QComboBox()
        side_layout.addWidget(self.region_picker)
        self.load_region_button = QtWidgets.QPushButton("Load selected region")
        self.load_region_button.clicked.connect(self._load_selected_region)
        side_layout.addWidget(self.load_region_button)

        side_layout.addWidget(QtWidgets.QLabel("Active region to paint"))
        self.active_combo = QtWidgets.QComboBox()
        self.active_combo.currentTextChanged.connect(self._set_active_area)
        side_layout.addWidget(self.active_combo)

        self.mode_button = QtWidgets.QPushButton("Mode: paint")
        self.mode_button.clicked.connect(self._toggle_mode)
        side_layout.addWidget(self.mode_button)

        self.continuous_checkbox = QtWidgets.QCheckBox("Continuous paint while dragging")
        self.continuous_checkbox.setChecked(True)
        side_layout.addWidget(self.continuous_checkbox)

        self.symmetry_checkbox = QtWidgets.QCheckBox("Symmetric mirror painting across midline")
        self.symmetry_checkbox.setChecked(False)
        side_layout.addWidget(self.symmetry_checkbox)

        self.sync_slice_checkbox = QtWidgets.QCheckBox("3D click updates slice positions")
        self.sync_slice_checkbox.setChecked(True)
        side_layout.addWidget(self.sync_slice_checkbox)

        self.paint_color_button = QtWidgets.QPushButton(self.paint_color)
        self.paint_color_button.setStyleSheet(f"background-color: {self.paint_color}; color: black;")
        self.paint_color_button.clicked.connect(self._choose_paint_color)
        side_layout.addWidget(QtWidgets.QLabel("Paint color"))
        side_layout.addWidget(self.paint_color_button)

        side_layout.addWidget(QtWidgets.QLabel("Brush radius, um"))
        self.brush_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.brush_slider.setMinimum(25)
        self.brush_slider.setMaximum(800)
        self.brush_slider.setValue(150)
        side_layout.addWidget(self.brush_slider)

        self.active_opacity_slider = self._add_slider(side_layout, "Active mesh opacity", 5, 100, 60)
        self.reference_opacity_slider = self._add_slider(side_layout, "Other loaded mesh opacity", 0, 100, 30)
        self.paint_opacity_slider = self._add_slider(side_layout, "Paint overlay opacity", 10, 100, 90)
        self.slice_thickness_slider = self._add_slider(side_layout, "2D overlay thickness, um", 25, 500, 100)
        self.slice_thickness_slider.valueChanged.connect(lambda _: self._update_slice_views())

        self.show_painted_2d_checkbox = QtWidgets.QCheckBox("Show painted ROI on slices")
        self.show_painted_2d_checkbox.setChecked(True)
        self.show_painted_2d_checkbox.stateChanged.connect(lambda _: self._update_slice_views())
        side_layout.addWidget(self.show_painted_2d_checkbox)

        self.show_cells_2d_checkbox = QtWidgets.QCheckBox("Show imported cells on slices")
        self.show_cells_2d_checkbox.setChecked(True)
        self.show_cells_2d_checkbox.stateChanged.connect(lambda _: self._update_slice_views())
        side_layout.addWidget(self.show_cells_2d_checkbox)

        self.load_cells_button = QtWidgets.QPushButton("Load cells CSV/TSV/XLSX")
        self.load_cells_button.clicked.connect(self._load_cells_dialog)
        side_layout.addWidget(self.load_cells_button)

        self.clear_cells_button = QtWidgets.QPushButton("Clear cells")
        self.clear_cells_button.clicked.connect(self._clear_cells)
        side_layout.addWidget(self.clear_cells_button)

        self.region_table = QtWidgets.QTableWidget()
        self.region_table.setColumnCount(4)
        self.region_table.setHorizontalHeaderLabels(["Show", "Area", "Name", "Color"])
        self.region_table.verticalHeader().setVisible(False)
        side_layout.addWidget(self.region_table, stretch=1)

        button_grid = QtWidgets.QGridLayout()
        self.clear_button = QtWidgets.QPushButton("Clear active paint")
        self.clear_button.clicked.connect(self._clear_active_paint)
        button_grid.addWidget(self.clear_button, 0, 0)
        self.save_roi_button = QtWidgets.QPushButton("Save active ROI")
        self.save_roi_button.clicked.connect(self._save_active_roi)
        button_grid.addWidget(self.save_roi_button, 0, 1)
        self.save_scene_button = QtWidgets.QPushButton("Save scene/meshes")
        self.save_scene_button.clicked.connect(self._save_scene_outputs)
        button_grid.addWidget(self.save_scene_button, 1, 0)
        self.screenshot_button = QtWidgets.QPushButton("Screenshot")
        self.screenshot_button.clicked.connect(self._save_screenshot)
        button_grid.addWidget(self.screenshot_button, 1, 1)
        side_layout.addLayout(button_grid)

        self.plotter = QtInteractor(central)

        right = QtWidgets.QWidget()
        right.setFixedWidth(570)
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.addWidget(QtWidgets.QLabel("Allen-style 2D slice viewer"))
        self.coronal_label = QtWidgets.QLabel("Coronal")
        right_layout.addWidget(self.coronal_label)
        self.coronal_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.coronal_slider.setMinimum(0)
        self.coronal_slider.setMaximum(self.shape[0] - 1)
        self.coronal_slider.valueChanged.connect(lambda _: self._update_slice_views())
        right_layout.addWidget(self.coronal_slider)
        self.coronal_fig = Figure(figsize=(5.3, 4.2), dpi=100)
        self.coronal_canvas = FigureCanvas(self.coronal_fig)
        right_layout.addWidget(self.coronal_canvas, stretch=1)
        self.sagittal_label = QtWidgets.QLabel("Sagittal")
        right_layout.addWidget(self.sagittal_label)
        self.sagittal_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.sagittal_slider.setMinimum(0)
        self.sagittal_slider.setMaximum(self.shape[2] - 1)
        self.sagittal_slider.valueChanged.connect(lambda _: self._update_slice_views())
        right_layout.addWidget(self.sagittal_slider)
        self.sagittal_fig = Figure(figsize=(5.3, 4.2), dpi=100)
        self.sagittal_canvas = FigureCanvas(self.sagittal_fig)
        right_layout.addWidget(self.sagittal_canvas, stretch=1)

        layout.addWidget(side)
        layout.addWidget(self.plotter.interactor, stretch=1)
        layout.addWidget(right)
        self.status = self.statusBar()

    def _add_slider(self, layout, label, min_value, max_value, value):
        layout.addWidget(QtWidgets.QLabel(label))
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setMinimum(min_value)
        slider.setMaximum(max_value)
        slider.setValue(value)
        slider.valueChanged.connect(lambda _: self._refresh_scene())
        layout.addWidget(slider)
        return slider

    # ---------- loading/rendering ----------
    def _load_reference_brain_shell(self) -> None:
        self.plotter.clear()
        for acronym in ["root", "grey", "CH", "CTX", "HPF"]:
            try:
                mesh = trimesh.load(self.atlas.meshfile_from_structure(acronym), force="mesh")
                self.reference_actor = self.plotter.add_mesh(
                    pv.wrap(mesh), color="#d8d8d8", opacity=self.brain_opacity_slider.value() / 100,
                    show_edges=False, pickable=False, name="reference_brain"
                )
                break
            except Exception:
                continue
        self.plotter.add_axes()
        self.plotter.enable_eye_dome_lighting()
        self.plotter.show_grid()
        self.plotter.reset_camera()

    def _load_region(self, acronym: str, make_active: bool = True, quiet: bool = False) -> bool:
        if acronym in self.regions:
            if make_active:
                self.active_area = acronym
            return True
        try:
            tri_mesh = trimesh.load(self.atlas.meshfile_from_structure(acronym), force="mesh")
            sid = self._structure_id(acronym)
            region = RegionMesh(
                acronym=acronym,
                name=self._structure_name(acronym),
                structure_id=sid,
                descendant_ids=self._descendant_ids(sid),
                trimesh_mesh=tri_mesh,
                pyvista_mesh=pv.wrap(tri_mesh),
                face_centroids=tri_mesh.triangles_center,
                color=self._structure_color(acronym),
            )
            region.actor = self.plotter.add_mesh(
                region.pyvista_mesh, color=region.color, opacity=self._mesh_opacity(acronym),
                show_edges=True, edge_color="gray", line_width=0.2, pickable=True, name=acronym
            )
            self.regions[acronym] = region
            if make_active:
                self.active_area = acronym
            if not quiet:
                self._update_status(f"Loaded {acronym}: {region.name}")
            return True
        except Exception as exc:
            self._update_status(f"Could not load {acronym}: {exc}")
            return False

    def _filter_region_picker(self, text: str) -> None:
        query = text.lower().strip()
        self.region_picker.clear()
        n = 0
        for label in self.all_region_labels:
            if not query or query in label.lower():
                self.region_picker.addItem(label)
                n += 1
            if n >= 250:
                break

    def _load_selected_region(self) -> None:
        text = self.region_picker.currentText()
        if not text:
            return
        acronym = text.split(" - ", 1)[0]
        if self._load_region(acronym, make_active=True):
            self._refresh_controls()
            self._refresh_scene()

    def _refresh_controls(self) -> None:
        self._filter_region_picker(self.region_search.text())
        self.active_combo.blockSignals(True)
        self.active_combo.clear()
        self.active_combo.addItems(list(self.regions.keys()))
        if self.active_area in self.regions:
            self.active_combo.setCurrentText(self.active_area)
        self.active_combo.blockSignals(False)
        self._refresh_region_table()

    def _refresh_region_table(self) -> None:
        self.region_table.setRowCount(len(self.regions))
        for row, (acronym, region) in enumerate(self.regions.items()):
            show_box = QtWidgets.QCheckBox()
            show_box.setChecked(region.visible)
            show_box.stateChanged.connect(lambda _, a=acronym, b=show_box: self._set_region_visibility(a, b.isChecked()))
            self.region_table.setCellWidget(row, 0, show_box)
            self.region_table.setItem(row, 1, QtWidgets.QTableWidgetItem(acronym))
            self.region_table.setItem(row, 2, QtWidgets.QTableWidgetItem(region.name))
            color_button = QtWidgets.QPushButton(region.color)
            color_button.setStyleSheet(f"background-color: {region.color};")
            color_button.clicked.connect(lambda _, a=acronym, b=color_button: self._choose_region_color(a, b))
            self.region_table.setCellWidget(row, 3, color_button)

    def _mesh_opacity(self, acronym: str) -> float:
        if acronym == self.active_area:
            return self.active_opacity_slider.value() / 100
        return self.reference_opacity_slider.value() / 100

    def _refresh_scene(self) -> None:
        if self.reference_actor is not None:
            self.reference_actor.SetVisibility(self.reference_checkbox.isChecked())
            self.reference_actor.GetProperty().SetOpacity(self.brain_opacity_slider.value() / 100)
        for acronym, region in self.regions.items():
            if region.actor is not None:
                region.actor.SetVisibility(region.visible)
                region.actor.GetProperty().SetColor(*hex_to_rgb01(region.color))
                region.actor.GetProperty().SetOpacity(self._mesh_opacity(acronym))
            if region.painted_actor is not None:
                region.painted_actor.SetVisibility(region.visible)
                region.painted_actor.GetProperty().SetColor(*hex_to_rgb01(self.paint_color))
                region.painted_actor.GetProperty().SetOpacity(self.paint_opacity_slider.value() / 100)
        if self.cell_layer and self.cell_layer.actor:
            self.cell_layer.actor.GetProperty().SetColor(*hex_to_rgb01(self.cell_layer.color))
        self.plotter.render()
        self._update_slice_views()

    # ---------- slices ----------
    def _um_to_index(self, value_um: float, axis: int) -> int:
        return int(np.clip(round(value_um / self.resolution_um[axis]), 0, self.shape[axis] - 1))

    def _index_to_um(self, index: int, axis: int) -> float:
        return float(index * self.resolution_um[axis])

    def _reset_slices_to_active_region(self) -> None:
        if self.active_area and self.active_area in self.regions:
            center = self.regions[self.active_area].face_centroids.mean(axis=0)
            self.coronal_slider.setValue(self._um_to_index(center[0], 0))
            self.sagittal_slider.setValue(self._um_to_index(center[2], 2))
        else:
            self.coronal_slider.setValue(self.shape[0] // 2)
            self.sagittal_slider.setValue(self.shape[2] // 2)

    def _annotation_rgb(self, annotation_slice: np.ndarray) -> np.ndarray:
        rgb = np.full((*annotation_slice.shape, 3), 245, dtype=np.uint8)
        rgb[annotation_slice > 0] = np.array([224, 224, 224], dtype=np.uint8)
        for region in self.regions.values():
            if region.visible and region.descendant_ids:
                mask = np.isin(annotation_slice, list(region.descendant_ids))
                rgb[mask] = hex_to_rgb255(region.color)
        return rgb

    def _update_slice_views(self) -> None:
        if not hasattr(self, "coronal_fig"):
            return
        self._plot_coronal()
        self._plot_sagittal()

    def _plot_coronal(self) -> None:
        x_idx = self.coronal_slider.value()
        x_um = self._index_to_um(x_idx, 0)
        self.coronal_label.setText(f"Coronal X/AP: index {x_idx}, {x_um:.0f} um")
        rgb = self._annotation_rgb(self.annotation[x_idx, :, :])
        self.coronal_fig.clear()
        ax = self.coronal_fig.add_subplot(111)
        ax.imshow(rgb, extent=[0, self.size_um[2], self.size_um[1], 0], origin="upper", interpolation="nearest")
        ax.set_xlabel("Z / ML, um")
        ax.set_ylabel("Y / DV, um")
        self._overlay_points(ax, "coronal", x_um)
        self.coronal_fig.tight_layout()
        self.coronal_canvas.draw_idle()

    def _plot_sagittal(self) -> None:
        z_idx = self.sagittal_slider.value()
        z_um = self._index_to_um(z_idx, 2)
        self.sagittal_label.setText(f"Sagittal Z/ML: index {z_idx}, {z_um:.0f} um")
        rgb = self._annotation_rgb(self.annotation[:, :, z_idx]).transpose(1, 0, 2)
        self.sagittal_fig.clear()
        ax = self.sagittal_fig.add_subplot(111)
        ax.imshow(rgb, extent=[0, self.size_um[0], self.size_um[1], 0], origin="upper", interpolation="nearest")
        ax.set_xlabel("X / AP, um")
        ax.set_ylabel("Y / DV, um")
        self._overlay_points(ax, "sagittal", z_um)
        self.sagittal_fig.tight_layout()
        self.sagittal_canvas.draw_idle()

    def _overlay_points(self, ax, plane: str, plane_um: float) -> None:
        half_thick = self.slice_thickness_slider.value() / 2
        if self.show_painted_2d_checkbox.isChecked():
            for region in self.regions.values():
                if not region.visible or not region.painted_faces:
                    continue
                pts = region.face_centroids[sorted(region.painted_faces)]
                if plane == "coronal":
                    pts = pts[np.abs(pts[:, 0] - plane_um) <= half_thick]
                    if pts.size:
                        ax.scatter(pts[:, 2], pts[:, 1], s=8, c=self.paint_color, edgecolors="none")
                else:
                    pts = pts[np.abs(pts[:, 2] - plane_um) <= half_thick]
                    if pts.size:
                        ax.scatter(pts[:, 0], pts[:, 1], s=8, c=self.paint_color, edgecolors="none")
        if self.show_cells_2d_checkbox.isChecked() and self.cell_layer is not None:
            pts = self.cell_layer.xyz
            if plane == "coronal":
                near = pts[np.abs(pts[:, 0] - plane_um) <= half_thick]
                if near.size:
                    ax.scatter(near[:, 2], near[:, 1], s=18, c=self.cell_layer.color, edgecolors="black", linewidths=0.2)
            else:
                near = pts[np.abs(pts[:, 2] - plane_um) <= half_thick]
                if near.size:
                    ax.scatter(near[:, 0], near[:, 1], s=18, c=self.cell_layer.color, edgecolors="black", linewidths=0.2)

    # ---------- painting ----------
    def _setup_picking(self) -> None:
        self.cell_picker = vtk.vtkCellPicker()
        self.cell_picker.SetTolerance(0.0008)
        iren = self.plotter.iren.interactor
        iren.AddObserver("LeftButtonPressEvent", self._on_left_press)
        iren.AddObserver("LeftButtonReleaseEvent", self._on_left_release)
        iren.AddObserver("MouseMoveEvent", self._on_mouse_move)

    def _on_left_press(self, obj, event) -> None:
        self.mouse_down = True
        self._paint_from_mouse()

    def _on_left_release(self, obj, event) -> None:
        self.mouse_down = False

    def _on_mouse_move(self, obj, event) -> None:
        if self.mouse_down and self.continuous_checkbox.isChecked():
            self._paint_from_mouse()

    def _paint_from_mouse(self) -> None:
        if not self.active_area or self.active_area not in self.regions:
            return
        iren = self.plotter.iren.interactor
        x, y = iren.GetEventPosition()
        if not self.cell_picker.Pick(x, y, 0, self.plotter.renderer):
            return
        point = np.asarray(self.cell_picker.GetPickPosition(), dtype=float)
        self.last_picked_point = point
        if self.sync_slice_checkbox.isChecked():
            self.coronal_slider.setValue(self._um_to_index(point[0], 0))
            self.sagittal_slider.setValue(self._um_to_index(point[2], 2))
        self._paint_near_point(point)
        if self.symmetry_checkbox.isChecked():
            mirror = point.copy()
            mirror[2] = (2 * self.midline_z_um) - mirror[2]
            self.last_mirror_point = mirror
            self._paint_near_point(mirror)

    def _paint_near_point(self, point: np.ndarray) -> None:
        region = self.regions[self.active_area]
        distances = np.linalg.norm(region.face_centroids - point[None, :], axis=1)
        face_ids = set(int(x) for x in np.where(distances <= self.brush_slider.value())[0])
        if not face_ids:
            face_ids = {int(np.argmin(distances))}
        if self.paint_mode == "paint":
            region.painted_faces.update(face_ids)
        else:
            region.painted_faces.difference_update(face_ids)
        self._update_painted_overlay(region)
        self._update_status(f"{self.paint_mode} {region.acronym}: {len(region.painted_faces)} painted faces")
        self._refresh_scene()

    def _selected_faces_mesh(self, region: RegionMesh) -> trimesh.Trimesh | None:
        if not region.painted_faces:
            return None
        faces = region.trimesh_mesh.faces[sorted(region.painted_faces)]
        return trimesh.Trimesh(vertices=region.trimesh_mesh.vertices.copy(), faces=faces, process=True)

    def _update_painted_overlay(self, region: RegionMesh) -> None:
        if region.painted_actor is not None:
            self.plotter.remove_actor(region.painted_actor)
            region.painted_actor = None
        selected = self._selected_faces_mesh(region)
        if selected is not None:
            region.painted_actor = self.plotter.add_mesh(
                pv.wrap(selected), color=self.paint_color, opacity=self.paint_opacity_slider.value() / 100,
                show_edges=False, pickable=False, name=f"painted_{region.acronym}"
            )

    # ---------- cells ----------
    def _load_cells_dialog(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load cell coordinates", str(PROJECT_DIR),
            "Table files (*.csv *.tsv *.txt *.xlsx *.xls);;All files (*)"
        )
        if not path:
            return
        try:
            df = self._read_table(Path(path))
            x_col, y_col, z_col = self._find_xyz_columns(df)
            xyz = df[[x_col, y_col, z_col]].astype(float).to_numpy()
            xyz = xyz[np.all(np.isfinite(xyz), axis=1)]
            self.cell_layer = CellLayer(path=path, dataframe=df, xyz=xyz)
            pdata = pv.PolyData(xyz)
            self.cell_layer.actor = self.plotter.add_mesh(
                pdata, color=self.cell_layer.color, point_size=8, render_points_as_spheres=True,
                pickable=False, name="cell_coordinates"
            )
            self._update_status(f"Loaded {xyz.shape[0]} cells from {Path(path).name}")
            self._refresh_scene()
        except Exception as exc:
            self._update_status(f"Could not load cells: {exc}")

    def _read_table(self, path: Path) -> pd.DataFrame:
        if path.suffix.lower() in {".xlsx", ".xls"}:
            return pd.read_excel(path)
        if path.suffix.lower() == ".tsv":
            return pd.read_csv(path, sep="\t")
        if path.suffix.lower() == ".txt":
            return pd.read_csv(path, sep=None, engine="python")
        return pd.read_csv(path)

    def _find_xyz_columns(self, df: pd.DataFrame):
        lower = {str(c).strip().lower(): c for c in df.columns}
        aliases = {
            "x": ["x", "x_um", "atlas_x", "ap"],
            "y": ["y", "y_um", "atlas_y", "dv"],
            "z": ["z", "z_um", "atlas_z", "ml"],
        }
        found = []
        for axis in ["x", "y", "z"]:
            col = next((lower[a] for a in aliases[axis] if a in lower), None)
            if col is None:
                raise ValueError("Expected x/y/z columns or aliases x_um/y_um/z_um, atlas_x/atlas_y/atlas_z, ap/dv/ml")
            found.append(col)
        return found

    # ---------- buttons / saving ----------
    def _set_active_area(self, acronym: str) -> None:
        if acronym in self.regions:
            self.active_area = acronym
            self._refresh_scene()

    def _set_region_visibility(self, acronym: str, visible: bool) -> None:
        self.regions[acronym].visible = visible
        self._refresh_scene()

    def _choose_region_color(self, acronym: str, button: QtWidgets.QPushButton) -> None:
        color = QtWidgets.QColorDialog.getColor(QColor(self.regions[acronym].color), self, "Choose region color")
        if color.isValid():
            self.regions[acronym].color = color.name()
            button.setText(color.name())
            button.setStyleSheet(f"background-color: {color.name()};")
            self._refresh_scene()

    def _choose_paint_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(QColor(self.paint_color), self, "Choose paint color")
        if color.isValid():
            self.paint_color = color.name()
            self.paint_color_button.setText(self.paint_color)
            self.paint_color_button.setStyleSheet(f"background-color: {self.paint_color}; color: black;")
            for region in self.regions.values():
                self._update_painted_overlay(region)
            self._refresh_scene()

    def _toggle_mode(self) -> None:
        self.paint_mode = "erase" if self.paint_mode == "paint" else "paint"
        self.mode_button.setText(f"Mode: {self.paint_mode}")

    def _clear_active_paint(self) -> None:
        if self.active_area:
            region = self.regions[self.active_area]
            region.painted_faces.clear()
            self._update_painted_overlay(region)
            self._refresh_scene()

    def _clear_cells(self) -> None:
        if self.cell_layer and self.cell_layer.actor is not None:
            self.plotter.remove_actor(self.cell_layer.actor)
        self.cell_layer = None
        self._refresh_scene()

    def _save_active_roi(self) -> None:
        if not self.active_area:
            return
        region = self.regions[self.active_area]
        if not region.painted_faces:
            self._update_status(f"No painted faces to save for {region.acronym}")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"{region.acronym}_painted_roi_{timestamp}"
        mesh = self._selected_faces_mesh(region)
        ply_path = OUTPUT_DIR / f"{stem}.ply"
        csv_path = OUTPUT_DIR / f"{stem}_face_ids.csv"
        json_path = OUTPUT_DIR / f"{stem}_metadata.json"
        mesh.export(ply_path)
        self._write_face_ids(region, csv_path)
        metadata = {
            "atlas": ATLAS_NAME,
            "area": region.acronym,
            "region_name": region.name,
            "structure_id": region.structure_id,
            "n_painted_faces": len(region.painted_faces),
            "atlas_resolution_um": self.resolution_um,
            "atlas_shape": self.shape,
            "paint_color": self.paint_color,
            "region_color": region.color,
            "ply_file": str(ply_path),
            "face_ids_file": str(csv_path),
        }
        with open(json_path, "w") as f:
            json.dump(metadata, f, indent=2)
        self._update_status(f"Saved active ROI: {ply_path}")

    def _write_face_ids(self, region: RegionMesh, path: Path) -> None:
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["area", "face_id", "center_x_um", "center_y_um", "center_z_um"])
            for face_id in sorted(region.painted_faces):
                x, y, z = region.face_centroids[face_id]
                writer.writerow([region.acronym, face_id, x, y, z])

    def _save_scene_outputs(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scene_dir = OUTPUT_DIR / f"scene_{timestamp}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        manifest = {"atlas": ATLAS_NAME, "regions": [], "cells_file": None}
        for acronym, region in self.regions.items():
            full_path = scene_dir / f"{acronym}_full_mesh.ply"
            region.trimesh_mesh.export(full_path)
            item = {
                "area": acronym,
                "name": region.name,
                "structure_id": region.structure_id,
                "color": region.color,
                "visible": region.visible,
                "full_mesh_file": str(full_path),
                "n_painted_faces": len(region.painted_faces),
            }
            if region.painted_faces:
                roi_path = scene_dir / f"{acronym}_painted_roi.ply"
                face_path = scene_dir / f"{acronym}_painted_face_ids.csv"
                self._selected_faces_mesh(region).export(roi_path)
                self._write_face_ids(region, face_path)
                item["painted_roi_file"] = str(roi_path)
                item["painted_face_ids_file"] = str(face_path)
            manifest["regions"].append(item)
        if self.cell_layer is not None:
            cells_path = scene_dir / "imported_cells_atlas_coordinates.csv"
            pd.DataFrame(self.cell_layer.xyz, columns=["x", "y", "z"]).to_csv(cells_path, index=False)
            manifest["cells_file"] = str(cells_path)
        with open(scene_dir / "scene_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
        self._update_status(f"Saved scene outputs: {scene_dir}")

    def _save_screenshot(self) -> None:
        path = OUTPUT_DIR / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        self.plotter.screenshot(str(path))
        self._update_status(f"Saved screenshot: {path}")

    def _update_status(self, text: str) -> None:
        self.status.showMessage(text)


def main() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MeshPainterWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
