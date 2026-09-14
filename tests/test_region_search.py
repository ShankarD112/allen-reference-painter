import unittest
from qtpy import QtCore
from allen_reference_painter.region_search import RegionSearchModel


class RegionSearchTests(unittest.TestCase):
    def setUp(self):
        self.model = RegionSearchModel(['ENTl - Entorhinal area lateral',
            'ENT - Entorhinal area', 'ENTm - Entorhinal area medial',
            'CA1 - Field CA1'])

    def test_exact_acronym_before_children(self):
        self.model.search(' ent ')
        self.assertEqual(self.model.index(0, 0).data(QtCore.Qt.UserRole), 'ENT')
        self.assertEqual(self.model.rowCount(), 3)

    def test_multiword_case_insensitive(self):
        self.model.search('LATERAL   entorhinal')
        self.assertEqual(self.model.rowCount(), 1)
        self.assertEqual(self.model.index(0, 0).data(QtCore.Qt.UserRole), 'ENTl')

    def test_identical_search_does_not_reset_selection(self):
        self.assertTrue(self.model.search('ENT'))
        index = QtCore.QPersistentModelIndex(self.model.index(2, 0))
        self.assertFalse(self.model.search(' ent '))
        self.assertTrue(index.isValid())
        self.assertEqual(index.data(QtCore.Qt.UserRole), 'ENTm')

    def test_no_matches_and_no_250_result_cap(self):
        self.model.search('[')
        self.assertEqual(self.model.rowCount(), 0)
        model = RegionSearchModel([f'R{i} - Region {i}' for i in range(1000)])
        model.search('region')
        self.assertEqual(model.rowCount(), 1000)
