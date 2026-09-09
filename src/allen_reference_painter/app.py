"""
Allen Reference Painter - Python/Qt desktop prototype.

BrainGlobe Allen 25um atlas -> trimesh/PyVista meshes -> Qt GUI for viewing,
painting, importing cell coordinates, and saving atlas-coordinate outputs.
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

from .runtime import data_dir
from .meshes import load_atlas_mesh

PROJECT_DIR = data_dir()
OUTPUT_DIR = PROJECT_DIR / "outputs"
PROJECTS_DIR = PROJECT_DIR / "projects"
OUTPUT_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)

ATLAS_NAME = "allen_mouse_25um"
STARTER_AREAS: list[str] = []

DEFAULT_PAINT_COLOR = "#ff3333"
DEFAULT_MIRROR_COLOR = "#00d7ff"
DEFAULT_CELL_COLOR = "#00d7ff"
DEFAULT_REGION_COLOR = "#dddddd"
CORONAL_PLANE_COLOR = "#ffd400"
SAGITTAL_PLANE_COLOR = "#00d7ff"

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

CELL_UNIT_OPTIONS = {
    "Microns / atlas space (um)": "um",
    "Millimeters (mm -> um x1000)": "mm",
    "Voxel indices (index -> um using atlas resolution)": "voxel",
    "Auto detect": "auto",
}

NONE_LABEL = "(none)"
SINGLE_COLOR_LABEL = "(single color)"


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
    original_xyz: np.ndarray
    xyz: np.ndarray
    coordinate_mode: str
    color: str = DEFAULT_CELL_COLOR
    actor: object | None = None
    label_column: str | None = None
    color_column: str | None = None


class MeshPainterWindow(QtWidgets.QMainWindow):
    def __init__(self, atlas=None) -> None:
        super().__init__()
        self.setWindowTitle("Allen Reference Painter")
        self.resize(2150, 1180)

        self.atlas = atlas if atlas is not None else BrainGlobeAtlas(ATLAS_NAME)
        self.annotation = np.asarray(self.atlas.annotation)
        self.resolution_um = tuple(float(x) for x in self.atlas.resolution)
        self.shape = self.annotation.shape
        self.size_um = tuple(self.shape[i] * self.resolution_um[i] for i in range(3))
        self.midline_z_um = self.size_um[2] / 2.0

        self.regions: Dict[str, RegionMesh] = {}
        self.active_area: str | None = None
        self.paint_mode = "paint"
        self.paint_color = DEFAULT_PAINT_COLOR
        self.mirror_color = DEFAULT_MIRROR_COLOR
        self.cell_layer: CellLayer | None = None
        self.mouse_down = False
        self.last_picked_point: np.ndarray | None = None
        self.last_mirror_point: np.ndarray | None = None
        self.reference_actor = None
        self.coronal_plane_actor = None
        self.sagittal_plane_actor = None

        self.structure_index = self._build_structure_index()
        self.all_region_labels = self._all_region_labels()

        self._build_ui()
        self._load_reference_brain_shell()
        for area in STARTER_AREAS:
            self._load_region(area, make_active=False, quiet=True)
        self._refresh_controls()
        self._setup_picking()
        self._reset_slices_to_center()
        self._on_slice_changed()
        self._update_status("Ready. Search/load a region or import cells. No region meshes are preloaded.")

    # ------------------------------------------------------------------
    # Atlas helpers
    # ------------------------------------------------------------------
    def _build_structure_index(self) -> dict[str, dict]:
        out = {}
        for sid, info in self.atlas.structures.items():
            acronym = str(info.get("acronym", "")).strip()
            if not acronym:
                continue
            atlas_color = rgb_triplet_to_hex(info.get("rgb_triplet"))
            out[acronym] = {
                "id": int(sid),
                "name": str(info.get("name", acronym)),
                "color": FALLBACK_REGION_COLORS.get(acronym, atlas_color or DEFAULT_REGION_COLOR),
            }
        return out

    def _all_region_labels(self) -> list[str]:
        return [
            f"{acronym} - {info['name']}"
            for acronym, info in sorted(self.structure_index.items(), key=lambda x: x[0].lower())
        ]

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

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout(central)

        left = QtWidgets.QWidget()
        left.setFixedWidth(470)
        left_layout = QtWidgets.QVBoxLayout(left)

        title = QtWidgets.QLabel("Allen Reference Painter")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        left_layout.addWidget(title)

        left_layout.addWidget(QtWidgets.QLabel("Search/load Allen region or subregion"))
        self.region_search = QtWidgets.QLineEdit()
        self.region_search.setPlaceholderText("Search acronym/name, e.g. ENT, SUB, CA1")
        self.region_search.textChanged.connect(self._filter_region_picker)
        left_layout.addWidget(self.region_search)

        self.region_picker = QtWidgets.QComboBox()
        left_layout.addWidget(self.region_picker)

        load_row = QtWidgets.QHBoxLayout()
        self.load_region_button = QtWidgets.QPushButton("Load selected region")
        self.load_region_button.clicked.connect(self._load_selected_region)
        load_row.addWidget(self.load_region_button)
        self.remove_region_button = QtWidgets.QPushButton("Remove active")
        self.remove_region_button.clicked.connect(self._remove_active_region)
        load_row.addWidget(self.remove_region_button)
        left_layout.addLayout(load_row)

        left_layout.addWidget(QtWidgets.QLabel("Loaded region meshes"))
        self.region_table = QtWidgets.QTableWidget()
        self.region_table.setColumnCount(4)
        self.region_table.setHorizontalHeaderLabels(["Show", "Area", "Name", "Color"])
        self.region_table.verticalHeader().setVisible(False)
        self.region_table.setAlternatingRowColors(True)
        self.region_table.setColumnWidth(0, 48)
        self.region_table.setColumnWidth(1, 72)
        self.region_table.setColumnWidth(2, 220)
        self.region_table.setColumnWidth(3, 92)
        self.region_table.horizontalHeader().setStretchLastSection(True)
        self.region_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.region_table.cellClicked.connect(self._region_table_clicked)
        left_layout.addWidget(self.region_table, stretch=1)

        center = QtWidgets.QWidget()
        center_layout = QtWidgets.QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)

        top_tools = QtWidgets.QWidget()
        top_layout = QtWidgets.QVBoxLayout(top_tools)
        top_layout.setContentsMargins(4, 4, 4, 4)

        row1 = QtWidgets.QHBoxLayout()
        self.active_combo = QtWidgets.QComboBox()
        self.active_combo.currentTextChanged.connect(self._set_active_area)
        row1.addWidget(QtWidgets.QLabel("Active region:"))
        row1.addWidget(self.active_combo, stretch=2)

        self.mode_button = QtWidgets.QPushButton("Mode: paint")
        self.mode_button.clicked.connect(self._toggle_mode)
        row1.addWidget(self.mode_button)

        self.paint_color_button = QtWidgets.QPushButton(self.paint_color)
        self.paint_color_button.setStyleSheet(f"background-color: {self.paint_color}; color: black;")
        self.paint_color_button.clicked.connect(self._choose_paint_color)
        row1.addWidget(QtWidgets.QLabel("Paint color:"))
        row1.addWidget(self.paint_color_button)

        self.mirror_color_button = QtWidgets.QPushButton(self.mirror_color)
        self.mirror_color_button.setStyleSheet(f"background-color: {self.mirror_color}; color: black;")
        self.mirror_color_button.clicked.connect(self._choose_mirror_color)
        row1.addWidget(QtWidgets.QLabel("Mirror marker:"))
        row1.addWidget(self.mirror_color_button)
        top_layout.addLayout(row1)

        row2 = QtWidgets.QHBoxLayout()
        self.continuous_checkbox = QtWidgets.QCheckBox("Continuous paint while dragging")
        self.continuous_checkbox.setChecked(False)
        row2.addWidget(self.continuous_checkbox)

        self.symmetry_checkbox = QtWidgets.QCheckBox("Symmetric mirror painting")
        self.symmetry_checkbox.setChecked(False)
        row2.addWidget(self.symmetry_checkbox)

        self.sync_slice_checkbox = QtWidgets.QCheckBox("3D click updates slices")
        self.sync_slice_checkbox.setChecked(True)
        row2.addWidget(self.sync_slice_checkbox)

        self.reference_checkbox = QtWidgets.QCheckBox("Reference brain")
        self.reference_checkbox.setChecked(True)
        self.reference_checkbox.stateChanged.connect(lambda _: self._refresh_scene())
        row2.addWidget(self.reference_checkbox)

        self.show_coronal_plane_checkbox = QtWidgets.QCheckBox("3D coronal plane")
        self.show_coronal_plane_checkbox.setChecked(False)
        self.show_coronal_plane_checkbox.stateChanged.connect(lambda _: self._update_slice_planes())
        row2.addWidget(self.show_coronal_plane_checkbox)

        self.show_sagittal_plane_checkbox = QtWidgets.QCheckBox("3D sagittal plane")
        self.show_sagittal_plane_checkbox.setChecked(False)
        self.show_sagittal_plane_checkbox.stateChanged.connect(lambda _: self._update_slice_planes())
        row2.addWidget(self.show_sagittal_plane_checkbox)

        self.show_painted_2d_checkbox = QtWidgets.QCheckBox("ROI on slices")
        self.show_painted_2d_checkbox.setChecked(True)
        self.show_painted_2d_checkbox.stateChanged.connect(lambda _: self._update_slice_views())
        row2.addWidget(self.show_painted_2d_checkbox)

        self.show_cells_2d_checkbox = QtWidgets.QCheckBox("Cells on slices")
        self.show_cells_2d_checkbox.setChecked(True)
        self.show_cells_2d_checkbox.stateChanged.connect(lambda _: self._update_slice_views())
        row2.addWidget(self.show_cells_2d_checkbox)
        row2.addStretch(1)
        top_layout.addLayout(row2)

        row3 = QtWidgets.QHBoxLayout()
        self.brush_slider = self._compact_slider(row3, "Brush um", 25, 800, 150, self._refresh_scene)
        self.active_opacity_slider = self._compact_slider(row3, "Active opacity", 5, 100, 60, self._refresh_scene)
        self.reference_opacity_slider = self._compact_slider(row3, "Other opacity", 0, 100, 30, self._refresh_scene)
        self.paint_opacity_slider = self._compact_slider(row3, "Paint opacity", 10, 100, 90, self._refresh_scene)
        self.brain_opacity_slider = self._compact_slider(row3, "Brain opacity", 0, 100, 8, self._refresh_scene)
        self.slice_thickness_slider = self._compact_slider(row3, "Slice thick um", 25, 1000, 250, self._update_slice_views)
        self.cell_size_slider = self._compact_slider(row3, "Cell size", 4, 60, 22, self._refresh_cell_actor)
        self.plane_opacity_slider = self._compact_slider(row3, "Plane opacity", 1, 60, 12, self._update_slice_planes)
        top_layout.addLayout(row3)

        row4 = QtWidgets.QHBoxLayout()
        row4.addWidget(QtWidgets.QLabel("Cell units:"))
        self.cell_units_combo = QtWidgets.QComboBox()
        self.cell_units_combo.addItems(list(CELL_UNIT_OPTIONS.keys()))
        self.cell_units_combo.setCurrentText("Microns / atlas space (um)")
        self.cell_units_combo.currentTextChanged.connect(lambda _: self._apply_cell_units_to_loaded_cells())
        row4.addWidget(self.cell_units_combo)

        self.apply_cell_units_button = QtWidgets.QPushButton("Apply units")
        self.apply_cell_units_button.clicked.connect(self._apply_cell_units_to_loaded_cells)
        row4.addWidget(self.apply_cell_units_button)

        self.load_cells_button = QtWidgets.QPushButton("Load cells CSV/TSV/XLSX")
        self.load_cells_button.clicked.connect(self._load_cells_dialog)
        row4.addWidget(self.load_cells_button)
        self.clear_cells_button = QtWidgets.QPushButton("Clear cells")
        self.clear_cells_button.clicked.connect(self._clear_cells)
        row4.addWidget(self.clear_cells_button)
        self.clear_button = QtWidgets.QPushButton("Clear active paint")
        self.clear_button.clicked.connect(self._clear_active_paint)
        row4.addWidget(self.clear_button)
        self.save_roi_button = QtWidgets.QPushButton("Save active ROI")
        self.save_roi_button.clicked.connect(self._save_active_roi)
        row4.addWidget(self.save_roi_button)
        self.save_scene_button = QtWidgets.QPushButton("Save scene/meshes")
        self.save_scene_button.clicked.connect(self._save_scene_outputs)
        row4.addWidget(self.save_scene_button)
        self.screenshot_button = QtWidgets.QPushButton("Screenshot")
        self.screenshot_button.clicked.connect(self._save_screenshot)
        row4.addWidget(self.screenshot_button)
        row4.addStretch(1)
        top_layout.addLayout(row4)

        row5 = QtWidgets.QHBoxLayout()
        row5.addWidget(QtWidgets.QLabel("Cell label/hover:"))
        self.cell_label_combo = QtWidgets.QComboBox()
        self.cell_label_combo.addItem(NONE_LABEL)
        self.cell_label_combo.currentTextChanged.connect(self._cell_metadata_options_changed)
        row5.addWidget(self.cell_label_combo)

        row5.addWidget(QtWidgets.QLabel("Color cells by:"))
        self.cell_colorby_combo = QtWidgets.QComboBox()
        self.cell_colorby_combo.addItem(SINGLE_COLOR_LABEL)
        self.cell_colorby_combo.currentTextChanged.connect(self._cell_metadata_options_changed)
        row5.addWidget(self.cell_colorby_combo)

        row5.addWidget(QtWidgets.QLabel("Camera:"))
        for label, callback in [
            ("Iso", self._view_iso),
            ("XY", self._view_xy),
            ("XZ", self._view_xz),
            ("YZ", self._view_yz),
        ]:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(callback)
            row5.addWidget(button)
        row5.addStretch(1)
        top_layout.addLayout(row5)

        center_layout.addWidget(top_tools)
        self.plotter = QtInteractor(central)
        center_layout.addWidget(self.plotter.interactor, stretch=1)

        right = QtWidgets.QWidget()
        right.setFixedWidth(570)
        right_layout = QtWidgets.QVBoxLayout(right)
        right_title = QtWidgets.QLabel("Allen-style 2D slice viewer")
        right_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        right_layout.addWidget(right_title)

        self.coronal_label = QtWidgets.QLabel("Coronal")
        right_layout.addWidget(self.coronal_label)
        self.coronal_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.coronal_slider.setMinimum(0)
        self.coronal_slider.setMaximum(self.shape[0] - 1)
        self.coronal_slider.valueChanged.connect(lambda _: self._on_slice_changed())
        right_layout.addWidget(self.coronal_slider)
        self.coronal_fig = Figure(figsize=(5.3, 4.2), dpi=100)
        self.coronal_canvas = FigureCanvas(self.coronal_fig)
        right_layout.addWidget(self.coronal_canvas, stretch=1)

        self.sagittal_label = QtWidgets.QLabel("Sagittal")
        right_layout.addWidget(self.sagittal_label)
        self.sagittal_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.sagittal_slider.setMinimum(0)
        self.sagittal_slider.setMaximum(self.shape[2] - 1)
        self.sagittal_slider.valueChanged.connect(lambda _: self._on_slice_changed())
        right_layout.addWidget(self.sagittal_slider)
        self.sagittal_fig = Figure(figsize=(5.3, 4.2), dpi=100)
        self.sagittal_canvas = FigureCanvas(self.sagittal_fig)
        right_layout.addWidget(self.sagittal_canvas, stretch=1)

        main_layout.addWidget(left)
        main_layout.addWidget(center, stretch=1)
        main_layout.addWidget(right)
        self.status = self.statusBar()

    def _compact_slider(self, layout, label, min_value, max_value, value, callback):
        box = QtWidgets.QWidget()
        box.setFixedWidth(145)
        vbox = QtWidgets.QVBoxLayout(box)
        vbox.setContentsMargins(2, 0, 2, 0)
        text = QtWidgets.QLabel(f"{label}: {value}")
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setMinimum(min_value)
        slider.setMaximum(max_value)
        slider.setValue(value)

        def on_change(v):
            text.setText(f"{label}: {v}")
            callback()

        slider.valueChanged.connect(on_change)
        vbox.addWidget(text)
        vbox.addWidget(slider)
        layout.addWidget(box)
        return slider

    # ------------------------------------------------------------------
    # Loading/rendering
    # ------------------------------------------------------------------
    def _load_reference_brain_shell(self) -> None:
        self.plotter.clear()
        for acronym in ["root", "grey", "CH", "CTX", "HPF"]:
            try:
                mesh = load_atlas_mesh(self.atlas, acronym)
                self.reference_actor = self.plotter.add_mesh(
                    pv.wrap(mesh),
                    color="#d8d8d8",
                    opacity=self.brain_opacity_slider.value() / 100,
                    show_edges=False,
                    pickable=False,
                    name="reference_brain",
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
            tri_mesh = load_atlas_mesh(self.atlas, acronym)
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
            self.regions[acronym] = region
            region.actor = self.plotter.add_mesh(
                region.pyvista_mesh,
                color=region.color,
                opacity=self._mesh_opacity(acronym),
                show_edges=True,
                edge_color="gray",
                line_width=0.2,
                pickable=True,
                name=acronym,
            )
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
            self.plotter.reset_camera()

    def _remove_active_region(self) -> None:
        if not self.active_area or self.active_area not in self.regions:
            return
        acronym = self.active_area
        region = self.regions.pop(acronym)
        if region.actor is not None:
            self.plotter.remove_actor(region.actor)
        if region.painted_actor is not None:
            self.plotter.remove_actor(region.painted_actor)
        self.active_area = next(iter(self.regions), None)
        self._refresh_controls()
        self._refresh_scene()
        self._update_status(f"Removed {acronym}")

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
        self.region_table.resizeRowsToContents()

    def _region_table_clicked(self, row: int, _col: int) -> None:
        item = self.region_table.item(row, 1)
        if item is not None and item.text() in self.regions:
            self.active_area = item.text()
            self.active_combo.setCurrentText(self.active_area)
            self._refresh_scene()

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
        self._refresh_cell_actor(update_existing_only=True)
        self._update_pick_markers()
        self._update_slice_planes()
        self.plotter.render()
        self._update_slice_views()

    # ------------------------------------------------------------------
    # Slices and plane indicators
    # ------------------------------------------------------------------
    def _um_to_index(self, value_um: float, axis: int) -> int:
        return int(np.clip(round(value_um / self.resolution_um[axis]), 0, self.shape[axis] - 1))

    def _index_to_um(self, index: int, axis: int) -> float:
        return float(index * self.resolution_um[axis])

    def _reset_slices_to_center(self) -> None:
        self.coronal_slider.setValue(self.shape[0] // 2)
        self.sagittal_slider.setValue(self.shape[2] // 2)

    def _on_slice_changed(self) -> None:
        self._update_slice_views()
        self._update_slice_planes()

    def _update_slice_planes(self) -> None:
        if not hasattr(self, "plotter"):
            return
        for actor_name in ["coronal_slice_plane", "sagittal_slice_plane"]:
            try:
                self.plotter.remove_actor(actor_name)
            except Exception:
                pass
        opacity = self.plane_opacity_slider.value() / 100 if hasattr(self, "plane_opacity_slider") else 0.12
        if getattr(self, "show_coronal_plane_checkbox", None) is not None and self.show_coronal_plane_checkbox.isChecked():
            x_um = self._index_to_um(self.coronal_slider.value(), 0)
            plane = pv.Plane(
                center=(x_um, self.size_um[1] / 2, self.size_um[2] / 2),
                direction=(1, 0, 0),
                i_size=self.size_um[2],
                j_size=self.size_um[1],
            )
            self.plotter.add_mesh(
                plane,
                color=CORONAL_PLANE_COLOR,
                opacity=opacity,
                pickable=False,
                name="coronal_slice_plane",
            )
        if getattr(self, "show_sagittal_plane_checkbox", None) is not None and self.show_sagittal_plane_checkbox.isChecked():
            z_um = self._index_to_um(self.sagittal_slider.value(), 2)
            plane = pv.Plane(
                center=(self.size_um[0] / 2, self.size_um[1] / 2, z_um),
                direction=(0, 0, 1),
                i_size=self.size_um[0],
                j_size=self.size_um[1],
            )
            self.plotter.add_mesh(
                plane,
                color=SAGITTAL_PLANE_COLOR,
                opacity=opacity,
                pickable=False,
                name="sagittal_slice_plane",
            )
        self.plotter.render()

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
                        ax.scatter(pts[:, 2], pts[:, 1], s=9, c=self.paint_color, edgecolors="none")
                else:
                    pts = pts[np.abs(pts[:, 2] - plane_um) <= half_thick]
                    if pts.size:
                        ax.scatter(pts[:, 0], pts[:, 1], s=9, c=self.paint_color, edgecolors="none")
        if self.show_cells_2d_checkbox.isChecked() and self.cell_layer is not None:
            pts = self.cell_layer.xyz
            if plane == "coronal":
                near = pts[np.abs(pts[:, 0] - plane_um) <= half_thick]
                if near.size:
                    ax.scatter(near[:, 2], near[:, 1], s=28, c=self.cell_layer.color, edgecolors="black", linewidths=0.35)
            else:
                near = pts[np.abs(pts[:, 2] - plane_um) <= half_thick]
                if near.size:
                    ax.scatter(near[:, 0], near[:, 1], s=28, c=self.cell_layer.color, edgecolors="black", linewidths=0.35)
        if self.last_picked_point is not None:
            if plane == "coronal":
                ax.scatter([self.last_picked_point[2]], [self.last_picked_point[1]], s=65, c="#ffd400", edgecolors="black")
            else:
                ax.scatter([self.last_picked_point[0]], [self.last_picked_point[1]], s=65, c="#ffd400", edgecolors="black")
        if self.symmetry_checkbox.isChecked() and self.last_mirror_point is not None:
            if plane == "coronal":
                ax.scatter([self.last_mirror_point[2]], [self.last_mirror_point[1]], s=65, c=self.mirror_color, edgecolors="black")
            else:
                ax.scatter([self.last_mirror_point[0]], [self.last_mirror_point[1]], s=65, c=self.mirror_color, edgecolors="black")

    # ------------------------------------------------------------------
    # Camera views
    # ------------------------------------------------------------------
    def _view_iso(self) -> None:
        self.plotter.view_isometric()
        self.plotter.reset_camera()

    def _view_xy(self) -> None:
        self.plotter.view_xy()
        self.plotter.reset_camera()

    def _view_xz(self) -> None:
        self.plotter.view_xz()
        self.plotter.reset_camera()

    def _view_yz(self) -> None:
        self.plotter.view_yz()
        self.plotter.reset_camera()

    # ------------------------------------------------------------------
    # Painting and picking
    # ------------------------------------------------------------------
    def _setup_picking(self) -> None:
        self.cell_picker = vtk.vtkCellPicker()
        self.cell_picker.SetTolerance(0.0008)
        self.point_picker = vtk.vtkPointPicker()
        self.point_picker.SetTolerance(0.03)
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
        elif not self.mouse_down:
            self._update_hovered_cell_status()

    def _update_hovered_cell_status(self) -> None:
        if self.cell_layer is None or self.cell_layer.actor is None:
            return
        try:
            iren = self.plotter.iren.interactor
            x, y = iren.GetEventPosition()
            if not self.point_picker.Pick(x, y, 0, self.plotter.renderer):
                return
            point_id = int(self.point_picker.GetPointId())
            if point_id < 0 or point_id >= self.cell_layer.xyz.shape[0]:
                return
            text = self._cell_status_text(point_id)
            if text:
                self._update_status(text)
        except Exception:
            return

    def _cell_status_text(self, point_id: int) -> str:
        if self.cell_layer is None:
            return ""
        row = self.cell_layer.dataframe.iloc[point_id]
        label = ""
        label_col = self.cell_label_combo.currentText() if hasattr(self, "cell_label_combo") else NONE_LABEL
        if label_col != NONE_LABEL and label_col in self.cell_layer.dataframe.columns:
            label = f"{label_col}: {row[label_col]} | "
        color_col = self.cell_colorby_combo.currentText() if hasattr(self, "cell_colorby_combo") else SINGLE_COLOR_LABEL
        color_txt = ""
        if color_col != SINGLE_COLOR_LABEL and color_col in self.cell_layer.dataframe.columns:
            color_txt = f" | {color_col}: {row[color_col]}"
        x, y, z = self.cell_layer.xyz[point_id]
        return f"Cell {point_id + 1} | {label}x/y/z um: {x:.1f}, {y:.1f}, {z:.1f}{color_txt}"

    def _paint_from_mouse(self) -> None:
        if not self.active_area or self.active_area not in self.regions:
            return
        iren = self.plotter.iren.interactor
        x, y = iren.GetEventPosition()
        if not self.cell_picker.Pick(x, y, 0, self.plotter.renderer):
            return
        point = np.asarray(self.cell_picker.GetPickPosition(), dtype=float)
        self.last_picked_point = point
        points = [point]
        if self.symmetry_checkbox.isChecked():
            mirror = point.copy()
            mirror[2] = (2 * self.midline_z_um) - mirror[2]
            self.last_mirror_point = mirror
            points.append(mirror)
        else:
            self.last_mirror_point = None
        if self.sync_slice_checkbox.isChecked():
            self.coronal_slider.setValue(self._um_to_index(point[0], 0))
            self.sagittal_slider.setValue(self._um_to_index(point[2], 2))
        self._paint_at_points(points)

    def _face_ids_near_point(self, region: RegionMesh, point: np.ndarray) -> Set[int]:
        distances = np.linalg.norm(region.face_centroids - point[None, :], axis=1)
        face_ids = set(int(x) for x in np.where(distances <= self.brush_slider.value())[0])
        if not face_ids:
            face_ids = {int(np.argmin(distances))}
        return face_ids

    def _paint_at_points(self, points: list[np.ndarray]) -> None:
        region = self.regions[self.active_area]
        face_ids: Set[int] = set()
        for point in points:
            face_ids.update(self._face_ids_near_point(region, point))
        if self.paint_mode == "paint":
            region.painted_faces.update(face_ids)
        else:
            region.painted_faces.difference_update(face_ids)
        self._update_painted_overlay(region)
        mirror_note = " + mirror" if len(points) > 1 else ""
        self._update_status(f"{self.paint_mode}{mirror_note} {region.acronym}: {len(region.painted_faces)} painted faces")
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
                pv.wrap(selected),
                color=self.paint_color,
                opacity=self.paint_opacity_slider.value() / 100,
                show_edges=False,
                pickable=False,
                name=f"painted_{region.acronym}",
            )

    def _update_pick_markers(self) -> None:
        for actor_name in ["last_pick", "last_mirror"]:
            try:
                self.plotter.remove_actor(actor_name)
            except Exception:
                pass
        if self.last_picked_point is not None:
            sphere = pv.Sphere(radius=90, center=self.last_picked_point)
            self.plotter.add_mesh(sphere, color="#ffd400", pickable=False, name="last_pick")
        if self.symmetry_checkbox.isChecked() and self.last_mirror_point is not None:
            sphere = pv.Sphere(radius=90, center=self.last_mirror_point)
            self.plotter.add_mesh(sphere, color=self.mirror_color, pickable=False, name="last_mirror")

    # ------------------------------------------------------------------
    # Cells
    # ------------------------------------------------------------------
    def _load_cells_dialog(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load cell coordinates",
            str(PROJECT_DIR),
            "Table files (*.csv *.tsv *.txt *.xlsx *.xls);;All files (*)",
        )
        if not path:
            return
        try:
            df = self._read_table(Path(path))
            x_col, y_col, z_col = self._find_xyz_columns(df)
            good_rows = np.all(np.isfinite(df[[x_col, y_col, z_col]].astype(float).to_numpy()), axis=1)
            df = df.loc[good_rows].reset_index(drop=True)
            original_xyz = df[[x_col, y_col, z_col]].astype(float).to_numpy()
            xyz, mode = self._convert_cell_coordinates(original_xyz)
            self.cell_layer = CellLayer(path=path, dataframe=df, original_xyz=original_xyz, xyz=xyz, coordinate_mode=mode)
            self._populate_cell_metadata_controls(df)
            self._refresh_cell_actor(update_existing_only=False)
            self._center_view_on_cells()
            self.plotter.reset_camera()
            self._update_status(f"Loaded {xyz.shape[0]} cells from {Path(path).name} ({mode})")
            self._refresh_scene()
        except Exception as exc:
            self._update_status(f"Could not load cells: {exc}")

    def _populate_cell_metadata_controls(self, df: pd.DataFrame) -> None:
        columns = [str(c) for c in df.columns]
        numeric_columns = [str(c) for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        for combo in [self.cell_label_combo, self.cell_colorby_combo]:
            combo.blockSignals(True)
            combo.clear()
        self.cell_label_combo.addItem(NONE_LABEL)
        self.cell_label_combo.addItems(columns)
        self.cell_colorby_combo.addItem(SINGLE_COLOR_LABEL)
        self.cell_colorby_combo.addItems(numeric_columns)
        if "Name" in columns:
            self.cell_label_combo.setCurrentText("Name")
        elif "name" in columns:
            self.cell_label_combo.setCurrentText("name")
        for combo in [self.cell_label_combo, self.cell_colorby_combo]:
            combo.blockSignals(False)

    def _cell_metadata_options_changed(self) -> None:
        if self.cell_layer is None:
            return
        label_col = self.cell_label_combo.currentText()
        color_col = self.cell_colorby_combo.currentText()
        self.cell_layer.label_column = None if label_col == NONE_LABEL else label_col
        self.cell_layer.color_column = None if color_col == SINGLE_COLOR_LABEL else color_col
        self._refresh_cell_actor(update_existing_only=False)
        self._update_slice_views()

    def _selected_cell_unit_code(self) -> str:
        label = self.cell_units_combo.currentText()
        return CELL_UNIT_OPTIONS.get(label, "um")

    def _convert_cell_coordinates(self, xyz: np.ndarray) -> tuple[np.ndarray, str]:
        if xyz.size == 0:
            return xyz, "empty"
        mode = self._selected_cell_unit_code()
        if mode == "um":
            return xyz.copy(), "microns"
        if mode == "mm":
            return xyz * 1000.0, "millimeters converted to microns x1000"
        if mode == "voxel":
            return xyz * np.array(self.resolution_um)[None, :], "voxel indices converted to microns"

        max_vals = np.nanmax(xyz, axis=0)
        shape_arr = np.array(self.shape, dtype=float)
        size_arr = np.array(self.size_um, dtype=float)
        if np.all(max_vals <= shape_arr + 5):
            return xyz * np.array(self.resolution_um)[None, :], "auto: voxel indices converted to microns"
        if np.all(max_vals < 30):
            return xyz * 1000.0, "auto: millimeters converted to microns x1000"
        if np.any(max_vals > size_arr * 1.25):
            return xyz.copy(), "auto: microns, some coordinates outside atlas bounds"
        return xyz.copy(), "auto: microns"

    def _apply_cell_units_to_loaded_cells(self) -> None:
        if self.cell_layer is None:
            return
        xyz, mode = self._convert_cell_coordinates(self.cell_layer.original_xyz)
        self.cell_layer.xyz = xyz
        self.cell_layer.coordinate_mode = mode
        self._refresh_cell_actor(update_existing_only=False)
        self._center_view_on_cells()
        self._update_status(f"Applied cell units: {mode}")
        self._refresh_scene()

    def _center_view_on_cells(self) -> None:
        if self.cell_layer is None or self.cell_layer.xyz.size == 0:
            return
        center = self.cell_layer.xyz.mean(axis=0)
        self.coronal_slider.setValue(self._um_to_index(center[0], 0))
        self.sagittal_slider.setValue(self._um_to_index(center[2], 2))

    def _refresh_cell_actor(self, update_existing_only: bool = False) -> None:
        if self.cell_layer is None:
            return
        if self.cell_layer.actor is not None:
            self.plotter.remove_actor(self.cell_layer.actor)
            self.cell_layer.actor = None
        elif update_existing_only:
            return
        pdata = pv.PolyData(self.cell_layer.xyz)
        color_col = self.cell_colorby_combo.currentText() if hasattr(self, "cell_colorby_combo") else SINGLE_COLOR_LABEL
        if color_col != SINGLE_COLOR_LABEL and color_col in self.cell_layer.dataframe.columns:
            values = pd.to_numeric(self.cell_layer.dataframe[color_col], errors="coerce").to_numpy(dtype=float)
            finite = np.isfinite(values)
            if np.any(finite):
                fill_value = float(np.nanmedian(values[finite]))
                values = np.where(finite, values, fill_value)
                pdata[color_col] = values
                self.cell_layer.color_column = color_col
                self.cell_layer.actor = self.plotter.add_mesh(
                    pdata,
                    scalars=color_col,
                    cmap="viridis",
                    point_size=self.cell_size_slider.value(),
                    render_points_as_spheres=True,
                    pickable=True,
                    name="cell_coordinates",
                    scalar_bar_args={"title": color_col},
                )
                return
        self.cell_layer.color_column = None
        self.cell_layer.actor = self.plotter.add_mesh(
            pdata,
            color=self.cell_layer.color,
            point_size=self.cell_size_slider.value(),
            render_points_as_spheres=True,
            pickable=True,
            name="cell_coordinates",
        )

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
            "x": ["x", "x_um", "atlas_x", "ap", "ap_um"],
            "y": ["y", "y_um", "atlas_y", "dv", "dv_um"],
            "z": ["z", "z_um", "atlas_z", "ml", "ml_um"],
        }
        found = []
        for axis in ["x", "y", "z"]:
            col = next((lower[a] for a in aliases[axis] if a in lower), None)
            if col is None:
                raise ValueError("Expected x/y/z columns or aliases x_um/y_um/z_um, atlas_x/atlas_y/atlas_z, ap/dv/ml")
            found.append(col)
        return found

    # ------------------------------------------------------------------
    # Buttons / saving
    # ------------------------------------------------------------------
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

    def _choose_mirror_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(QColor(self.mirror_color), self, "Choose mirror marker color")
        if color.isValid():
            self.mirror_color = color.name()
            self.mirror_color_button.setText(self.mirror_color)
            self.mirror_color_button.setStyleSheet(f"background-color: {self.mirror_color}; color: black;")
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
        self.cell_label_combo.clear()
        self.cell_label_combo.addItem(NONE_LABEL)
        self.cell_colorby_combo.clear()
        self.cell_colorby_combo.addItem(SINGLE_COLOR_LABEL)
        self._refresh_scene()

    def _save_active_roi(self) -> None:
        if not self.active_area:
            self._update_status("No active region loaded.")
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
            "mirror_color": self.mirror_color,
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
            out = self.cell_layer.dataframe.copy()
            n = min(len(out), self.cell_layer.xyz.shape[0])
            out = out.iloc[:n].copy()
            out["app_x_um"] = self.cell_layer.xyz[:n, 0]
            out["app_y_um"] = self.cell_layer.xyz[:n, 1]
            out["app_z_um"] = self.cell_layer.xyz[:n, 2]
            out.to_csv(cells_path, index=False)
            manifest["cells_file"] = str(cells_path)
            manifest["cell_coordinate_mode"] = self.cell_layer.coordinate_mode
            manifest["cell_units_dropdown"] = self.cell_units_combo.currentText()
            manifest["cell_label_column"] = self.cell_label_combo.currentText()
            manifest["cell_color_column"] = self.cell_colorby_combo.currentText()
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
