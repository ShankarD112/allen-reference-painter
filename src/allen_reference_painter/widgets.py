"""Small reusable Qt widget helpers."""

from __future__ import annotations

from qtpy import QtWidgets


def make_row(*widgets: QtWidgets.QWidget, stretch: bool = True) -> QtWidgets.QHBoxLayout:
    """Create a horizontal row layout from widgets."""
    row = QtWidgets.QHBoxLayout()
    for widget in widgets:
        row.addWidget(widget)
    if stretch:
        row.addStretch(1)
    return row


def set_fixed_height(*widgets: QtWidgets.QWidget, height: int = 32) -> None:
    """Apply consistent fixed/minimum height behavior to small controls."""
    for widget in widgets:
        widget.setMinimumHeight(height)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
