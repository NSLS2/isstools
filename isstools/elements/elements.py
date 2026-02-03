import pkg_resources
import json
from qtpy import QtWidgets, QtCore, QtGui
from isstools.dialogs.BasicDialogs import message_box, question_message_box
import pandas as pd

def get_element_dict():
    json_data = open(pkg_resources.resource_filename('isstools', 'edges_lines.json')).read()
    element_dict = {}

    for i in json.loads(json_data):
        element_dict[i['symbol']] = i
    return element_dict

element_dict = get_element_dict()

def _check_entry(el, edge, energy, name, row):


    info = f'Proposal: {name}, row: {row+1}, element: {el}, edge: {edge}, energy: {energy}'
    if el in element_dict.keys():
        if edge in element_dict[el].keys():
            if abs(energy - float(
                    element_dict[el][edge])) < 10:  # provided energy must be within 10 eV from the xray DB
                if (energy > 4900) and (energy < 32000):
                    return True
                else:
                    message_box('Energy outside of feasible range',
                                ('Warning\nAn entry with energy outside of feasible range found!\n' +
                                 'This measurement will be skipped.\n' +
                                 info))
            else:
                message_box('Invalid energy',
                            ('Warning\nAn entry with invalid energy was found!\n' +
                             'This measurement will be skipped.\n' +
                             info))
        else:
            message_box('Edge not found',
                        ('Warning\nAn entry with invalid edge was found!\n' +
                         'This measurement will be skipped.\n' +
                         info))
    else:
        message_box('Element not found',
                    ('Warning\nAn entry with invalid element was found!\n' +
                     'This measurement will be skipped.\n' +
                     info))
    return False


elements_lines_dict = {
    # 3d
    'Ti' : ['Ka1', 'Kb1', 'Kb5'],
    'V' :  ['Ka1', 'Kb1', 'Kb5'],
    'Cr' : ['Ka1', 'Kb1', 'Kb5'],
    'Mn' : ['Ka1', 'Kb1', 'Kb5'],
    'Fe' : ['Ka1', 'Kb1', 'Kb5'],
    'Co' : ['Ka1', 'Kb1', 'Kb5'],
    'Ni' : ['Ka1', 'Kb1', 'Kb5'],
    'Cu' : ['Ka1', 'Kb1', 'Kb5'],
    'Zn' : ['Ka1', 'Kb1', 'Kb5'],
    # misc
    'As' : ['Ka1', 'Kb1'],
    'Se' : ['Ka1', 'Kb1'],
    'Br' : ['Ka1', 'Kb1'],
    'Kr' : ['Ka1', 'Kb1'],
    # 4d
    'Nb' : ['Ka1', 'Kb1', 'Kb5'],
    'Mo' : ['Ka1', 'Kb1', 'Kb5'],
    'Ru' : ['Ka1', 'Kb1', 'Kb5'],
    'Rh' : ['Ka1', 'Kb1', 'Kb5'],
    'Pd' : ['Ka1', 'Kb1', 'Kb5'],
    'Ag' : ['Ka1', 'Kb1', 'Kb5'],
    'Cd' : ['Ka1', 'Kb1', 'Kb5'],
    # 5d
    'W' : ['La1'],
    'Re' : ['La1'],
    'Os' : ['La1'],
    'Ir' : ['La1'],
    'Pt' : ['La1'],
    'Au' : ['La1'],
    'Hg' : ['La1'],
    'Pb' : ['La1'],
    'Bi' : ['La1'],
    }



def remove_ev_from_energy_str(energy):
    if 'ev' in energy:
        return energy.replace('ev', '')
    if 'eV' in energy:
        return energy.replace('eV', '')
    if 'EV' in energy:
        return energy.replace('EV', '')
    return energy


special_char_list = ['!', '@', '#', '$', '%','^', '&', '*', '/', '\\', '.']
def remove_special_characters(input_str):
    for c in special_char_list:
        input_str = input_str.replace(c, '_')
    return input_str



_edges_L1 = ['L1', 'L-1', 'L_1', 'L-I', 'L_I']
_edges_L2 = ['L2', 'L-2', 'L_2', 'L-II', 'L_II']
_edges_L3 = ['L3', 'L-3', 'L_3', 'L-III', 'L_III']
def remove_edge_from_edge_str(edge):
    if 'K' in edge:
        return 'K'
    if any([suf in edge for suf in _edges_L1]):
        return 'L1'
    if any([suf in edge for suf in _edges_L2]):
        return 'L2'
    if any([suf in edge for suf in _edges_L3]):
        return 'L3'
    return edge

def clean_el_str(el):
    for i in element_dict.keys():
        if i in el:
            return i
    return el


