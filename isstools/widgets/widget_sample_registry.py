import os
import sys

import pkg_resources
import json
from qtpy import uic, QtCore, QtWidgets, QtGui
from qtpy.QtCore import QObject
from bluesky.plan_stubs import mv
# from isstools.batch.table_batch import XASBatchExperiment
# from xas.trajectory import trajectory_manager
from isstools.widgets import widget_batch_manual_legacy
from isscloudtools import gdrive, initialize
import numpy as np
from isstools.dialogs.BasicDialogs import message_box, question_message_box
# from xas.trajectory import trajectory, trajectory_manager
from xas.image_analysis import analyze_spiral_scan

import time as ttime
from isstools.batch.autopilot_routines import Experiment, TrajectoryStack
from isstools.elements.batch_motion import SamplePositioner
import bluesky.plan_stubs as bps
from pyzbar.pyzbar import decode as pzDecode
import pandas as pd
from isstools.elements.elements import remove_ev_from_energy_str, remove_edge_from_edge_str, clean_el_str
from isstools.elements.batch_elements import *
from isstools.elements.batch_elements import (_create_batch_experiment, _create_new_sample, _create_new_scan, _create_service_item, _clone_scan_item, _clone_sample_item)
from isstools.elements.elements import element_dict, _check_entry, remove_special_characters

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_sample_registry.ui')


