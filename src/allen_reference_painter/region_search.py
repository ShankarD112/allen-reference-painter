"""Pre-indexed literal region search; explicit selection owns loading."""
from qtpy import QtCore


def normalize(text):
    return ' '.join(text.casefold().split())


def rank_regions(entries, query):
    query = normalize(query)
    tokens = query.split()
    matches = [e for e in entries if all(t in e[2] for t in tokens)]
    return sorted(matches, key=lambda e: (
        0 if e[1] == query else 1 if e[1].startswith(query) else 2,
        0 if e[3].startswith(query) else 1, e[1]))


class RegionSearchModel(QtCore.QAbstractListModel):
    def __init__(self, labels, parent=None):
        super().__init__(parent)
        self.entries = [(label, normalize(label.split(' - ', 1)[0]), normalize(label),
                         normalize(label.partition(' - ')[2])) for label in labels]
        self.query = None
        self.matches = []

    def search(self, query):
        query = normalize(query)
        if query == self.query:
            return False
        matches = rank_regions(self.entries, query)
        self.beginResetModel()
        self.query, self.matches = query, matches
        self.endResetModel()
        return True

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.matches)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.matches):
            return None
        label = self.matches[index.row()][0]
        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.ToolTipRole):
            return label
        if role == QtCore.Qt.UserRole:
            return label.split(' - ', 1)[0]
