import os
from subprocess import call

from isstools.widgets import widget_energy_selector


import numpy as np
import pkg_resources
from qtpy import uic, QtWidgets, QtCore, QtGui
from qtpy.Qt import Qt
from qtpy.QtWidgets import QMenu

from isstools.conversions import xray
from isstools.dialogs import UpdateAngleOffset
from isstools.elements.figure_update import update_figure
from xas.trajectory import TrajectoryCreator
from isstools.elements.figure_update import setup_figure
from ophyd import utils as ophyd_utils
from xas.bin import xas_energy_grid
from xas.xray import e2k, k2e
from isstools.dialogs.BasicDialogs import question_message_box, message_box
from ..elements.elements import remove_special_characters
from isstools.widgets import widget_emission_energy_selector

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_scan_manager.ui')

class UIScanManager(*uic.loadUiType(ui_path)):
    scansChanged = QtCore.Signal()

    def __init__(self,
                 hhm= None,
                 spectrometer=None,
                 scan_manager=None,
                 johann_spectrometer_manager=None,
                 detector_dict=[],
                 parent = None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.counter = 0
        self.setupUi(self)
        self.parent = parent
        self.hhm = hhm
        self.spectrometer = spectrometer

        self.scan_manager = scan_manager
        self.johann_spectrometer_manager = johann_spectrometer_manager
        self.detector_dict = detector_dict
        self.widget_energy_selector = widget_energy_selector.UIEnergySelector()
        self.layout_energy_selector.addWidget(self.widget_energy_selector)

        self.widget_emission_energy = widget_emission_energy_selector.UIEmissionEnergySelectorEnergyOnly(parent=self)
        self.layout_emission_energy_selector.addWidget(self.widget_emission_energy)

        self.push_update_offset.clicked.connect(self.update_offset)

        self.hhm.angle_offset.subscribe(self.update_angle_offset_label)
        self.populate_detectors()
        self.push_preview_scan.clicked.connect(self.preview_scan)
        self.push_add_to_manager.clicked.connect(self.add_scan_to_manager)
        self.push_delete_scan.clicked.connect(self.delete_scan)
        self.listWidget_local_manager.doubleClicked.connect(self.local_list_clicked)

        self.figure_trajectory, self.canvas_trajectory, self.toolbar_trajectory  = \
            setup_figure(self, self.layout_trajectory)
        self.figure_trajectory.ax1 = self.figure_trajectory.ax
        self.figure_trajectory.ax2 = self.figure_trajectory.ax.twinx()
        self.update_local_manager_list()

        self.update_exafs_end_values()
        self.enable_exafs_end_field()
        self.edit_exafs_end_k.textChanged.connect(self.update_exafs_end_values)
        self.edit_exafs_end_eV.textChanged.connect(self.update_exafs_end_values)
        self.radioButton_exafs_end_eV.toggled.connect(self.enable_exafs_end_field)
        self.radioButton_exafs_end_k.toggled.connect(self.enable_exafs_end_field)

        self.handle_mono_tabs(self.tabWidget_mono_scan.currentIndex())
        self.tabWidget_mono_scan.tabBarClicked.connect(self.handle_mono_tabs)

        self.handle_xas_step_scan_group(checked=True)
        self.groupBox_step_xas_scan.clicked.connect(self.handle_xas_step_scan_group)
        self.groupBox_step_linear_scan.clicked.connect(self.handle_linear_step_scan_group)

        self.tabWidget_mono_scan_type.tabBarClicked.connect(self.handle_mono_scan_type_tabs)

        # self.handle_spectrometer_tabs()
        self.tabWidget_spectrometer_scan.tabBarClicked.connect(self.handle_spectrometer_tabs)

        self.disable_spectrometer_tabs()
        self.radioButton_spectrometer_none.toggled.connect(self.disable_spectrometer_tabs)
        self.radioButton_spectrometer_johann.toggled.connect(self.enable_spectrometer_johann)
        self.radioButton_spectrometer_von_hamos.toggled.connect(self.enable_spectrometer_vonhamos)

        self.handle_exposure_parameters_crosstalk()
        self.groupBox_constant_energy_exposure_params.toggled.connect(self.handle_exposure_parameters_tab_selection)

        self.dict_presets = {"Regular fly scan": [4, 6, 20],
                        "Regular fly scan with SDD": [12, 18, 60]}
        self.comboBox_fly_scan_presets.addItems(list(self.dict_presets.keys()))
        self.comboBox_fly_scan_presets.currentIndexChanged.connect(self.fly_scan_preset)
        self.comboBox_fly_scan_presets.activated.connect(self.fly_scan_preset)

        self.listWidget_local_manager.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listWidget_local_manager.customContextMenuRequested.connect(self.local_manager_context_menu)

        # self.update_comboBox_spectrometer_config()

    def update_angle_offset_label(self, pvname = None, value=None, char_value=None, **kwargs):
        self.label_angle_offset.setText('{0:.8f}'.format(value))

    def update_exafs_end_values(self):
        try:
            if self.radioButton_exafs_end_k.isChecked() and (not self.radioButton_exafs_end_eV.isChecked()):
                k = float(self.edit_exafs_end_k.text())
                energy = np.round(k2e(k, 0))
                self.edit_exafs_end_eV.setText(str(energy))
            else:
                energy = float(self.edit_exafs_end_eV.text())
                k = np.round(e2k(energy, 0), 2)
                self.edit_exafs_end_k.setText(str(k))
        except ValueError:
            pass

    def enable_exafs_end_field(self):
        if self.radioButton_exafs_end_k.isChecked() and (not self.radioButton_exafs_end_eV.isChecked()):
            self.edit_exafs_end_k.setEnabled(True)
            self.edit_exafs_end_eV.setEnabled(False)
        else:
            self.edit_exafs_end_k.setEnabled(False)
            self.edit_exafs_end_eV.setEnabled(True)

    def handle_mono_tabs(self, index):
        mono_scan = self.tabWidget_mono_scan.tabText(index).lower()
        if mono_scan == 'constant energy':
            self.tabWidget_mono_scan_type.setEnabled(False)
            self.handle_mono_spectrometer_crosstalk(mono_is_fixed=True)
            self.handle_exposure_parameters_crosstalk(mono_is_fixed=True)
        elif mono_scan == 'scan energy':
            self.tabWidget_mono_scan_type.setEnabled(True)
            self.handle_mono_spectrometer_crosstalk(mono_is_fixed=False)
            self.handle_exposure_parameters_crosstalk(mono_is_fixed=False)
            self.handle_xas_edge_parameters_group()

    def handle_mono_scan_type_tabs(self, index):
        mono_scan_type = self.tabWidget_mono_scan_type.tabText(index).lower()
        if mono_scan_type == 'step scan':
            self.handle_xas_edge_parameters_group(step_scan_selected=True)
        else:
            self.handle_xas_edge_parameters_group(step_scan_selected=False, linear_scan_checked=False)

    def handle_xas_edge_parameters_group(self, step_scan_selected=None, linear_scan_checked=None):
        if step_scan_selected is None:
            step_scan_selected = self.tabWidget_mono_scan_type.tabText(self.tabWidget_mono_scan_type.currentIndex()).lower() == 'step scan'
        if linear_scan_checked is None:
            linear_scan_checked = self.groupBox_step_linear_scan.isChecked()

        if step_scan_selected and linear_scan_checked:
            self.groupBox_xas_edge_parameters.setEnabled(False)
        else:
            self.groupBox_xas_edge_parameters.setEnabled(True)

    def handle_spectrometer_tabs(self, index):
        if self.radioButton_spectrometer_johann.isChecked():
            spectrometer_scan = self.tabWidget_spectrometer_scan.tabText(index).lower()
            if spectrometer_scan == 'constant energy':
                self.tabWidget_spectrometer_scan_type.setEnabled(False)
                self.handle_exposure_parameters_crosstalk(is_johann=True, spectrometer_is_fixed=True)
            elif spectrometer_scan == 'scan energy':
                self.tabWidget_spectrometer_scan_type.setEnabled(True)
                self.handle_mono_spectrometer_crosstalk(is_johann=True, spectrometer_is_not_fixed=True)
                self.handle_exposure_parameters_crosstalk(is_johann=True, spectrometer_is_fixed=False)

    def handle_xas_step_scan_group(self, checked=False):
        if checked:
            self.groupBox_step_linear_scan.setChecked(False)
            self.handle_xas_edge_parameters_group(step_scan_selected=True, linear_scan_checked=False)
        else:
            self.groupBox_step_linear_scan.setChecked(True)
            self.handle_xas_edge_parameters_group(step_scan_selected=True, linear_scan_checked=True)

    def handle_linear_step_scan_group(self, checked=False):
        if checked:
            self.groupBox_step_xas_scan.setChecked(False)
            self.handle_xas_edge_parameters_group(step_scan_selected=True, linear_scan_checked=True)
        else:
            self.groupBox_step_xas_scan.setChecked(True)
            self.handle_xas_edge_parameters_group(step_scan_selected=True, linear_scan_checked=False)

    def update_comboBox_spectrometer_config(self):
        self.comboBox_spectrometer_config.clear()
        if self.radioButton_spectrometer_johann.isChecked():
            existing_config_list = [self.johann_spectrometer_manager.generate_config_str(c) for c in self.johann_spectrometer_manager.configs]
            # items = ['Current'] + existing_config_list
            items = existing_config_list[::-1]
            self.comboBox_spectrometer_config.addItems(items)

    def populate_detectors(self):
        detector_names = ['Pilatus 100k New', 'Pilatus 100k', 'Xspress3', 'Ge detector']
        for detector in detector_names:
            qitem = QtWidgets.QCheckBox(detector)
            qitem.setCheckState(False)
            qitem.setTristate(False)
            self.verticalLayout_detectors.addWidget(qitem)

    def disable_spectrometer_tabs(self):
        if self.radioButton_spectrometer_none.isChecked():
            self.tabWidget_spectrometer_scan.setEnabled(False)
            self.tabWidget_spectrometer_scan_type.setEnabled(False)
            self.comboBox_spectrometer_config.setEnabled(False)
            self.update_comboBox_spectrometer_config()
            self.check_aux_detector(False, aux_detector='Pilatus 100k New')
            self.handle_exposure_parameters_crosstalk(spectrometer_is_fixed=True)


    def enable_spectrometer_johann(self):
        if self.radioButton_spectrometer_johann.isChecked():
            self.tabWidget_spectrometer_scan.setEnabled(True)
            self.tabWidget_spectrometer_scan_type.setEnabled(True)
            self.comboBox_spectrometer_config.setEnabled(True)
            self.update_comboBox_spectrometer_config()
            self.check_aux_detector(True, aux_detector='Pilatus 100k New')
            self.handle_mono_spectrometer_crosstalk(is_johann=True)
            self.handle_exposure_parameters_crosstalk(is_johann=True)

    def enable_spectrometer_vonhamos(self):
        if self.radioButton_spectrometer_von_hamos.isChecked():
            self.tabWidget_spectrometer_scan.setEnabled(False)
            self.tabWidget_spectrometer_scan_type.setEnabled(False)
            self.comboBox_spectrometer_config.setEnabled(False)
            self.update_comboBox_spectrometer_config()
            self.check_aux_detector(True, aux_detector='Pilatus 100k New')
            self.handle_exposure_parameters_crosstalk(is_johann=False)

    def handle_mono_spectrometer_crosstalk(self, is_johann=None, mono_is_fixed=None, spectrometer_is_not_fixed=None):
        if mono_is_fixed is None:
            mono_is_fixed = (self._mono_scan == 'constant energy')
        if is_johann is None:
            is_johann = self.radioButton_spectrometer_johann.isChecked()
        if spectrometer_is_not_fixed is None:
            spectrometer_is_not_fixed = (self._spectrometer_scan != 'constant energy')
        if mono_is_fixed and is_johann and spectrometer_is_not_fixed:
            self.spectrometer_dwell_setEnabled(True)
        else:
            self.spectrometer_dwell_setEnabled(False)

    def spectrometer_dwell_setEnabled(self, state):
        self.label_spectrometer_dwell.setEnabled(state)
        self.edit_preline_dwell.setEnabled(state)
        self.edit_mainline_dwell.setEnabled(state)
        self.edit_postline_dwell.setEnabled(state)
        self.label_preline.setEnabled(state)
        self.label_mainline.setEnabled(state)
        self.label_postline.setEnabled(state)
        self.label_preline_dwell_units.setEnabled(state)
        self.label_mainline_dwell_units.setEnabled(state)
        self.label_postline_dwell_units.setEnabled(state)

    def handle_exposure_parameters_tab_selection(self, state):
        if state:
            if self.tabWidget_mono_scan.currentIndex() != 1:
                self.tabWidget_mono_scan.setCurrentIndex(1) # switch to constant energy tab
                self.handle_mono_tabs(1) # and handle it
            if self.radioButton_spectrometer_johann.isChecked():
                if self.tabWidget_spectrometer_scan.currentIndex() != 1:
                    self.tabWidget_spectrometer_scan.setCurrentIndex(1)  # switch to constant energy tab
                    self.handle_spectrometer_tabs(1)  # and handle it


    def handle_exposure_parameters_crosstalk(self, mono_is_fixed=None, is_johann=None, spectrometer_is_fixed=None):
        if mono_is_fixed is None:
            mono_is_fixed = (self._mono_scan == 'constant energy')
        if is_johann is None:
            is_johann = self.radioButton_spectrometer_johann.isChecked()
        if not is_johann:
            spectrometer_is_fixed = True
        if spectrometer_is_fixed is None:
            spectrometer_is_fixed = (self._spectrometer_scan == 'constant energy')
        if mono_is_fixed and spectrometer_is_fixed:
            self.groupBox_constant_energy_exposure_params.setChecked(True)
        else:
            self.groupBox_constant_energy_exposure_params.setChecked(False)



    def check_aux_detector(self, check_state, aux_detector='Pilatus 100k'):
        for j in range(1, self.verticalLayout_detectors.count()):
            checkBox = self.verticalLayout_detectors.itemAt(j).widget()
            if checkBox.text() == aux_detector:
                checkBox.setChecked(check_state)

    @property
    def _mono_scan(self):
        return self.tabWidget_mono_scan.tabText(self.tabWidget_mono_scan.currentIndex()).lower()
        #WIP

    @property
    def _mono_scan_type(self):
        if self._mono_scan == 'scan energy':
            return self.tabWidget_mono_scan_type.tabText(self.tabWidget_mono_scan_type.currentIndex()).lower()
        else:
            return 'constant energy'

    @property
    def _traj_dict(self):
        if self.radioButton_flypath_standard.isChecked():
             traj_dict = {'type': 'standard',
                          'preedge_duration': float(self.edit_ds2_pree_duration.text()),
                          'edge_duration': float(self.edit_ds2_edge_duration.text()),
                          'postedge_duration': float(self.edit_ds2_poste_duration.text()),
                          'preedge_flex': float(self.edit_preedge_flex_frac.text()),
                          'postedge_flex': float(self.edit_postedge_flex_frac.text())}
        elif self.radioButton_flypath_doublesine.isChecked():
            traj_dict = {'type': 'double_sine',
                         'preedge_duration': float(self.edit_ds_pree_duration.text()),
                         'postedge_duration': float(self.edit_ds_poste_duration.text())}
        elif self.radioButton_flypath_sine.isChecked():
            traj_dict = {'type': 'sine',
                         'duration': float(self.edit_sine_total_duration.text())}

        traj_common = {'pad': float(self.edit_pad_time.text()),
                       'repeat': int(self.spinBox_tiling_repetitions.value()),
                       'single_direction': self.checkBox_traj_single_dir.isChecked(),
                       'revert': self.checkBox_traj_revert.isChecked(),
                       'filename' : ''}

        return {**traj_dict, **traj_common}


    @property
    def _step_dict(self):
        return {'grid_kind' : 'xas',
                'preedge_stepsize': float(self.edit_preedge_spacing.text()),
                'XANES_stepsize': float(self.edit_xanes_spacing.text()),
                'EXAFS_stepsize': float(self.edit_exafs_spacing.text()),
                'preedge_dwelltime': float(self.edit_preedge_dwell.text()),
                'XANES_dwelltime': float(self.edit_xanes_dwell.text()),
                'EXAFS_dwelltime': float(self.edit_exafs_dwell.text()),
                'k_power': int(self.comboBox_exafs_dwell_kpower.currentText()),
                'revert': self.checkBox_energy_down.isChecked()}

    @property
    def _linear_step_dict(self):
        return {'grid_kind': 'linear',
                'energy_min': float(self.edit_linear_scan_start.text()),
                'energy_max': float(self.edit_linear_scan_end.text()),
                'energy_step': float(self.edit_linear_scan_spacing.text()),
                'dwell_time': float(self.edit_linear_scan_dwell.text()),
                'revert': self.checkBox_energy_down.isChecked(),
                'element': '',
                'edge': '',
                'e0': 0}

    @property
    def _mono_scan_parameters(self):
        scan_type = self._mono_scan_type
        if scan_type == 'constant energy':
            scan_parameters = {'energy' : self.doubleSpinBox_mono_energy.value()}
            if self.groupBox_constant_energy_exposure_params.isChecked():
                scan_parameters['dwell_time'] = self.doubleSpinBox_dwell_time.value()
                scan_parameters['n_exposures'] = self.spinBox_n_exposures.value()
        else:
            if (scan_type == 'step scan') and self.groupBox_step_linear_scan.isChecked():
                scan_parameters = self._linear_step_dict
            else:
                scan_parameters_common = {'element': self.widget_energy_selector.comboBox_element.currentText(),
                                          'edge': self.widget_energy_selector.comboBox_edge.currentText(),
                                          'e0': float(self.widget_energy_selector.edit_E0.text()),
                                          'preedge_start': float(self.edit_preedge_start.text()),
                                          'XANES_start': float(self.edit_xanes_start.text()),
                                          'XANES_end': float(self.edit_xanes_end.text()),
                                          'EXAFS_end': float(self.edit_exafs_end_k.text())}

                if scan_type == 'fly scan':
                    scan_parameters =  {**scan_parameters_common, **self._traj_dict}
                elif scan_type == 'step scan':
                    scan_parameters = {**scan_parameters_common, **self._step_dict}
        return {'scan_type' : scan_type,
                'scan_parameters' : scan_parameters}

    @property
    def _aux_parameters(self):
        return_dict = {'detectors' : self._scan_detectors,
                       'offset' : float(self.label_angle_offset.text())}
        if not self.radioButton_spectrometer_none.isChecked():
            return_dict['spectrometer'] = self._spectrometer_parameters
        return_dict['scan_for_calibration_purpose'] = self.checkBox_calibration_purpose.isChecked()
        return return_dict

    @property
    def _scan_detectors(self):
        det_list = []
        for j in range(1, self.verticalLayout_detectors.count()):
            checkBox = self.verticalLayout_detectors.itemAt(j).widget()
            if checkBox.isChecked():
                det_list.append(checkBox.text())
        return det_list

    @property
    def _spectrometer_scan(self):
        return self.tabWidget_spectrometer_scan.tabText(self.tabWidget_spectrometer_scan.currentIndex()).lower()

    @property
    def _spectrometer_scan_type(self):
        if self._spectrometer_scan == 'scan energy':
            return self.tabWidget_spectrometer_scan_type.tabText(self.tabWidget_spectrometer_scan_type.currentIndex()).lower()
        else:
            return 'constant energy'

    @property
    def _spectromer_config_uid(self):
        # if self.comboBox_spectrometer_config.currentText() == 'Current':
        #     return None
        n_configs = len(self.johann_spectrometer_manager.configs)
        index = n_configs - 1 - self.comboBox_spectrometer_config.currentIndex()
        return self.johann_spectrometer_manager.configs[index]['uid']

    @property
    def _spectrometer_parameters(self):

        if self.radioButton_spectrometer_von_hamos.isChecked():
            return {'kind': 'von_hamos',
                    'scan_type': 'constant energy',
                    'scan_parameters': {}} # just in case

        elif self.radioButton_spectrometer_johann.isChecked():
            scan_type = self._spectrometer_scan_type
            spectrometer_config_uid = self._spectromer_config_uid
            if scan_type == 'constant energy':
                scan_parameters = {'energy' : self.doubleSpinBox_spectrometer_energy.value()}
            else:
                scan_parameters_common = {'element': self.widget_emission_energy.comboBox_element.currentText(),
                                          'line': self.widget_emission_energy.comboBox_line.currentText(),
                                          'e0': float(self.widget_emission_energy.edit_E.text()),
                                          'preline_start': float(self.edit_preline_start.text()),
                                          'mainline_start': float(self.edit_line_start.text()),
                                          'mainline_end': float(self.edit_line_end.text()),
                                          'postline_end': float(self.edit_postline_end.text()),
                                          'revert' : self.checkBox_spectrometer_energy_down.isChecked()}
                if scan_type == 'fly scan':
                    scan_parameters = {**scan_parameters_common, **self._spectrometer_duration_dict}
                    # raise NotImplementedError('Emission Fly scans are not implemented yet')
                elif scan_type == 'step scan':
                    scan_parameters = {**scan_parameters_common, **self._spectrometer_step_dict}

            return {'kind': 'johann',
                    'scan_type': scan_type,
                    'spectrometer_config_uid': spectrometer_config_uid,
                    'scan_parameters': scan_parameters}


    @property
    def _spectrometer_step_dict(self):
        output = {'preline_stepsize': float(self.edit_preline_spacing.text()),
                  'mainline_stepsize': float(self.edit_mainline_spacing.text()),
                  'postline_stepsize': float(self.edit_postline_spacing.text()),
                  'revert': self.checkBox_spectrometer_energy_down.isChecked()}
        if self._mono_scan_type == 'constant energy':
            emission_dwell_dict = {'preline_dwelltime': float(self.edit_preline_dwell.text()),
                                   'mainline_dwelltime': float(self.edit_mainline_dwell.text()),
                                   'postline_dwelltime': float(self.edit_postline_dwell.text())}
            output = {**output, **emission_dwell_dict}
        return output

    @property
    def _spectrometer_duration_dict(self):
        output = {'revert': self.checkBox_spectrometer_fly_energy_down.isChecked()}
        if self._mono_scan_type != 'fly scan':
            emission_dwell_dict = {'preline_duration': float(self.edit_preline_fly_duration.text()),
                                   'mainline_duration': float(self.edit_mainline_fly_duration.text()),
                                   'postline_duration': float(self.edit_postline_fly_duration.text())}
            output = {**output, **emission_dwell_dict}
        return output

    def preview_scan(self, keep_scan_name=False):
        self.mono_scan_parameters = self._mono_scan_parameters
        self.aux_parameters = self._aux_parameters
        self.scan_manager.create_scan_preview(self.mono_scan_parameters,
                                              self.aux_parameters,
                                              self.plot_trajectory_func)
        if not keep_scan_name:
            signature  = f'{self.widget_energy_selector.comboBox_element.currentText()}-' \
                         f'{self.widget_energy_selector.comboBox_edge.currentText()}'
            print(signature)
            self.lineEdit_scan_name.setText(signature)


    def add_scan_to_manager(self):
        name = self.lineEdit_scan_name.text()
        if name !='':
            name = remove_special_characters(name)
            self.preview_scan(keep_scan_name=True)
            self.scan_manager.add_scan(self.mono_scan_parameters,
                                       self.aux_parameters,
                                       name)
            self.update_local_manager_list()
        else:
            message_box('Warning', 'Scan name is empty')

    def plot_trajectory_func(self, x, y):

        update_figure([self.figure_trajectory.ax1,self.figure_trajectory.ax2 ],
                          self.toolbar_trajectory,
                          self.canvas_trajectory)
        self.figure_trajectory.ax1.plot(x, y)
        self.figure_trajectory.ax1.set_xlabel('Time, s')
        self.figure_trajectory.ax1.set_ylabel('Energy, eV')
        self.figure_trajectory.ax2.plot(x[:-1], np.diff(y) / np.diff(x), 'r--')
        self.figure_trajectory.ax2.set_ylabel('Velocity (eV/s)')
        self.figure_trajectory.ax1.set_xlim(x.min(), x.max())
        self.figure_trajectory.ax2.set_xlim(x.min(), x.max())
        self.canvas_trajectory.draw_idle()

    def update_local_manager_list(self):
        self.listWidget_local_manager.clear()
        for scan in self.scan_manager.scan_list_local:
            if not scan['archived']:
                scan_defs = scan['scan_def']
                self.listWidget_local_manager.addItem(scan_defs)
        self.scansChanged.emit()


    def delete_scan(self):
        selection = self.listWidget_local_manager.selectedIndexes()
        if selection != []:
            self.scan_manager.delete_local_scan(selection[0].row())
            self.update_local_manager_list()

    def local_list_clicked(self):
        selection = self.listWidget_local_manager.selectedIndexes()
        if selection != []:
            local_scan = self.scan_manager.scan_list_local[selection[0].row()]
            uid = local_scan['uid']
            global_scan = self.scan_manager.scan_dict[uid]
            params = ''
            # detectors = local_scan['aux_parameters']['detectors']
            scan_aux_parameters = local_scan['aux_parameters']
            for k, v in global_scan['scan_parameters'].items():
                params += f' {k}: {v} \n'
            params += '\nAux parameters\n'
            for k, v in scan_aux_parameters.items():
                params += f' {k}: {v} \n'
            scan_info = f" {local_scan['scan_def']} \n UID: {uid} \n\n Scan parameters \n {params}"
            message_box('Scan information', scan_info)

    def populate_fields_with_scan_parameters(self):
        selection = self.listWidget_local_manager.selectedIndexes()
        if selection != []:
            local_scan = self.scan_manager.scan_list_local[selection[0].row()]
            uid = local_scan['uid']
            global_scan = self.scan_manager.scan_dict[uid]

            scan_parameters = global_scan['scan_parameters']
            aux_parameters = local_scan['aux_parameters']

            if global_scan['scan_type'] == 'constant energy':
                self.tabWidget_mono_scan.setCurrentIndex(1)
                self.tabWidget_mono_scan.tabBarClicked.emit(1)
                self.doubleSpinBox_mono_energy.setValue(scan_parameters['energy'])
            else:
                self.tabWidget_mono_scan.setCurrentIndex(0)
                self.tabWidget_mono_scan.tabBarClicked.emit(0)
                for i in range(self.widget_energy_selector.comboBox_element.count()):
                    if self.widget_energy_selector.comboBox_element.itemText(i) == scan_parameters['element']:
                        self.widget_energy_selector.comboBox_element.setCurrentIndex(i)
                for i in range(self.widget_energy_selector.comboBox_edge.count()):
                    if self.widget_energy_selector.comboBox_edge.itemText(i) == scan_parameters['edge']:
                        self.widget_energy_selector.comboBox_edge.setCurrentIndex(i)
                self.widget_energy_selector.edit_E0.setText(str(int(scan_parameters['e0'])))
                self.edit_preedge_start.setText(str(int(scan_parameters['preedge_start'])))
                self.edit_xanes_start.setText(str(int(scan_parameters['XANES_start'])))
                self.edit_xanes_end.setText(str(int(scan_parameters['XANES_end'])))
                self.edit_exafs_end_k.setText(str(int(scan_parameters['EXAFS_end'])))

            for i in range(self.widget_energy_selector.comboBox_element.count()):
                if self.widget_energy_selector.comboBox_element.itemText(i) == scan_parameters['element']:
                    self.widget_energy_selector.comboBox_element.setCurrentIndex(i)
            for i in range(self.widget_energy_selector.comboBox_edge.count()):
                if self.widget_energy_selector.comboBox_edge.itemText(i) == scan_parameters['edge']:
                    self.widget_energy_selector.comboBox_edge.setCurrentIndex(i)
            self.widget_energy_selector.edit_E0.setText(str(int(scan_parameters['e0'])))

            self.edit_preedge_start.setText(str(int(scan_parameters['preedge_start'])))
            self.edit_xanes_start.setText(str(int(scan_parameters['XANES_start'])))
            self.edit_xanes_end.setText(str(int(scan_parameters['XANES_end'])))
            self.edit_exafs_end_k.setText(str(int(scan_parameters['EXAFS_end'])))

            if global_scan['scan_type'] == 'fly scan':
                self.tabWidget_mono_scan_type.setCurrentIndex(0)
                self.tabWidget_mono_scan_type.tabBarClicked.emit(0)

                if global_scan['scan_parameters']['type'] == 'standard':
                    self.radioButton_flypath_standard.setChecked(1)
                    self.edit_ds2_pree_duration.setText(str(scan_parameters['preedge_duration']))
                    self.edit_ds2_edge_duration.setText(str(scan_parameters['edge_duration']))
                    self.edit_ds2_poste_duration.setText(str(scan_parameters['postedge_duration']))
                    self.edit_preedge_flex_frac.setText(str(scan_parameters['preedge_flex']))
                    self.edit_postedge_flex_frac.setText(str(scan_parameters['postedge_flex']))
                elif global_scan['scan_parameters']['type'] == 'double_sine':
                    self.radioButton_flypath_doublesine.setChecked(1)
                    self.edit_ds_pree_duration.setText(str(scan_parameters['preedge_duration']))
                    self.edit_ds_poste_duration.setText(str(scan_parameters['postedge_duration']))
                elif global_scan['scan_parameters']['type'] == 'sine':
                    self.radioButton_flypath_sine.setChecked(1)
                    self.edit_sine_total_duration.setText(str(scan_parameters['duration']))
                self.edit_pad_time.setText(str(scan_parameters['pad']))
                self.spinBox_tiling_repetitions.setValue(scan_parameters['repeat'])
                self.checkBox_traj_single_dir.setChecked(scan_parameters['single_direction'])
                self.checkBox_traj_revert.setChecked(scan_parameters['revert'])
            else:
                self.tabWidget_mono_scan_type.setCurrentIndex(1)
                self.tabWidget_mono_scan_type.tabBarClicked.emit(1)
                self.checkBox_energy_down.setChecked(scan_parameters['revert'])
                if scan_parameters['grid_kind'] == 'xas':
                    self.groupBox_step_xas_scan.setChecked(True)
                    self.edit_preedge_spacing.setText(str(scan_parameters['preedge_stepsize']))
                    self.edit_xanes_spacing.setText(str(scan_parameters['XANES_stepsize']))
                    self.edit_exafs_spacing.setText(str(scan_parameters['EXAFS_stepsize']))
                    self.edit_preedge_dwell.setText(str(scan_parameters['preedge_dwelltime']))
                    self.edit_xanes_dwell.setText(str(scan_parameters['XANES_dwelltime']))
                    self.edit_exafs_dwell.setText(str(scan_parameters['EXAFS_dwelltime']))
                    self.comboBox_exafs_dwell_kpower.setCurrentIndex(scan_parameters['k_power'])

                elif scan_parameters['grid_kind'] == 'linear':
                    self.groupBox_step_linear_scan.setChecked(True)
                    self.edit_linear_scan_start.setText(str(scan_parameters['energy_min']))
                    self.edit_linear_scan_end.setText(str(scan_parameters['energy_max']))
                    self.edit_linear_scan_spacing.setText(str(scan_parameters['energy_step']))
                    self.edit_linear_scan_dwell.setText(str(scan_parameters['dwell_time']))

            if 'spectrometer' in aux_parameters.keys():
                spectrometer_parameters = aux_parameters['spectrometer']
                if spectrometer_parameters['kind'] == 'johann':
                    spectrometer_scan_parameters = spectrometer_parameters['scan_parameters']
                    spectrometer_config_string = self.johann_spectrometer_manager.generate_config_str_from_uid(spectrometer_parameters['spectrometer_config_uid'])
                    for i in range(self.comboBox_spectrometer_config.count()):
                        if self.comboBox_spectrometer_config.itemText(i) == spectrometer_config_string:
                            self.comboBox_spectrometer_config.setCurrentIndex(i)

                    if spectrometer_parameters['scan_type'] == 'constant energy':
                        self.tabWidget_spectrometer_scan.setCurrentIndex(1)
                        self.tabWidget_spectrometer_scan.tabBarClicked.emit(1)
                        self.doubleSpinBox_spectrometer_energy.setValue(spectrometer_scan_parameters['energy'])

                    else:
                        self.tabWidget_spectrometer_scan.setCurrentIndex(0)
                        self.tabWidget_spectrometer_scan.tabBarClicked.emit(1)
                        for i in range(self.widget_emission_energy.comboBox_element.count()):
                            if self.widget_emission_energy.comboBox_element.itemText(i) == spectrometer_scan_parameters['element']:
                                self.widget_emission_energy.comboBox_element.setCurrentIndex(i)
                        for i in range(self.widget_emission_energy.comboBox_line.count()):
                            if self.widget_emission_energy.comboBox_line.itemText(i) == spectrometer_scan_parameters['line']:
                                self.widget_emission_energy.comboBox_line.setCurrentIndex(i)
                        self.widget_emission_energy.edit_E.setText(str(int(spectrometer_scan_parameters['e0'])))
                        self.edit_preline_start.setText(str(spectrometer_scan_parameters['preline_start']))
                        self.edit_line_start.setText(str(spectrometer_scan_parameters['mainline_start']))
                        self.edit_line_end.setText(str(spectrometer_scan_parameters['mainline_end']))
                        self.edit_postline_end.setText(str(spectrometer_scan_parameters['postline_end']))
                        if spectrometer_parameters['scan_type'] == 'step scan':
                            self.edit_preline_spacing.setText(str(spectrometer_scan_parameters['preline_stepsize']))
                            self.edit_mainline_spacing.setText(str(spectrometer_scan_parameters['mainline_stepsize']))
                            self.edit_postline_spacing.setText(str(spectrometer_scan_parameters['postline_stepsize']))
                            self.checkBox_spectrometer_energy_down.setChecked(spectrometer_scan_parameters['revert'])
                            if global_scan['scan_type'] == 'constant energy':
                                self.edit_preline_dwell.setText(str(spectrometer_scan_parameters['preline_dwelltime']))
                                self.edit_mainline_dwell.setText(str(spectrometer_scan_parameters['mainline_dwelltime']))
                                self.edit_postline_dwell.setText(str(spectrometer_scan_parameters['postline_dwelltime']))

                elif spectrometer_parameters['kind'] == 'von_hamos':
                    self.radioButton_spectrometer_von_hamos.setChecked(True)

            else:
                self.radioButton_spectrometer_none.setChecked(True)

            # handle dwell time and exposures
            if ((global_scan['scan_type'] == 'constant energy') and
                ()):
                pass


            self.checkBox_calibration_purpose.setChecked(aux_parameters['scan_for_calibration_purpose'])

            self.lineEdit_scan_name.setText(local_scan['scan_name'])




            # detectors = local_scan['aux_parameters']['detectors']


    def update_offset(self):
        offset = float(self.label_angle_offset.text())
        energy = float(self.widget_energy_selector.edit_E0.text())
        dlg = UpdateAngleOffset.UpdateAngleOffset(offset, energy, parent=self)
        if dlg.exec_():
            try:
                values = dlg.getValues()
                if len(values) == 1:
                    offset = values[0]
                    self.hhm.angle_offset.put(float(offset))
                    self.update_angle_offset_label(value=float(dlg.getValues()))
                elif len(values) == 2:
                    old_energy_str, new_energy_str = values
                    # self.hhm.calibrate(float(old_energy_str), float(new_energy_str))
                    self.hhm.calibrate(float(new_energy_str), float(old_energy_str))
                    self.update_angle_offset_label(value=self.hhm.angle_offset.get())
                message_box('Warning', 'The new calibration will be applied only to new scans.\nIf you want new calibration to apply to old scans, you will have to redefine/recreate them.')
            except Exception as exc:
                if type(exc) == ophyd_utils.errors.LimitError:
                    print('[New offset] {}. No reason to be desperate, though.'.format(exc))
                else:
                    print('[New offset] Something went wrong, not the limit: {}'.format(exc))


    def fly_scan_preset(self):
        fly_scan_parameters =self.dict_presets[self.comboBox_fly_scan_presets.currentText()]
        self.edit_ds2_pree_duration.setText(str(fly_scan_parameters[0]))
        self.edit_ds2_edge_duration.setText(str(fly_scan_parameters[1]))
        self.edit_ds2_poste_duration.setText(str(fly_scan_parameters[2]))



    def local_manager_context_menu(self, QPos):
        menu = QMenu()
        change_offset = menu.addAction("&Update scan angular offset to current")
        populate_fields = menu.addAction("&Populate fields with scan parameters")
        parentPosition = self.listWidget_local_manager.mapToGlobal(QtCore.QPoint(0, 0))
        menu.move(parentPosition + QPos)
        action = menu.exec_()
        if action == change_offset:
            self.change_offset_for_local_scan()
        elif action == populate_fields:
            self.populate_fields_with_scan_parameters()

    def change_offset_for_local_scan(self):
        # print('dont worry - nothing happens')
        selection = self.listWidget_local_manager.selectedIndexes()
        indexes = [sel.row() for sel in selection]
        self.scan_manager.update_local_scan_offset_to_current(indexes)
        # self.update_local_manager_list()

    # def populate_fields_with_scan_parameters(self):
    #     pass
