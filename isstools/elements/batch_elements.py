import numpy as np
from isstools.resources import resource_path
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.Qt import QObject
import copy

from functools import lru_cache


@lru_cache(maxsize=4)
def _batch_icon(kind):
    # Construct icons only when a GUI item is created, after QApplication exists.
    return QtGui.QIcon(resource_path(f'icons/{kind}.png'))


def _create_batch_experiment(experiment_name, experiment_rep, model=None):
    item_name = 'Batch experiment "{}" repeat {} times'.format(experiment_name, experiment_rep)
    item = QtGui.QStandardItem(item_name)
    item.name = item_name
    item.setEditable(False)
    item.setDropEnabled(True)
    item.item_type = 'experiment'
    item.repeat = experiment_rep
    item.setIcon(_batch_icon('experiment'))
    if model:
        parent = model.invisibleRootItem()
        parent.appendRow(item)
    else:
        return item


def _create_new_sample(sample_name, sample_comment, sample_x, sample_y, sample_z, sample_th, model=None, setCheckable=True):
    item = QtGui.QStandardItem(f'{sample_name} at X {sample_x :0.2f} Y {sample_y :0.2f} Z {sample_z :0.2f} Th {sample_th :0.2f}')
    item.setDropEnabled(False)
    item.item_type = 'sample'
    if setCheckable:
        item.setCheckable(True)
    item.setEditable(False)
    item.x = sample_x
    item.y = sample_y
    item.z = sample_z
    item.th = sample_th
    item.name = sample_name
    item.comment = sample_comment
    item.setIcon(_batch_icon('sample'))
    if model:
        parent = model.invisibleRootItem()
        parent.appendRow(item)
    else:
        return item


def _create_new_scan(scan_name, scan_type, scan_traj, scan_repeat, scan_delay, scan_autofoil, model=None, setCheckable=True):
    item = QtGui.QStandardItem(f'{scan_type} with {scan_name}, {scan_repeat} times with {scan_delay} s delay')
    item.setDropEnabled(False)
    item.item_type = 'scan'
    item.scan_type = scan_type
    item.trajectory = scan_traj
    item.repeat = scan_repeat
    item.name = scan_name
    item.delay = scan_delay
    item.autofoil = scan_autofoil
    if setCheckable:
        item.setCheckable(True)
    item.setEditable(False)
    item.setIcon(_batch_icon('scan'))
    if model:
        parent = model.invisibleRootItem()
        parent.appendRow(item)
    else:
        return item


def _create_service_item(name, service_plan, service_params):
    item = QtGui.QStandardItem(f'Service: {name}')
    item.item_type = 'service'
    item.name = name
    item.setIcon(_batch_icon('service'))
    item.service_plan = service_plan
    item.service_params = service_params
    return item


def _clone_sample_item(item_sample):
    new_item_sample = QtGui.QStandardItem(item_sample.text())
    new_item_sample.item_type = 'sample'
    new_item_sample.x = item_sample.x
    new_item_sample.y = item_sample.y
    new_item_sample.z = item_sample.z
    new_item_sample.th = item_sample.th
    new_item_sample.name = item_sample.name
    new_item_sample.comment = item_sample.comment
    new_item_sample.setIcon(_batch_icon('sample'))
    return new_item_sample

def _clone_scan_item(item_scan):
    new_item_scan = QtGui.QStandardItem(item_scan.text())
    new_item_scan.item_type = 'scan'
    new_item_scan.trajectory = item_scan.trajectory
    new_item_scan.scan_type = item_scan.scan_type
    new_item_scan.repeat = item_scan.repeat
    new_item_scan.delay = item_scan.delay
    new_item_scan.name = item_scan.name
    return new_item_scan


class TableModel(QtCore.QAbstractTableModel):

    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            value = self._data.iloc[index.row(), index.column()]
            return str(value)

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._data.columns[section])

            if orientation == Qt.Vertical:
                return str(self._data.index[section])
