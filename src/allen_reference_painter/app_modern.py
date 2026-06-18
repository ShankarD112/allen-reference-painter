"""
Modern sunset-themed launcher for Allen Reference Painter.

This wraps the main app with visual styling and a few UI behavior fixes without
removing the stable prototype in app.py.
"""

from __future__ import annotations

import numpy as np
from qtpy import QtCore, QtWidgets

from .app import MeshPainterWindow


SUNSET_STYLE = """
QMainWindow, QWidget {
    background-color: #11100f;
    color: #f4efe8;
    font-family: Segoe UI, Inter, Arial, sans-serif;
    font-size: 12px;
}
QLabel {
    color: #f4efe8;
}
QStatusBar {
    background: #171412;
    color: #f9c784;
    border-top: 1px solid #33261f;
}
QPushButton {
    background-color: #231b18;
    color: #f8efe7;
    border: 1px solid #4c352c;
    border-radius: 8px;
    padding: 7px 11px;
}
QPushButton:hover {
    background-color: #3a241d;
    border: 1px solid #ff9f1c;
}
QPushButton:pressed {
    background-color: #ff9f1c;
    color: #17100c;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #1b1715;
    color: #f8efe7;
    border: 1px solid #4a352d;
    border-radius: 8px;
    padding: 6px 9px;
    selection-background-color: #ff9f1c;
    selection-color: #1b100a;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #ff9f1c;
}
QComboBox QAbstractItemView {
    background-color: #1b1715;
    color: #f8efe7;
    border: 1px solid #4a352d;
    selection-background-color: #ff9f1c;
    selection-color: #1b100a;
    outline: 0;
}
QTableWidget {
    background-color: #151311;
    alternate-background-color: #1c1714;
    color: #f8efe7;
    gridline-color: #39271f;
    border: 1px solid #33261f;
    border-radius: 10px;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background-color: #221a16;
    color: #ffcf99;
    border: 0px;
    border-right: 1px solid #39271f;
    padding: 7px;
    font-weight: 600;
}
QCheckBox {
    spacing: 7px;
    color: #f4efe8;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1px solid #6b4a3a;
    background-color: #171412;
}
QCheckBox::indicator:checked {
    background-color: #ff9f1c;
    border: 1px solid #ffb85c;
}
QSlider::groove:horizontal {
    height: 5px;
    background: #35251f;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #ff9f1c;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: #ffe0b2;
    border: 1px solid #ff9f1c;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background: #171412;
    border: none;
    width: 10px;
    height: 10px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #6b4a3a;
    border-radius: 5px;
}
QScrollBar::handle:hover {
    background: #ff9f1c;
}
QGroupBox {
    border: 1px solid #33261f;
    border-radius: 10px;
    margin-top: 10px;
    padding: 8px;
    color: #ffcf99;
}
"""


class ModernMeshPainterWindow(MeshPainterWindow):
    """Small UI/behavior refinement layer over the main prototype."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Allen Brain Painter")
        self.setStyleSheet(SUNSET_STYLE)
        self._modernize_existing_widgets()
        self._install_region_search_helpers()
        self._update_status("Modern sunset theme active. Type a region acronym/name and press Enter or Load selected region.")

    def _modernize_existing_widgets(self) -> None:
        # Keep the app copyright-safe: text title only, no icon/logo assets.
        self.plotter.set_background("#0d0c0b")
        try:
            self.region_table.setStyleSheet("QTableWidget { border-radius: 12px; }")
            self.region_table.setCornerButtonEnabled(False)
        except Exception:
            pass
        try:
            for fig in [self.coronal_fig, self.sagittal_fig]:
                fig.patch.set_facecolor("#11100f")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Search/dropdown behavior
    # ------------------------------------------------------------------
    def _install_region_search_helpers(self) -> None:
        labels = self.all_region_labels
        completer = QtWidgets.QCompleter(labels, self)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self.region_search.setCompleter(completer)
        self.region_search.returnPressed.connect(self._load_selected_region)
        self.region_search.textChanged.connect(self._sync_dropdown_to_search_text)
        self._sync_dropdown_to_search_text(self.region_search.text())

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
        query = text.strip()
        if not query:
            return None
        query_lower = query.lower()
        # Exact acronym is highest priority.
        for acronym in self.structure_index:
            if acronym.lower() == query_lower:
                return acronym
        # Then exact displayed label or first substring match.
        for label in self.all_region_labels:
            acronym, name = label.split(" - ", 1)
            if label.lower() == query_lower or name.lower() == query_lower:
                return acronym
        for label in self.all_region_labels:
            if query_lower in label.lower():
                return label.split(" - ", 1)[0]
        return None

    def _load_selected_region(self) -> None:
        acronym = self._resolve_region_from_text(self.region_search.text())
        if acronym is None:
            text = self.region_picker.currentText()
            acronym = text.split(" - ", 1)[0] if text else None
        if not acronym:
            self._update_status("No matching Allen region found. Try an acronym like ENT, CA1, SUB, PERI.")
            return
        if self._load_region(acronym, make_active=True):
            self._refresh_controls()
            self._refresh_scene()
            self.plotter.reset_camera()
            self._update_status(f"Loaded {acronym}. Search box and dropdown are synced.")

    # ------------------------------------------------------------------
    # More reliable cell hover/status behavior
    # ------------------------------------------------------------------
    def _update_hovered_cell_status(self) -> None:
        if self.cell_layer is None or self.cell_layer.xyz.size == 0:
            return
        try:
            iren = self.plotter.iren.interactor
            x, y = iren.GetEventPosition()

            picked = False
            picked_position = None
            point_id = -1
            if hasattr(self, "point_picker"):
                picked = bool(self.point_picker.Pick(x, y, 0, self.plotter.renderer))
                if picked:
                    point_id = int(self.point_picker.GetPointId())
                    picked_position = np.asarray(self.point_picker.GetPickPosition(), dtype=float)

            if 0 <= point_id < self.cell_layer.xyz.shape[0]:
                self._update_status(self._cell_status_text(point_id))
                return

            if picked_position is None or not np.all(np.isfinite(picked_position)):
                return

            distances = np.linalg.norm(self.cell_layer.xyz - picked_position[None, :], axis=1)
            nearest = int(np.argmin(distances))
            # A permissive atlas-space threshold because screen-space picking in VTK
            # can miss small rendered spheres. This still avoids constantly changing
            # the status bar when the cursor is far away from cells.
            if distances[nearest] <= 500:
                self._update_status(self._cell_status_text(nearest))
        except Exception:
            return

    def _refresh_cell_actor(self, update_existing_only: bool = False) -> None:
        super()._refresh_cell_actor(update_existing_only=update_existing_only)
        # Restrict the point picker to the cell actor when possible. This makes
        # hover status much more reliable than picking against every mesh/plane.
        try:
            if self.cell_layer is not None and self.cell_layer.actor is not None and hasattr(self, "point_picker"):
                self.point_picker.InitializePickList()
                self.point_picker.AddPickList(self.cell_layer.actor)
                self.point_picker.PickFromListOn()
        except Exception:
            pass


def main() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModernMeshPainterWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