class UISampleRegistry(*uic.loadUiType(ui_path)):
    def __init__(self,
                 motors_dict,
                 camera_dict,
                 hhm,
                 trajectory_manager,
                 RE,
                 # db,
                 sample_stage,
                 parent_gui,
                 service_plan_funcs,
                 plan_funcs,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        #self.addCanvas()
        #
        self.plan_funcs = plan_funcs
        self.service_plan_funcs = service_plan_funcs
        # self.plan_funcs_names = plan_funcs.keys()
        # self.service_plan_funcs_names = service_plan_funcs.keys()
        #
        # self.motors_dict = motors_dict
        # self.mot_list = self.motors_dict.keys()
        # self.mot_sorted_list = list(self.mot_list)
        # self.mot_sorted_list.sort()
        self.camera_dict = camera_dict
        self.motors_dict = motors_dict
        self.hhm = hhm
        self.trajectory_manager = trajectory_manager
        self.traj_stack = TrajectoryStack(self.hhm, self.trajectory_manager)

        self.RE = RE

        self.sample_stage = sample_stage
        self.settings = parent_gui.settings

        self.service = initialize.get_gdrive_service()
        self.service_sheets = initialize.get_gsheets_service()
        self.sheet = self.service_sheets.spreadsheets()

        self.parent_gui = parent_gui
        self.push_proposal_list.clicked.connect(self.get_proposal_list_gdrive)
        self.push_select_proposals.clicked.connect(self.select_proposals)
        self.push_clear_table.clicked.connect(self.clear_table)
        self.push_validate_samples.clicked.connect(self.validate_samples)
        self.push_export_as_batch.clicked.connect(self.export_as_batch)

        # self.read_json_data()
        self.table_keys = ['Found','Run','Proposal', 'SAF', 'Holder ID', 'Sample #', 'Name', 'Comment', 'Composition',
                           'Element', 'Concentration', 'Edge','Energy', 'k-range', '# of scans', 'Position', 'Holder type', 'Autofoil' ]


        self.tableWidget_sample_def.setColumnCount(len(self.table_keys))
        self.tableWidget_sample_def.setHorizontalHeaderLabels(self.table_keys)
        self.tableWidget_sample_def.cellChanged.connect(self.update_sample_df)
        self.sample_df = pd.DataFrame(columns=self.table_keys)
        for jj in range(len(self.table_keys)):
            self.tableWidget_sample_def.resizeColumnToContents(jj)


        self.tableWidget_proposal.setColumnCount(2)
        self.tableWidget_proposal.setHorizontalHeaderLabels(['Proposal', 'PI'])
        self.tableWidget_proposal.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.tableWidget_proposal.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)



        # self.get_proposal_list_gdrive()



    # def read_json_data(self):
    #     json_data = open(pkg_resources.resource_filename('isstools', 'edges_lines.json')).read()
    #     self.element_dict = {}
    #
    #     for i in json.loads(json_data):
    #         self.element_dict[i['symbol']] = i


    def get_proposal_list_gdrive(self):
        cycle = self.RE.md['cycle']
        year = self.RE.md['year']
        found_flag = False
        fid_year = gdrive.folder_exists_in_root(self.service, year)
        fid_cycle = gdrive.folder_exists(self.service, fid_year, cycle)
        files = gdrive.get_file_list(self.service, fid_cycle)['files']
        # TODO: one day please make a decent dict to store the important info!!
        self.file_names = []
        for f in files:
            proposal_num = f['name'][-6:]
            if str.isnumeric(proposal_num):
                self.file_names.append(proposal_num)
            else:
                self.file_names.append(f['name'])
        self.file_names = np.array(self.file_names)
        self.file_ids = np.array([i['id'] for i in files])
        ptable_row_index = 0

        proposal_info = self.read_proposal_info(year, cycle)


        if files:
            self.tableWidget_proposal.setRowCount(0)
            for file in files:
                fn= file['name']
                proposal_num = fn[-6:]
                # if str.isnumeric(fn) and len(fn)==6:
                if str.isnumeric(proposal_num):
                    found_flag = True
                    self.tableWidget_proposal.insertRow(ptable_row_index)

                    self.tableWidget_proposal.setItem(ptable_row_index, 0, QtWidgets.QTableWidgetItem(proposal_num))

                    try:
                        self.tableWidget_proposal.setItem(ptable_row_index, 1,
                                                            QtWidgets.QTableWidgetItem(proposal_info[proposal_num]['name']))
                    except KeyError:
                        self.tableWidget_proposal.setItem(ptable_row_index, 1,
                                                            QtWidgets.QTableWidgetItem('staff'))
                    ptable_row_index += 1
            for jj in range(2):
                self.tableWidget_proposal.resizeColumnToContents(jj)
        # else:
        #     message_box('Error','No proposal definition files found')
        #
        # if not found_flag:
        #     message_box('Error', 'No proposal definition files found')


    def read_proposal_info(self, year, cycle):
        try:
            info_file_name = str(year) + '-' + str(cycle) + ' Proposal list'
            # print(info_file_name)
            # print(self.file_names)
            # print(self.file_names == info_file_name)
            file_id = self.file_ids[self.file_names == info_file_name][0]
            try:
                result = self.sheet.values().get(spreadsheetId=file_id, range='Sheet1').execute()
            except:
                result = self.sheet.values().get(spreadsheetId=file_id, range='8-ID').execute()
            sheet_data = result['values']
            # print(sheet_data)
            proposal_info = {}
            for i, row in enumerate(sheet_data):
                if i > 0:  # skip the header
                    proposal_info[row[0]] = {'name' : row[2] + ', ' + row[1],'email' : row[3]}
            # print(proposal_info)
            return proposal_info
        except:
            return None




    def select_proposals(self):
        self.tableWidget_sample_def.setRowCount(0)
        self.sample_df = pd.DataFrame(columns=self.table_keys)
        selected_items = [i.data() for i in self.tableWidget_proposal.selectedIndexes() if i.column()==0]
        selected_file_ids = []

        for item in selected_items:
            file_id = self.file_ids[item == self.file_names]
            selected_file_ids.append(file_id[0])

        # self.batch_experiment = []
        qtable_row_index = 0
        df_row_index = 0

        for file_id, name in zip(selected_file_ids, selected_items):
            result = self.sheet.values().get(spreadsheetId=file_id, range='Sheet1').execute()
            sheet_data = result['values']

            for i, row in enumerate(sheet_data):
                if i > 0: # skip the header
                    # sample_holder_id, sample_num, saf_num, sample_label, comment, composition, hazards = row[:6]
                    # 'Sample holder ID', 'Sample #', 'SAF #', 'Sample label', 'Comment', 'Composition', 'Hazards'
                    # sample_info = [name.text()]+row[:6]
                    sample_info = [name] + row[:6]
                    els = row[7::6]
                    el_concs = row[8::6]
                    edges = row[9::6]
                    energies = row[10::6]
                    kranges = row[11::6]
                    nscanss = row[12::6]

                    for el, el_conc, edge, energy, krange, nscans in zip(els, el_concs, edges, energies, kranges, nscanss):
                        el = clean_el_str(el)
                        edge = remove_edge_from_edge_str(edge)
                        energy = remove_ev_from_energy_str(energy)
                        if _check_entry(el, edge, float(energy), name, i):
                            entry_list = [False,False] + sample_info + [el, el_conc, edge, energy, krange, nscans] + ['', '', True]
                            self.sample_df.loc[df_row_index] = entry_list
                            df_row_index += 1

        self.sample_df_to_table_widget()
        # combo_run = self.parent_gui.widget_run.comboBox_autopilot_sample_number #???
        # combo_run.clear
        # for indx, _ in self.sample_df.iterrows():
        #     combo_run.addItem(str(indx + 1))

    def clear_table(self):
        self.sample_df = pd.DataFrame(columns=self.table_keys)
        self.sample_df_to_table_widget()


    def sample_df_to_table_widget(self):
        self.tableWidget_sample_def.cellChanged.disconnect()
        self.tableWidget_sample_def.setRowCount(0)
        self.tableWidget_sample_def.clearContents()
        nrows = self.sample_df.shape[0]
        for i in range(nrows):
            entry_list = list(self.sample_df.iloc[i])
            self.tableWidget_sample_def.insertRow(i)
            for j, item in enumerate(entry_list):
                self.tableWidget_sample_def.setItem(i, j, QtWidgets.QTableWidgetItem(item))

        self.checkBoxes_found = []
        self.checkBoxes_run = []
        self.checkBoxes_autofoil = []
        for i in range(nrows):
            ######## THIS IS REALLY UNCLEAR: WHY 'RUN' UPDATES 0-th COLUMN??!
            chkBoxItem = QtWidgets.QTableWidgetItem()
            chkBoxItem.setFlags( QtCore.Qt.ItemIsEnabled)
            if self.sample_df.iloc[i]['Run']:
                chkBoxItem.setCheckState(QtCore.Qt.Checked)
            else:
                chkBoxItem.setCheckState(QtCore.Qt.Unchecked)
            self.tableWidget_sample_def.setItem(i,0,chkBoxItem)
            self.checkBoxes_found.append(chkBoxItem)

            chkBoxItem = QtWidgets.QTableWidgetItem()
            chkBoxItem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            if self.sample_df.iloc[i]['Found']:
                chkBoxItem.setCheckState(QtCore.Qt.Checked)
            else:
                chkBoxItem.setCheckState(QtCore.Qt.Unchecked)
            self.tableWidget_sample_def.setItem(i, 1, chkBoxItem)
            self.checkBoxes_run.append(chkBoxItem)

            chkBoxItem = QtWidgets.QTableWidgetItem()
            chkBoxItem.setFlags(QtCore.Qt.ItemIsEnabled)
            if self.sample_df.iloc[i]['Autofoil']:
                chkBoxItem.setCheckState(QtCore.Qt.Checked)
            else:
                chkBoxItem.setCheckState(QtCore.Qt.Unchecked)
            self.tableWidget_sample_def.setItem(i, 17, chkBoxItem)
            self.checkBoxes_autofoil.append(chkBoxItem)

        for jj in range(len(self.table_keys)):
            self.tableWidget_sample_def.resizeColumnToContents(jj)

        self.tableWidget_sample_def.cellChanged.connect(self.update_sample_df)


    def update_sample_df(self, row, column):
        print(row, column)
        if column == 1:
            print('Changing run?')
            to_run =  int(self.checkBoxes_run[row].checkState())
            print(f'New status {to_run}')
            if to_run != 0:
                self.sample_df['Run'][row] = True
            else:
                self.sample_df['Run'][row] = False
        elif column == 17:
            to_autofoil = int(self.checkBoxes_autofoil[row].checkState())
            if to_autofoil != 0:
                self.sample_df['Autofoil'][row] = True
            else:
                self.sample_df['Autofoil'][row] = False
        else:
            self.sample_df.iloc[row][column] = self.tableWidget_sample_def.item(row, column).text()


    def export_as_batch_testing(self):
        self.sample_df['Position'] = '111'
        self.sample_df['Holder type'] = '1'
        self.sample_df['Found'] = True
        self.sample_df['Run'] = True
        self.get_sample_positioner()
        self.export_as_batch()


    def export_as_batch(self):
        # self.model_batch = QtGui.QStandardItemModel(self)
        # self.model_samples = QtGui.QStandardItemModel(self)
        # self.model_scans = QtGui.QStandardItemModel(self)

        # formatting dataframe
        self.sample_df['Energy'] = self.sample_df['Energy'].astype(float)
        self.sample_df['k-range'] = self.sample_df['k-range'].astype(float)
        self.sample_df['# of scans'] = self.sample_df['# of scans'].astype(int)
        self.sample_df = self.sample_df.replace({'True' : True, 'False': False})

        ascending = (self.read_mirror_position() < 20)
        # self.sample_df = self.sample_df.sort_values('Energy', ascending=ascending)
        self.sample_df = self.sample_df.sort_values(['Energy', 'Position'],
                                                    ascending=(ascending, True))
        traj_columns = ['Element', 'Edge', 'Energy', 'k-range', '# of scans']
        self.unique_traj_df = self.sample_df.drop_duplicates(traj_columns)

        self.model_batch = QtGui.QStandardItemModel(self)
        _create_batch_experiment('experiment', 1, model=self.model_batch)
        for _, scan_row in self.unique_traj_df.iterrows():
            any_samples_found = False
            item_scan = self._get_scan_item(scan_row)
            item_service = self._get_service_item(scan_row, None, 'optimize beamline')
            item_scan.appendRow(item_service)

            idx = (self.sample_df == scan_row)[traj_columns].all(1)


            for _, sample_row in self.sample_df[idx].iterrows():
                if sample_row['Found'] and sample_row['Run']:
                    any_samples_found = True
                    item_service = self._get_service_item(scan_row, sample_row, 'optimize sample')
                    item_sample = self._get_sample_item(sample_row)
                    item_scan.appendRow(item_service)
                    item_scan.appendRow(item_sample)

            if any_samples_found:
                self.model_batch.item(0).appendRow(item_scan)



        # for ii, row in self.sample_df.iterrows():
        #     if row['Found'] and row['Run']:
        #         item_sample = self._get_sample_item(row)
        #         item_service = self._get_service_item(row)
        #         item_scan = self._get_scan_item(row)
        #         item_scan.appendRow(item_service)
        #         item_scan.appendRow(item_sample)
        #
        #         self.model_batch.item(0).appendRow(item_scan)

        self.treeView_batch = self.parent_gui.widget_batch_mode.widget_batch_manual.treeView_batch
        self.treeView_batch.setModel(self.model_batch)
        self.parent_gui.widget_batch_mode.widget_batch_manual.model_batch = self.model_batch
        self.treeView_batch.expandAll()


    def _get_sample_item(self, row):
        # model_sample = QtGui.QStandardItemModel()
        sample_x, sample_y = self._get_sample_position(row)
        name = remove_special_characters(row['Name'])
        item_sample = _create_new_sample(name,  # sample name
                                         row['Comment'],  # sample_comment,
                                         sample_x,  # sample_x,
                                         sample_y,
                                         setCheckable=False)  # sample_y
        # item_sample = _clone_sample_item(model_sample.item(0))
        # item_sample.setCheckable(False)
        item_sample.setEditable(False)
        return item_sample


    def _get_service_item(self, row_scan, row_sample, service_type):
        if service_type == 'optimize beamline':
            item_service = _create_service_item('optimize beamline',
                                                self.service_plan_funcs['optimize_beamline_plan'],
                                                {'energy' : row_scan['Energy']})
        elif service_type == 'optimize sample':
            sample_x, sample_y = self._get_sample_position(row_sample)
            item_service = _create_service_item('optimize sample',
                                                self.service_plan_funcs['optimize_sample_plan'],
                                                {'sample_x' : sample_x,
                                                 'sample_y' : sample_y,
                                                 'energy' : row_scan['Energy'],
                                                 'concentration' : float(row_sample['Concentration']),
                                                 'name' :  f"{row_sample['Name']}_{row_sample['Position']}"})
        return item_service



    def _get_scan_item(self, row):
        # model_scan = QtGui.QStandardItemModel()
        traj_signature = {'type': 'Double Sine',
                          'parameters': {'element': row['Element'],
                                         'edge': row['Edge'],
                                         'E0': row['Energy'],
                                         'Epreedge': -200,
                                         'kmax': row['k-range'],
                                         't1': 10,
                                         't2': 20 * float(row['k-range']) / 16}}
        item_scan = _create_new_scan(row['Element'] + '-' + row['Edge'] + ' kmax ' + str(row['k-range']),  # scan name
                         'Fly scan (new PB)',  # scan type, normally fly scan
                         traj_signature,  # scan_traj
                         row['# of scans'],  # n scans
                         0,
                         row['Autofoil'],
                         setCheckable=False)  # scan delay
        # item_scan = _clone_scan_item(model_scan.item(0))

        # item_scan.setCheckable(False)
        item_scan.setEditable(False)
        return item_scan





                # self.traj_stack.set_traj(experiment.traj_signature)

                # self.table_keys = ['Found','Run','Proposal', 'SAF', 'Holder ID', 'Sample #', 'Name', 'Comment', 'Composition',
        #                    'Element', 'Concentration', 'Edge','Energy', 'k-range', '# of scans', 'Position', 'Holder type' ]


        # self.model_batch = self.parent_gui.widget_batch.widget_batch_manual.model_batch
        # self.model_samples = self.parent_gui.widget_batch.widget_batch_manual.model_samples
        # self.model_scans = self.parent_gui.widget_batch.widget_batch_manual.model_scans
        # self.model_batch = QtGui.QStandardItemModel(self)
        # self.model_samples = QtGui.QStandardItemModel(self)
        # self.model_scans = QtGui.QStandardItemModel(self)


    def _get_sample_position(self, row):
        i_stack, i_holder, i_sample = row['Position']
        sample_x, sample_y = self.sample_positioner.get_sample_position(int(i_stack),
                                                                        int(i_holder),
                                                                        int(i_sample),
                                                                        int(row['Holder type']))
        return sample_x, sample_y

    def _check_entry(self, el, edge, energy, name, row):
        info = f'Proposal: {name}, row: {row}, element: {el}, edge: {edge}, energy: {energy}'
        if el in self.element_dict.keys():
            if edge in self.element_dict[el].keys():
                if abs(energy - float(self.element_dict[el][edge])) < 10:  # provided energy must be within 10 eV from the xray DB
                    if (energy > 4900) and(energy < 32000):
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


    def read_mirror_position(self):
        mot = self.motors_dict['cm1_x']['object']
        return mot.read()[mot.name]['value']



    def validate_samples(self):
        self.get_sample_positioner()  # handle on sample positioner
        full_stop = False
        for s in range(self.sample_positioner.n_stacks):
            for h in range(self.sample_positioner.n_holders):
                found_holder, holder_type = self.validate_holder(s+1, h+1)

                if (not found_holder):
                    if h == 0:
                        full_stop = True
                    break
                if holder_type == 2: # only one capillary holder is allowed per stack
                    break
            if full_stop:
                print('no more holders found', file=self.parent_gui.emitstream_out, flush=True)
                break
        self.sample_df_to_table_widget()
        # mark samples that were not found:
        #for index, row in self.sample_df.iterrows():
        #    if not row['Found']:
        #        self.tableWidget_sample_def.setItem(index, 13, QtWidgets.QTableWidgetItem('False'))


    def validate_holder(self, idx_stack, idx_holder, n_attempts=3):

        print(f'looking at stack:{idx_stack}, holder:{idx_holder}', file=self.parent_gui.emitstream_out, flush=True)

        self.sample_positioner.goto_holder(idx_stack, idx_holder)
        self.RE(bps.sleep(0.5))
        i_attempt = 0
        while i_attempt<n_attempts:
            print('attempt:', i_attempt+1, file=self.parent_gui.emitstream_out, flush=True)
            qr_codes = self.read_qr_codes()
            if qr_codes:
                for qr_code in qr_codes:
                    qr_text = qr_code.data.decode('utf8')
                    proposal, holder_type, holder_id = qr_text.split('-')
                    found_holder = False
                    for index, row in self.sample_df.iterrows():
                        if ((row['Proposal'] == proposal) and
                            (row['Holder ID'] == holder_id)):
                            position = str(idx_stack) + str(idx_holder) + row['Sample #']
                            row['Found'] = True
                            row['Run'] = True
                            row['Position'] = position
                            row['Holder type'] = holder_type
                            # self.sample_df['Found'].iloc[index] = True
                            # self.sample_df['Run'].iloc[index] = True
                            # self.sample_df['Position'].iloc[index] = position
                            # self.sample_df['Holder type'].iloc[index] = holder_type
                            found_holder = True
                    return found_holder, holder_type

            else:
                i_attempt += 1
        return False, None


    def read_qr_codes(self):
        self.get_qr_roi()
        x1, x2, y1, y2 = self.qr_roi
        x1, x2 = np.sort([x1, x2])
        y1, y2 = np.sort([y1, y2])
        image_qr = self.camera_dict['camera_sample4'].image.image[y1:y2, x1:x2]
        return pzDecode(image_qr)

    def get_qr_roi(self):
        x1 = self.settings.value('qr_roi_x1', defaultValue=0, type=int)
        x2 = self.settings.value('qr_roi_x2', defaultValue=0, type=int)
        y1 = self.settings.value('qr_roi_y1', defaultValue=0, type=int)
        y2 = self.settings.value('qr_roi_y2', defaultValue=0, type=int)
        self.qr_roi = [x1, x2, y1, y2]

    def get_sample_positioner(self):
        stage_park_x = self.settings.value('stage_park_x', defaultValue=0, type=float)
        stage_park_y = self.settings.value('stage_park_y', defaultValue=0, type=float)
        sample_park_x = self.settings.value('sample_park_x', defaultValue=0, type=float)
        sample_park_y = self.settings.value('sample_park_y', defaultValue=0, type=float)

        self.sample_positioner = SamplePositioner(self.RE,
                                                  self.sample_stage,
                                                  stage_park_x,
                                                  stage_park_y,
                                                  offset_x=sample_park_x - stage_park_x,
                                                  offset_y=sample_park_y - stage_park_y)



    #
    # def run_autopilot(self):
    #
    #     # workflow:
    #     # go through the entire stack of samples and scan qr-codes:
    #     #               -mark the samples that were found in the table - done
    #     #               -mark the position of each sample - done
    #     # go through elements from low to high energy:
    #     #               -prepare and tune the beamline for each energy - done
    #     #               -(tbd) vibrations handling - done
    #     #               -set trajectory
    #     #               -sample optimization, aka gain setting, spiral scan etc
    #
    #     # self.get_sample_positioner() # handle on sample positioner
    #     # self.locate_samples() # go through all samples on the holder and confirm that all of them are found
    #
    #     # generate order
    #
    #     exec_order = np.argsort([float(i['Energy']) for i in self.batch_experiment])
    #     cm1_x_pos = self.read_mirror_position()
    #     if cm1_x_pos>20:
    #         exec_order = exec_order[::-1]
    #     print(exec_order)
    #     n_measurements = len(self.batch_experiment)
    #
    #     current_energy = None
    #     print(current_energy, flush=True)
    #     # for i in range(n_measurements):
    #     for i in [8]:
    #         idx = exec_order[i]
    #         step = self.batch_experiment[idx]
    #         if step['found']:
    #             # print((step['Sample label'],
    #             #        step['Comment'],
    #             #        step['# of scans'],
    #             #        0, # delay
    #             #        step['Element'],
    #             #        step['Edge'],
    #             #        step['Energy'],
    #             #        -200, # preedge
    #             #        step['k-range'],
    #             #        10, # t1
    #             #        20 * float(step['k-range'])/16))
    #
    #
    #             print(current_energy)
    #             print(step['Energy'])
    #             # if ((not current_energy) or
    #             #         (abs(current_energy - step['Energy']) > 0.1 * current_energy)):
    #             #     current_energy = step['Energy']
    #                 # self.sample_positioner.goto_park()
    #                 # self.parent_gui.widget_beamline_setup.prepare_beamline(energy_setting=int(current_energy))
    #
    #                 # if current_energy < 14000:
    #                 #     mirror_position = 0
    #                 # else:
    #                 #     mirror_position = 40
    #                 # print('Checking/Moving CM1 mirror X ... ', file=self.parent_gui.emitstream_out, flush=True, end='')
    #                 # self.RE(bps.mv(self.motors_dict['cm1_x']['object'], mirror_position))
    #                 # print('complete', file=self.parent_gui.emitstream_out, flush=True)
    #                 # self.parent_gui.widget_beamline_setup.tune_beamline()
    #                 # self.RE(self.service_plan_funcs['prepare_beamline_plan'](energy=current_energy,
    #                 #                                                          stdout=self.parent_gui.emitstream_out))
    #                 # self.RE(self.service_plan_funcs['tune_beamline_plan'](stdout=self.parent_gui.emitstream_out))
    #                 # print('Enabling feedback ... ', file=self.parent_gui.emitstream_out, flush=True, end='')
    #                 # self.parent_gui.widget_beamline_setup.update_piezo_center()
    #                 # if  not self.parent_gui.widget_beamline_setup.pushEnableHHMFeedback.isChecked:
    #                 #     self.parent_gui.widget_beamline_setup.pushEnableHHMFeedback.toggle()
    #                 #
    #                 # print('complete', file=self.parent_gui.emitstream_out, flush=True)
    #
    #             # experiment = Experiment(step['Sample label'],
    #             #                         step['Comment'],
    #             #                         step['# of scans'],
    #             #                         0, # delay
    #             #                         step['Element'],
    #             #                         step['Edge'],
    #             #                         step['Energy'],
    #             #                         -200, # preedge
    #             #                         step['k-range'],
    #             #                         10, # t1
    #             #                         20 * float(step['k-range'])/16) # t2
    #             # self.traj_stack.set_traj(experiment.traj_signature)
    #
    #             self.sample_positioner.goto_sample(*step['position'])
    #             print('seting gains/offsets ', file=self.parent_gui.emitstream_out, flush=True)
    #             self.RE(self.service_plan_funcs['adjust_ic_gains']())
    #             self.RE(self.service_plan_funcs['get_offsets'](time=2))
    #             print('seting gains/offsets complete', file=self.parent_gui.emitstream_out, flush=True)
    #             #
    #             # plan_func = self.plan_funcs['Fly scan (new PB)']
    #             #
    #             # RE_args = [plan_func(**experiment.run_parameters,
    #             #                      ignore_shutter=False,
    #             #                      stdout=self.parent_gui.emitstream_out)]
    #
    #             # if plan_key.lower().endswith('pilatus'):
    #             #     LivePlots.append(LivePlotPilatus)
    #             #
    #             # if plan_key.lower().startswith('step scan'):
    #             #     RE_args.append(LivePlots)
    #             self.optimize_sample_position()
    #
    #             self.RE(*RE_args)
    #
    #             # gains and offsets
    #             # spiral scan
    #             # measurement
    #
    # def optimize_sample_position(self, conc):
    #     uid = self.RE(self.service_plan_funcs['spiral_scan']())
    #     if type(uid) == tuple:
    #         uid = uid[0]
    #     x_opt, y_opt = analyze_spiral_scan(uid, conc)
    #     self.sample_positioner.goto_xy(x_opt, y_opt)
    #
    # def _print(self, msg,  **kwargs):
    #     print(msg, file=self.parent_gui.emitstream_out, flush=True, **kwargs)
    #
    #
    #
    #     # for step in self.batch_experiment:
    #     #
    #     #     start = ttime.time()
    #     #     # ['Proposal', 'SAF', 'Sample holder ID', 'Sample #', 'Sample label', 'Comment', 'Composition',
    #     #     #  'Element', 'Concentration', 'Edge', 'Energy', 'k-range', '# of scans']
    #     #
    #     #
    #     #     experiment = Experiment(step['Sample label'],
    #     #                             step['Comment'],
    #     #                             step['# of scans'],
    #     #                             0, # delay
    #     #                             step['Element'],
    #     #                             step['Edge'],
    #     #                             step['Energy'],
    #     #                             -200, # preedge
    #     #                             step['k-range'],
    #     #                             10, # t1
    #     #                             20 * float(step['k-range'])/16) # t2
    #     #
    #     #     self.traj_stack.set_traj(experiment.traj_signature)
    #     #
    #     #     print(f'success took: {ttime.time() - start}')
    #
    #
    #
    #
    #
    # def define_trajectories(self):
    #     for experiment in self.batch_experiment:
    #         # d = self.experiment
    #         traj = trajectory(self.hhm)
    #         kwargs = dict(
    #             edge_energy=experiment['Energy'],
    #             offsets=([experiment['pre-edge start'], d['pre-edge stop'],
    #                       d['post-edge stop'], xray.k2e(d['k-range'], d['Energy']) - d['Energy']]),
    #             trajectory_type='Double Sine',
    #             dsine_preedge_duration=d['time 1'],
    #             dsine_postedge_duration=d['time 2'],
    #         )
    #         print(kwargs)
    #         traj.define(**kwargs)
    #
    #         # Add some more parameters manually:
    #         traj.elem = d['Element']
    #         traj.edge = d['Edge']
    #         traj.e0 = d['Energy']
    #
    #         traj.interpolate()
    #         traj.revert()
    #         self.trajectories.append(traj)
    #
    # def save_trajectories(self):
    #     for ut in self.unique_trajectories:
    #         filename = os.path.join(self.trajectory_folder, 'trajectory_{}.txt'.format(str(uuid.uuid4())[:8]))
    #         self.trajectory_filenames.append(filename)
    #         print(f'Saving {filename}...')
    #         np.savetxt(filename, ut.energy_grid, fmt='%.6f',
    #                    header=f'element: {ut.elem}, edge: {ut.edge}, E0: {ut.e0}')
    #         call(['chmod', '666', filename])
    #
    # def load_trajectories(self):
    #     offset = self.hhm.angle_offset.value
    #     print(offset)
    #     for i, traj_file in enumerate(self.trajectory_filenames):
    #         self.trajectory_manager.load(os.path.basename(traj_file),i+1,is_energy=True, offset=offset )
    #
    #
    # # def retrieve_info_from_proposals(self):
    #
    #
    #
    # def run_spreadsheet_batch(self):
    #     for coord in self.coordinates:
    #         if getattr(self, 'checkBox_run_cell_{}'.format(coord)).isChecked():
    #             experiment = getattr(self,'batch_experiment_{}'.format(coord))
    #             reference_x= getattr(self,'reference_x_{}'.format(coord))
    #             reference_y = getattr(self, 'reference_y_{}'.format(coord))
    #
    #             experiment.batch_create_trajectories()
    #             experiment.create_unique_trajectories()
    #             experiment.assign_trajectory_number()
    #             experiment.save_trajectories()
    #             experiment.load_trajectories()
    #             #print(self.plan_funcs[3])
    #             #
    #             self.RE(experiment.plan_trajectory_priority(reference_x,reference_y,
    #                                                         sample_stage_x=self.test_motor.x,
    #                                                         sample_stage_y=self.test_motor.y,
    #                                                         plan=self.plan_funcs[0]))
    #
    # def update_reference(self):
    #     sender = QObject()
    #     sender_object = sender.sender().objectName()
    #     coord=sender_object[-2:]
    #     x_value = self.sample_stage.x.position
    #     y_value = self.sample_stage.y.position
    #
    #     setattr(self, 'reference_x_{}'.format(coord),x_value)
    #     setattr(self, 'reference_y_{}'.format(coord),y_value)
    #     getattr(self, 'lineEdit_reference_x_{}'.format(coord)).setText('{:.3f}'.format(x_value))
    #     getattr(self, 'lineEdit_reference_y_{}'.format(coord)).setText('{:.3f}'.format(y_value))
    #
    # def load_sample_definition(self):
    #     sender = QObject()
    #     sender_object = sender.sender().objectName()
    #     coord=sender_object[-2:]
    #     excel_file = QtWidgets.QFileDialog.getOpenFileNames(directory = '/nsls2/xf08id/Sandbox',
    #                filter = '*.xlsx', parent = self)[0]
    #     if len(excel_file):
    #
    #         self.label_database_status.setText('Loading {} to Sample Frame {}'.
    #                                            format(os.path.basename(excel_file[0]), coord))
    #         setattr(self, 'batch_experiment_{}'.format(coord), XASBatchExperiment(excel_file=excel_file[0], hhm=self.hhm))
    #         print(self.batch_experiment_11)
    #
    # def show_sample_definition(self):
    #     sender = QObject()
    #     sender_object = sender.sender().objectName()
    #     coord=sender_object[-2:]
    #     if hasattr(self,'batch_experiment_{}'.format(coord)):
    #         exp=getattr(self,'batch_experiment_{}'.format(coord))
    #         self.tableWidget_sample_def.setRowCount(len(exp.experiment_table))
    #         self.label_database_status.setText(exp.name)
    #         for i in range(len(exp.experiment_table)):
    #             d =exp.experiment_table.iloc[i]
    #             fields=['Proposal','SAF','Sample name','Composition','Element','Edge','Energy']
    #             for j,field in enumerate(fields):
    #                 self.tableWidget_sample_def.setItem(i, j, QtWidgets.QTableWidgetItem(str(d[field])))
    #             self.tableWidget_sample_def.setRowHeight(i,24)
    #     else:
    #         self.label_database_status.setText('Please load Experimental Definition first')
    #
    #
    # def abort_batch(self):
    #     if self.batch_running == True:
    #         self.batch_abort = True
    #         self.re_abort()
    #
    # def check_pause_abort_batch(self):
    #     if self.batch_abort:
    #         print('**** Aborting Batch! ****')
    #         raise Exception('Abort button pressed by user')
    #     elif self.batch_pause:
    #         self.label_batch_step.setText('[Paused] {}'.format(self.label_batch_step.text()))
    #         while self.batch_pause:
    #             QtCore.QCoreApplication.processEvents()
    #
    # def start_batch(self):
    #     print('[Launching Threads]')
    #     batch = self.widget_batch_manual.treeView_batch.model()
    #     self.RE(self.batch_parse_and_run(self.hhm, self.sample_stage, batch, self.plan_funcs))
    #
    # def batch_parse_and_run(self, hhm,sample_stage,batch,plans_dict):
    #     sys.stdout =  self.parent_gui.emitstream_out
    #     tm = trajectory_manager(hhm)
    #     for ii in range(batch.rowCount()):
    #         experiment = batch.item(ii)
    #         repeat=experiment.repeat
    #         for indx in range(repeat):
    #             exper_index = ''
    #             if repeat>1:
    #                 exper_index = f'{(indx+1):04d}'
    #             for jj in range(experiment.rowCount()):
    #                 print(experiment.rowCount())
    #                 step = experiment.child(jj)
    #                 if  step.item_type == 'sample':
    #                     sample = step
    #                     print('  ' + sample.name)
    #                     print('  ' + str(sample.x))
    #                     print('  ' + str(sample.y))
    #                     yield from mv(sample_stage.x, sample.x, sample_stage.y, sample.y)
    #                     #print(f'moving to {sample.x}, {sample y}')
    #                     for kk in range(sample.rowCount()):
    #                         scan = sample.child(kk)
    #                         traj_index= scan.trajectory
    #                         print('      ' + scan.scan_type)
    #                         plan = plans_dict[scan.scan_type]
    #                         sample_name =  '{} {} {}'.format(sample.name, scan.name, exper_index)
    #                         print(sample_name)
    #                         kwargs = {'name': sample_name,
    #                                   'comment': '',
    #                                   'delay': 0,
    #                                   'n_cycles': scan.repeat,
    #                                   'stdout': self.parent_gui.emitstream_out}
    #                         tm.init(traj_index+1)
    #                         yield from plan(**kwargs)
    #                 elif step.item_type == 'scan':
    #                     scan = step
    #                     traj_index = scan.trajectory
    #                     print('  ' + scan.scan_type)
    #                     tm.init(traj_index + 1)
    #                     for kk in range(step.rowCount()):
    #                         sample = scan.child(kk)
    #                         yield from mv(sample_stage.x, sample.x, sample_stage.y, sample.y)
    #                         plan = plans_dict[scan.scan_type]
    #                         print('     ' + sample.name)
    #                         print('     ' + str(sample.x))
    #                         print('     ' + str(sample.y))
    #                         sample_name = '{} {} {}'.format(sample.name, scan.name, exper_index)
    #                         print(sample_name)
    #                         kwargs = {'name': sample_name,
    #                                   'comment': '',
    #                                   'delay': 0,
    #                                   'n_cycles': repeat,
    #                                   'stdout': self.parent_gui.emitstream_out}
    #
    #                         yield from plan(**kwargs)
    #                 elif step.item_type == 'service':
    #                     yield from step.service_plan(**step.service_params)





