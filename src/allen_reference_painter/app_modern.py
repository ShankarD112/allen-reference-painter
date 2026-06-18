"""Modern sunset-themed launcher for Allen Reference Painter."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyvista as pv
from qtpy import QtCore, QtWidgets

from .app import MeshPainterWindow, NONE_LABEL, SINGLE_COLOR_LABEL

SCENE_TEXT_COLOR = "#fff7ef"
SCENE_BACKGROUND = "#0d0c0b"
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


class ModernMeshPainterWindow(MeshPainterWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Allen Brain Painter")
        self.setStyleSheet(SUNSET_STYLE)
        self.cell_label_actor = None
        self._modernize_existing_widgets()
        self._install_region_search_helpers()
        self._update_status("Modern sunset theme active. Top toolbar removed; use the existing in-panel controls.")

    def _modernize_existing_widgets(self) -> None:
        self.setMinimumSize(1450, 850)
        self._style_3d_scene_text()
        self.region_table.setStyleSheet("QTableWidget { border-radius: 12px; color: #fff7ef; }")
        self.region_table.setCornerButtonEnabled(False)
        self.region_table.setMinimumWidth(430)
        self.region_table.setMinimumHeight(250)
        for fig in [self.coronal_fig, self.sagittal_fig]:
            fig.patch.set_facecolor("#11100f")
        for widget in [self.region_search, self.region_picker, self.active_combo, self.cell_units_combo, self.cell_label_combo, self.cell_colorby_combo]:
            widget.setMinimumHeight(32)
            widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)

    def _style_3d_scene_text(self) -> None:
        try:
            self.plotter.set_background(SCENE_BACKGROUND)
            self.plotter.show_grid(
                color=SCENE_TEXT_COLOR,
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
        try:
            self.plotter.render()
        except Exception:
            pass

    def _load_reference_brain_shell(self) -> None:
        super()._load_reference_brain_shell()
        self._style_3d_scene_text()

    def _style_slice_axes(self, ax) -> None:
        ax.set_facecolor("#11100f")
        ax.xaxis.label.set_color(SCENE_TEXT_COLOR)
        ax.yaxis.label.set_color(SCENE_TEXT_COLOR)
        ax.tick_params(axis="both", colors=SCENE_TEXT_COLOR, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#6b4a3a")

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

    def _cell_metadata_options_changed(self) -> None:
        super()._cell_metadata_options_changed()
        self._refresh_cell_labels()

    def _apply_cell_units_to_loaded_cells(self) -> None:
        super()._apply_cell_units_to_loaded_cells()
        self._refresh_cell_labels()

    def _clear_cells(self) -> None:
        self._remove_cell_labels()
        super()._clear_cells()

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
            vals = pd.to_numeric(self.cell_layer.dataframe[color_col], errors="coerce").to_numpy(dtype=float)
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
                    scalar_bar_args={
                        "title": color_col,
                        "color": SCENE_TEXT_COLOR,
                        "title_font_size": 12,
                        "label_font_size": 10,
                        "fmt": "%.3g",
                    },
                )
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
        max_labels = 250
        xyz = self.cell_layer.xyz[:max_labels]
        labels = self.cell_layer.dataframe[label_col].astype(str).iloc[:max_labels].tolist()
        try:
            self.cell_label_actor = self.plotter.add_point_labels(
                xyz,
                labels,
                name="cell_name_labels",
                font_size=10,
                text_color=SCENE_TEXT_COLOR,
                point_color="#ff9f1c",
                point_size=3,
                shape_color="#211713",
                shape_opacity=0.55,
                always_visible=True,
                pickable=False,
                render_points_as_spheres=True,
            )
        except Exception:
            self.cell_label_actor = None

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
        try:
            iren = self.plotter.iren.interactor
            x, y = iren.GetEventPosition()
            picked_position = None
            if hasattr(self, "point_picker") and self.point_picker.Pick(x, y, 0, self.plotter.renderer):
                point_id = int(self.point_picker.GetPointId())
                if 0 <= point_id < self.cell_layer.xyz.shape[0]:
                    self._update_status(self._cell_status_text(point_id))
                    return
                picked_position = np.asarray(self.point_picker.GetPickPosition(), dtype=float)
            elif hasattr(self, "cell_picker") and self.cell_picker.Pick(x, y, 0, self.plotter.renderer):
                picked_position = np.asarray(self.cell_picker.GetPickPosition(), dtype=float)
            if picked_position is None or not np.all(np.isfinite(picked_position)):
                return
            distances = np.linalg.norm(self.cell_layer.xyz - picked_position[None, :], axis=1)
            nearest = int(np.argmin(distances))
            if distances[nearest] <= max_distance_um:
                self._update_status(self._cell_status_text(nearest))
            elif not quiet:
                self._update_status("No nearby cell found at click position.")
        except Exception:
            return


def main() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModernMeshPainterWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
