"""Modern sunset-themed launcher for Allen Reference Painter."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyvista as pv
from qtpy import QtCore, QtWidgets

from .app import MeshPainterWindow, NONE_LABEL, SINGLE_COLOR_LABEL

SCENE_TEXT_COLOR = "#fff7ef"
SCENE_BACKGROUND = "#0b1020"
SCENE_GRID_COLOR = "#7c8aa5"
SUNSET_STYLE = """
QMainWindow, QWidget { background-color: #11100f; color: #f7f1eb; font-family: Segoe UI, Inter, Arial, sans-serif; font-size: 12px; }
QLabel { color: #f7f1eb; }
QStatusBar { background: #171412; color: #ffcf99; border-top: 1px solid #33261f; }
QPushButton { background-color: #231b18; color: #fff4e8; border: 1px solid #4c352c; border-radius: 8px; padding: 7px 11px; }
QPushButton:hover { background-color: #3a241d; border: 1px solid #ff9f1c; }
QPushButton:pressed { background-color: #ff9f1c; color: #17100c; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background-color: #1b1715; color: #fff7ef; border: 1px solid #4a352d; border-radius: 8px; padding: 6px 9px; selection-background-color: #ff9f1c; selection-color: #1b100a; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #ff9f1c; }
QComboBox QAbstractItemView { background-color: #1b1715; color: #fff7ef; border: 1px solid #4a352d; selection-background-color: #ff9f1c; selection-color: #1b100a; outline: 0; }
QTableWidget { background-color: #151311; alternate-background-color: #1c1714; color: #fff7ef; gridline-color: #39271f; border: 1px solid #33261f; border-radius: 10px; }
QTableWidget::item { color: #fff7ef; padding: 6px; }
QTableWidget::item:selected { background-color: #5a3424; color: #ffffff; }
QHeaderView::section { background-color: #221a16; color: #ffcf99; border: 0px; border-right: 1px solid #39271f; padding: 7px; font-weight: 600; }
QCheckBox { spacing: 7px; color: #f7f1eb; }
QCheckBox::indicator { width: 17px; height: 17px; border-radius: 5px; border: 1px solid #6b4a3a; background-color: #171412; }
QCheckBox::indicator:checked { background-color: #ff9f1c; border: 1px solid #ffb85c; }
QSlider::groove:horizontal { height: 5px; background: #35251f; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #ff9f1c; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; background: #ffe0b2; border: 1px solid #ff9f1c; }
QScrollBar:vertical, QScrollBar:horizontal { background: #171412; border: none; width: 10px; height: 10px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #6b4a3a; border-radius: 5px; }
QScrollBar::handle:hover { background: #ff9f1c; }
"""


class CellTableDialog(QtWidgets.QDialog):
    """Table popup for selecting which imported cells are visible."""

    def __init__(self, dataframe: pd.DataFrame, selection_mask: np.ndarray, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Imported Cell Table")
        self.resize(1150, 650)
        self.dataframe = dataframe.reset_index(drop=True)
        self.selection_mask = selection_mask.astype(bool).copy()
        layout = QtWidgets.QVBoxLayout(self)

        controls = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Filter visible rows by text, e.g. Aug012024IR3a")
        self.search.textChanged.connect(self._populate)
        controls.addWidget(self.search, stretch=1)
        select_all = QtWidgets.QPushButton("Select all")
        select_all.clicked.connect(lambda: self._set_all(True))
        controls.addWidget(select_all)
        deselect_all = QtWidgets.QPushButton("Deselect all")
        deselect_all.clicked.connect(lambda: self._set_all(False))
        controls.addWidget(deselect_all)
        layout.addLayout(controls)

        self.table = QtWidgets.QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        layout.addWidget(self.table, stretch=1)

        bottom = QtWidgets.QHBoxLayout()
        self.count_label = QtWidgets.QLabel("")
        bottom.addWidget(self.count_label)
        bottom.addStretch(1)
        apply_button = QtWidgets.QPushButton("Apply selection")
        apply_button.clicked.connect(self.accept)
        bottom.addWidget(apply_button)
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        bottom.addWidget(cancel_button)
        layout.addLayout(bottom)
        self._populate()

    def _matching_indices(self) -> list[int]:
        query = self.search.text().strip().lower()
        if not query:
            return list(range(len(self.dataframe)))
        text = self.dataframe.astype(str).agg(" ".join, axis=1).str.lower()
        return list(np.where(text.str.contains(query, regex=False).to_numpy())[0])

    def _populate(self) -> None:
        idxs = self._matching_indices()
        cols = list(self.dataframe.columns)
        self.table.blockSignals(True)
        self.table.clear()
        self.table.setRowCount(len(idxs))
        self.table.setColumnCount(len(cols) + 2)
        self.table.setHorizontalHeaderLabels(["Show", "#"] + [str(c) for c in cols])
        for r, idx in enumerate(idxs):
            show_item = QtWidgets.QTableWidgetItem()
            show_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            show_item.setCheckState(QtCore.Qt.Checked if self.selection_mask[idx] else QtCore.Qt.Unchecked)
            show_item.setData(QtCore.Qt.UserRole, int(idx))
            self.table.setItem(r, 0, show_item)
            idx_item = QtWidgets.QTableWidgetItem(str(idx + 1))
            idx_item.setData(QtCore.Qt.UserRole, int(idx))
            self.table.setItem(r, 1, idx_item)
            for c, col in enumerate(cols, start=2):
                value = self.dataframe.iloc[idx][col]
                self.table.setItem(r, c, QtWidgets.QTableWidgetItem(str(value)))
        self.table.itemChanged.connect(self._item_changed)
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        self._update_count_label()

    def _item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        idx = item.data(QtCore.Qt.UserRole)
        if idx is not None:
            self.selection_mask[int(idx)] = item.checkState() == QtCore.Qt.Checked
            self._update_count_label()

    def _set_all(self, state: bool) -> None:
        idxs = self._matching_indices()
        self.selection_mask[idxs] = state
        self._populate()

    def _update_count_label(self) -> None:
        self.count_label.setText(f"Showing {int(self.selection_mask.sum())} of {len(self.selection_mask)} cells")


class ModernMeshPainterWindow(MeshPainterWindow):
    def __init__(self) -> None:
        self.cell_selection_mask = None
        self.visible_cell_indices = None
        super().__init__()
        self.setWindowTitle("Allen Brain Painter")
        self.setStyleSheet(SUNSET_STYLE)
        self.cell_label_actor = None
        self._modernize_existing_widgets()
        self._install_region_search_helpers()
        self._add_view_cell_table_button()
        self._update_status("Modern sunset theme active. The 3D scene uses a midnight-blue background and compact heat legend.")

    def _modernize_existing_widgets(self) -> None:
        self.setMinimumSize(1450, 850)
        self._style_3d_scene_text()
        self.region_table.setStyleSheet("QTableWidget { border-radius: 12px; color: #fff7ef; }")
        self.region_table.setCornerButtonEnabled(False)
        self.region_table.setMinimumWidth(430)
        self.region_table.setMinimumHeight(250)
        for fig in [self.coronal_fig, self.sagittal_fig]:
            fig.patch.set_facecolor(SCENE_BACKGROUND)
        for widget in [self.region_search, self.region_picker, self.active_combo, self.cell_units_combo, self.cell_label_combo, self.cell_colorby_combo]:
            widget.setMinimumHeight(32)
            widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)

    def _add_view_cell_table_button(self) -> None:
        self.view_cell_table_button = QtWidgets.QPushButton("View cell table")
        self.view_cell_table_button.clicked.connect(self._show_cell_table_dialog)
        self.view_cell_table_button.setEnabled(False)
        parent = self.load_cells_button.parentWidget()
        layout = parent.layout() if parent is not None else None
        inserted = False
        if layout is not None:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                row_layout = item.layout()
                if row_layout is None:
                    continue
                for j in range(row_layout.count()):
                    if row_layout.itemAt(j).widget() is self.clear_cells_button:
                        row_layout.insertWidget(j + 1, self.view_cell_table_button)
                        inserted = True
                        break
                if inserted:
                    break
        if not inserted:
            self.statusBar().addPermanentWidget(self.view_cell_table_button)

    def _style_3d_scene_text(self) -> None:
        try:
            self.plotter.set_background(SCENE_BACKGROUND)
            self.plotter.show_grid(
                color=SCENE_GRID_COLOR,
                font_size=8,
                grid="back",
                location="outer",
                xlabel="X / AP (um)",
                ylabel="Y / DV (um)",
                zlabel="Z / ML (um)",
            )
        except Exception:
            pass
        try:
            self.plotter.add_axes(line_width=2, color=SCENE_TEXT_COLOR)
        except Exception:
            pass
        self._force_scalar_bar_text_light()
        try:
            self.plotter.render()
        except Exception:
            pass

    def _force_scalar_bar_text_light(self) -> None:
        try:
            scalar_bars = getattr(self.plotter, "scalar_bars", {})
            actors = list(scalar_bars.values()) if hasattr(scalar_bars, "values") else []
            for actor in actors:
                for getter in ["GetTitleTextProperty", "GetLabelTextProperty", "GetAnnotationTextProperty"]:
                    if hasattr(actor, getter):
                        prop = getattr(actor, getter)()
                        prop.SetColor(1.0, 0.97, 0.94)
                        prop.SetOpacity(1.0)
                        prop.BoldOn()
                if hasattr(actor, "SetOrientationToHorizontal"):
                    actor.SetOrientationToHorizontal()
                if hasattr(actor, "SetPosition"):
                    actor.SetPosition(0.58, 0.055)
                if hasattr(actor, "SetWidth"):
                    actor.SetWidth(0.34)
                if hasattr(actor, "SetHeight"):
                    actor.SetHeight(0.055)
                if hasattr(actor, "SetMaximumNumberOfColors"):
                    actor.SetMaximumNumberOfColors(96)
                if hasattr(actor, "Modified"):
                    actor.Modified()
        except Exception:
            pass

    def _load_reference_brain_shell(self) -> None:
        super()._load_reference_brain_shell()
        self._style_3d_scene_text()

    def _style_slice_axes(self, ax) -> None:
        ax.set_facecolor(SCENE_BACKGROUND)
        ax.xaxis.label.set_color(SCENE_TEXT_COLOR)
        ax.yaxis.label.set_color(SCENE_TEXT_COLOR)
        ax.tick_params(axis="both", colors=SCENE_TEXT_COLOR, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#7c8aa5")

    def _plot_coronal(self) -> None:
        super()._plot_coronal()
        try:
            ax = self.coronal_fig.axes[0]
            self._style_slice_axes(ax)
            self.coronal_canvas.draw_idle()
        except Exception:
            pass

    def _plot_sagittal(self) -> None:
        super()._plot_sagittal()
        try:
            ax = self.sagittal_fig.axes[0]
            self._style_slice_axes(ax)
            self.sagittal_canvas.draw_idle()
        except Exception:
            pass

    def _install_region_search_helpers(self) -> None:
        completer = QtWidgets.QCompleter(self.all_region_labels, self)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self.region_search.setCompleter(completer)
        self.region_search.returnPressed.connect(self._load_selected_region)
        self.region_search.textChanged.connect(self._sync_dropdown_to_search_text)

    def _sync_dropdown_to_search_text(self, text: str) -> None:
        query = text.strip().lower()
        if not query:
            return
        for i in range(self.region_picker.count()):
            item = self.region_picker.itemText(i)
            acronym = item.split(" - ", 1)[0].lower()
            if acronym == query or query in item.lower():
                self.region_picker.setCurrentIndex(i)
                return

    def _resolve_region_from_text(self, text: str) -> str | None:
        query = text.strip().lower()
        if not query:
            return None
        for acronym in self.structure_index:
            if acronym.lower() == query:
                return acronym
        for label in self.all_region_labels:
            if query in label.lower():
                return label.split(" - ", 1)[0]
        return None

    def _load_selected_region(self) -> None:
        acronym = self._resolve_region_from_text(self.region_search.text())
        if acronym is None:
            text = self.region_picker.currentText()
            acronym = text.split(" - ", 1)[0] if text else None
        if not acronym:
            self._update_status("No matching Allen region found. Try ENT, CA1, SUB, PERI, etc.")
            return
        if self._load_region(acronym, make_active=True):
            self._refresh_controls()
            self._refresh_scene()
            self._style_3d_scene_text()
            self.plotter.reset_camera()
            self._update_status(f"Loaded {acronym}.")

    def _compact_scalar_bar_args(self, title: str) -> dict:
        return {
            "title": title,
            "color": SCENE_TEXT_COLOR,
            "title_font_size": 10,
            "label_font_size": 8,
            "fmt": "%.3g",
            "n_labels": 4,
            "vertical": False,
            "position_x": 0.58,
            "position_y": 0.055,
            "width": 0.34,
            "height": 0.055,
        }

    def _load_cells_dialog(self) -> None:
        super()._load_cells_dialog()
        if self.cell_layer is not None:
            self.cell_selection_mask = np.ones(len(self.cell_layer.dataframe), dtype=bool)
            self.visible_cell_indices = np.arange(len(self.cell_layer.dataframe))
            self.view_cell_table_button.setEnabled(True)
            self._refresh_cell_actor(update_existing_only=False)
            self._force_scalar_bar_text_light()

    def _show_cell_table_dialog(self) -> None:
        if self.cell_layer is None:
            self._update_status("Load a cell file first.")
            return
        if self.cell_selection_mask is None or len(self.cell_selection_mask) != len(self.cell_layer.dataframe):
            self.cell_selection_mask = np.ones(len(self.cell_layer.dataframe), dtype=bool)
        dialog = CellTableDialog(self.cell_layer.dataframe, self.cell_selection_mask, self)
        dialog.setStyleSheet(SUNSET_STYLE)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.cell_selection_mask = dialog.selection_mask.copy()
            self._refresh_cell_actor(update_existing_only=False)
            self._update_slice_views()
            self._update_status(f"Cell selection applied: {int(self.cell_selection_mask.sum())} of {len(self.cell_selection_mask)} cells visible.")

    def _selected_cell_indices(self) -> np.ndarray:
        if self.cell_layer is None:
            return np.array([], dtype=int)
        n = len(self.cell_layer.dataframe)
        if self.cell_selection_mask is None or len(self.cell_selection_mask) != n:
            self.cell_selection_mask = np.ones(n, dtype=bool)
        return np.where(self.cell_selection_mask)[0]

    def _cell_metadata_options_changed(self) -> None:
        super()._cell_metadata_options_changed()
        self._refresh_cell_labels()
        self._force_scalar_bar_text_light()

    def _apply_cell_units_to_loaded_cells(self) -> None:
        super()._apply_cell_units_to_loaded_cells()
        if self.cell_layer is not None:
            self.cell_selection_mask = np.ones(len(self.cell_layer.dataframe), dtype=bool)
            self.visible_cell_indices = np.arange(len(self.cell_layer.dataframe))
        self._refresh_cell_labels()
        self._force_scalar_bar_text_light()

    def _clear_cells(self) -> None:
        self._remove_cell_labels()
        self.cell_selection_mask = None
        self.visible_cell_indices = None
        if hasattr(self, "view_cell_table_button"):
            self.view_cell_table_button.setEnabled(False)
        super()._clear_cells()

    def _refresh_cell_actor(self, update_existing_only: bool = False) -> None:
        if self.cell_layer is None:
            return
        if self.cell_layer.actor is not None:
            self.plotter.remove_actor(self.cell_layer.actor)
            self.cell_layer.actor = None
        elif update_existing_only:
            return

        idx = self._selected_cell_indices()
        self.visible_cell_indices = idx
        if len(idx) == 0:
            self._remove_cell_labels()
            self._style_3d_scene_text()
            return

        pdata = pv.PolyData(self.cell_layer.xyz[idx])
        df_vis = self.cell_layer.dataframe.iloc[idx].reset_index(drop=True)
        color_col = self.cell_colorby_combo.currentText() if hasattr(self, "cell_colorby_combo") else SINGLE_COLOR_LABEL
        if color_col != SINGLE_COLOR_LABEL and color_col in df_vis.columns:
            vals = pd.to_numeric(df_vis[color_col], errors="coerce").to_numpy(dtype=float)
            finite = np.isfinite(vals)
            if np.any(finite):
                vals = np.where(finite, vals, float(np.nanmedian(vals[finite])))
                pdata[color_col] = vals
                self.cell_layer.color_column = color_col
                self.cell_layer.actor = self.plotter.add_mesh(
                    pdata,
                    scalars=color_col,
                    cmap="inferno",
                    point_size=self.cell_size_slider.value(),
                    render_points_as_spheres=True,
                    pickable=True,
                    name="cell_coordinates",
                    scalar_bar_args=self._compact_scalar_bar_args(color_col),
                )
                self._force_scalar_bar_text_light()
            else:
                self.cell_layer.actor = None
        if self.cell_layer.actor is None:
            self.cell_layer.color_column = None
            self.cell_layer.actor = self.plotter.add_mesh(
                pdata,
                color=self.cell_layer.color,
                point_size=self.cell_size_slider.value(),
                render_points_as_spheres=True,
                pickable=True,
                name="cell_coordinates",
            )
        try:
            if self.cell_layer.actor is not None and hasattr(self, "point_picker"):
                self.point_picker.InitializePickList()
                self.point_picker.AddPickList(self.cell_layer.actor)
                self.point_picker.PickFromListOn()
        except Exception:
            pass
        self._refresh_cell_labels()
        self._style_3d_scene_text()
        self._force_scalar_bar_text_light()

    def _remove_cell_labels(self) -> None:
        try:
            self.plotter.remove_actor("cell_name_labels")
        except Exception:
            pass
        self.cell_label_actor = None

    def _refresh_cell_labels(self) -> None:
        self._remove_cell_labels()
        if self.cell_layer is None or self.cell_layer.xyz.size == 0:
            return
        label_col = self.cell_label_combo.currentText() if hasattr(self, "cell_label_combo") else NONE_LABEL
        if label_col == NONE_LABEL or label_col not in self.cell_layer.dataframe.columns:
            return
        idx = self._selected_cell_indices()[:250]
        if len(idx) == 0:
            return
        xyz = self.cell_layer.xyz[idx]
        labels = self.cell_layer.dataframe.iloc[idx][label_col].astype(str).tolist()
        try:
            self.cell_label_actor = self.plotter.add_point_labels(
                xyz,
                labels,
                name="cell_name_labels",
                font_size=10,
                text_color=SCENE_TEXT_COLOR,
                point_color="#ff9f1c",
                point_size=3,
                shape_color="#111827",
                shape_opacity=0.55,
                always_visible=True,
                pickable=False,
                render_points_as_spheres=True,
            )
        except Exception:
            self.cell_label_actor = None

    def _cell_status_text(self, point_id: int) -> str:
        if self.cell_layer is None:
            return ""
        if self.visible_cell_indices is not None and 0 <= point_id < len(self.visible_cell_indices):
            point_id = int(self.visible_cell_indices[point_id])
        row = self.cell_layer.dataframe.iloc[point_id]
        label_col = self.cell_label_combo.currentText() if hasattr(self, "cell_label_combo") else NONE_LABEL
        label = ""
        if label_col != NONE_LABEL and label_col in self.cell_layer.dataframe.columns:
            label = f"{label_col}: {row[label_col]} | "
        color_col = self.cell_colorby_combo.currentText() if hasattr(self, "cell_colorby_combo") else SINGLE_COLOR_LABEL
        color_txt = ""
        if color_col != SINGLE_COLOR_LABEL and color_col in self.cell_layer.dataframe.columns:
            color_txt = f" | {color_col}: {row[color_col]}"
        x, y, z = self.cell_layer.xyz[point_id]
        return f"Cell {point_id + 1} | {label}x/y/z um: {x:.1f}, {y:.1f}, {z:.1f}{color_txt}"

    def _on_left_press(self, obj, event) -> None:
        if self.active_area and self.active_area in self.regions:
            return super()._on_left_press(obj, event)
        self._show_nearest_cell_from_mouse(max_distance_um=800)

    def _on_mouse_move(self, obj, event) -> None:
        if self.mouse_down and self.continuous_checkbox.isChecked():
            return super()._on_mouse_move(obj, event)
        self._show_nearest_cell_from_mouse(max_distance_um=450, quiet=True)

    def _show_nearest_cell_from_mouse(self, max_distance_um: float = 500, quiet: bool = False) -> None:
        if self.cell_layer is None or self.cell_layer.xyz.size == 0:
            return
        idx = self._selected_cell_indices()
        if len(idx) == 0:
            return
        try:
            iren = self.plotter.iren.interactor
            x, y = iren.GetEventPosition()
            picked_position = None
            if hasattr(self, "point_picker") and self.point_picker.Pick(x, y, 0, self.plotter.renderer):
                point_id = int(self.point_picker.GetPointId())
                if 0 <= point_id < len(idx):
                    self._update_status(self._cell_status_text(point_id))
                    return
                picked_position = np.asarray(self.point_picker.GetPickPosition(), dtype=float)
            elif hasattr(self, "cell_picker") and self.cell_picker.Pick(x, y, 0, self.plotter.renderer):
                picked_position = np.asarray(self.cell_picker.GetPickPosition(), dtype=float)
            if picked_position is None or not np.all(np.isfinite(picked_position)):
                return
            distances = np.linalg.norm(self.cell_layer.xyz[idx] - picked_position[None, :], axis=1)
            nearest_visible = int(np.argmin(distances))
            if distances[nearest_visible] <= max_distance_um:
                self._update_status(self._cell_status_text(nearest_visible))
            elif not quiet:
                self._update_status("No nearby visible cell found at click position.")
        except Exception:
            return


def main() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModernMeshPainterWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
