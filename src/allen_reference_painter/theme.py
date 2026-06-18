"""Theme constants and Qt stylesheets for Allen Reference Painter."""

from __future__ import annotations

SCENE_TEXT_COLOR = "#fff7ef"
SCENE_BACKGROUND = "#0b1020"
SCENE_GRID_COLOR = "#7c8aa5"
SCENE_LABEL_BACKGROUND = "#111827"
PAINT_COLOR = "#ff3333"
MIRROR_COLOR = "#00d7ff"
CELL_COLOR = "#00d7ff"
HEATMAP_CMAP = "inferno"

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