def compute_line_dictionary_for_spectrometer():

    lines = ['Ka1', 'Ka2', 'Kb1', 'Kb2', 'Kb3', 'Kb5', 'La1', 'Lb1', 'Lb3', 'Lb4','Lg1','Lg2','Lg3', 'Ma', 'Mb']

    edges = ['K', 'L1', 'L2', 'L3']

    output = []

    for _z in range(15, 95):
        for line in lines:
            line_info = xraydb.xray_line(_z, line)
            if line_info is None:
                continue
            energy = line_info.energy
            z = xraydb.atomic_symbol(_z)
            if 2500 < energy < 30000:
                output.append({'element': z, 'Z': _z, 'type': 'line', 'symbol': line, 'energy': energy})
                # if (_z, z) not in line_dict.keys():
                #     line_dict[(_z, z)] = {}
                # # print(_z, z, line, energy)
                # line_dict[(_z, z)][line] = ('line', energy)

        for edge in edges:
            edge_info = xraydb.xray_edge(_z, edge)
            if edge_info is None:
                continue
            energy = xraydb.xray_edge(_z, edge).energy
            # z = xraydb.atomic_symbol(_z)
            if 2000 < energy < 30000:
                output.append({'element': z, 'Z': _z, 'type': 'edge', 'symbol': edge, 'energy': energy})
                # if (_z, z) not in line_dict.keys():
                #     line_dict[(_z, z)] = {}
                # # print(_z, z, edge, energy)
                # line_dict[(_z, z)][edge] = ('edge', energy)

    df = pd.DataFrame(output)

    filepath = '../fluorescence_lines2.json'
    df.to_json(filepath)

def get_spectrometer_line_dict():
    fname = pkg_resources.resource_filename('isstools', 'fluorescence_lines2.json')
    return pd.read_json(fname)

class TreeView(QtWidgets.QTreeView):
    def __init__(self, parent, accepted_type, unique_elements=True):
        QtWidgets.QTreeView.__init__(self, parent)
        self.accepted_type = accepted_type
        self.unique_elements = unique_elements
        self.setDragEnabled(False)
        self.setAcceptDrops(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

    def startDrag(self, dropAction):
        mime = QtCore.QMimeData()
        mime.setData('accepted_type', self.accepted_type.encode('utf-8'))
        index = self.currentIndex()
        item = index.model().itemFromIndex(index)
        mime.setText(item.text())
        #mime.setData('application/x-item', '???')

        #print('Start dragging')
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        drag.exec(QtCore.Qt.CopyAction)#start(QtCore.Qt.CopyAction)#(QtCore.Qt.CopyAction)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("accepted_type"):
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragEnterEvent(self, event):
        if (event.mimeData().data('accepted_type').data().decode("utf-8") == self.accepted_type):
            event.accept()
        else:
            event.ignore()    

    def dropEvent(self, event):
        #if self.accepted_type = event.mimeData().data('accepted_type'):
        #QtWidgets.QTreeView.dropEvent(self, event)
        #if event.isAccepted():
        #    print('dropEvent', hasattr(self, 'x'))
        #print('Formats: {}'.format(event.mimeData().formats()))
        #print('Mime: {}'.format(event.mimeData().data('application/x-qstandarditemmodeldatalist')))
        #data = event.mimeData().data('application/x-qabstractitemmodeldatalist')
        print('here')

        '''
        exists = False
        curr_item_text = event.mimeData().text()
        if self.unique_elements:
            for i in range(self.model().rowCount()):
                if self.model().item(i).text() == curr_item_text:
                    exists = True
                    break

        if not exists:
            event.acceptProposedAction()
            item = QtGui.QStandardItem()
            item.setText(curr_item_text)
            parent = self.model().invisibleRootItem()
            parent.appendRow(item)
            QtWidgets.QTreeView.dropEvent(self, event)
        '''

# # import time as ttime
# # from ophyd import Signal
# # bla = Signal(name='bla')
# # def time_subscription(method, timestamp_dict):
# #     def wrapper(obj, *args, **kwargs):
# #         timestamp = ttime.time()
# #         result = method(obj, *args, **kwargs)
# #         return result
# #     return wrapper
#
# previous_time_dict = {}
# def time_subscription_decorator(method):
#     def wrapper(*args, **kwargs):
#         timestamp = ttime.time()
#         pv_key = kwargs['obj'].name
#         if pv_key in previous_time_dict.keys():
#             old_timestamp = previous_time_dict[pv_key]
#         else:
#             old_timestamp = 0
#
#         if timestamp - old_timestamp > 3:
#             print(f'method call at {timestamp}')
#             previous_time_dict[pv_key] = timestamp
#             return method(*args, **kwargs)
#         else:
#             print(f'to soon for a method call')
#             return None
#
#     return wrapper
#
# @time_subscription_decorator
# def print_value(value, **kwargs):
#     print(value)
#
#
# bla.subscribe(print_value)


