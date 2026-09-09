import unittest
import numpy as np
import pandas as pd
from qtpy import QtCore
from allen_reference_painter.cell_table import CellTableModel

class TableTests(unittest.TestCase):
    def test_filter_bulk_selection_and_source_row_mapping(self):
        model=CellTableModel(pd.DataFrame({'Name':['A','B','A2'],'Tau':[1,2,3]}),np.ones(3,dtype=bool))
        model.filter('A')
        model.select_filtered(False)
        self.assertEqual(model.selection.tolist(),[False,True,False])
        model.setData(model.index(1,0),QtCore.Qt.Checked,QtCore.Qt.CheckStateRole)
        self.assertEqual(model.selection.tolist(),[False,True,True])
        self.assertEqual(model.data(model.index(1,1)),'A2')
        model.filter('[')
        self.assertEqual(model.rowCount(),0)
        model.select_filtered(True)
        self.assertEqual(model.selection.tolist(),[False,True,True])
