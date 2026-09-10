"""Virtual cell table: instantiate only visible table cells, not N×M widgets."""
import numpy as np
from qtpy import QtCore, QtWidgets

class CellTableModel(QtCore.QAbstractTableModel):
    def __init__(self, dataframe, selection, parent=None):
        super().__init__(parent)
        self.frame = dataframe
        self.selection = np.asarray(selection, dtype=bool).copy()
        self.rows = np.arange(len(dataframe))
        self.search_text = dataframe.astype(str).agg(' '.join, axis=1).str.casefold()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.frame.columns) + 1

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        row, col = int(self.rows[index.row()]), index.column()
        if col == 0 and role == QtCore.Qt.CheckStateRole:
            return QtCore.Qt.Checked if self.selection[row] else QtCore.Qt.Unchecked
        if col > 0 and role == QtCore.Qt.DisplayRole:
            return str(self.frame.iat[row, col - 1])
        return None

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return 'Show' if section == 0 else str(self.frame.columns[section-1])
            return str(int(self.rows[section]) + 1)

    def flags(self, index):
        flags = super().flags(index)
        return flags | QtCore.Qt.ItemIsUserCheckable if index.column() == 0 else flags

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if index.isValid() and index.column() == 0 and role == QtCore.Qt.CheckStateRole:
            self.selection[self.rows[index.row()]] = value in (QtCore.Qt.Checked, QtCore.Qt.Checked.value)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def filter(self, query):
        self.beginResetModel()
        self.rows = np.flatnonzero(self.search_text.str.contains(query.casefold(), regex=False).to_numpy())
        self.endResetModel()

    def select_filtered(self, state):
        self.selection[self.rows] = state
        if len(self.rows):
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows)-1, 0), [QtCore.Qt.CheckStateRole])

class CellTableDialog(QtWidgets.QDialog):
    def __init__(self, dataframe, selection_mask, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Choose visible cells')
        self.resize(960, 640)
        layout = QtWidgets.QVBoxLayout(self)
        search = QtWidgets.QLineEdit(placeholderText='Filter any column…')
        layout.addWidget(search)
        self.model = CellTableModel(dataframe, selection_mask, self)
        table = QtWidgets.QTableView()
        table.setModel(self.model)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)
        self.count = QtWidgets.QLabel()
        layout.addWidget(self.count)
        row = QtWidgets.QHBoxLayout()
        for label, state in [('Show filtered', True), ('Hide filtered', False)]:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _=False, s=state: self.model.select_filtered(s))
            row.addWidget(button)
        layout.addLayout(row)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        search.textChanged.connect(lambda _: self.timer.start())
        self.timer.timeout.connect(lambda: self.model.filter(search.text()))
        self.model.dataChanged.connect(self._count)
        self.model.modelReset.connect(self._count)
        self._count()

    def _count(self, *args):
        self.count.setText(f'{self.model.selection.sum():,} / {len(self.model.selection):,} visible • {len(self.model.rows):,} matching rows')

    @property
    def selection_mask(self):
        return self.model.selection
