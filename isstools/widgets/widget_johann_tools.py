import json
import pkg_resources
from qtpy import uic, QtWidgets, QtCore
from isstools.widgets import widget_emission_energy_selector
import bluesky.plan_stubs as bps
from xas.spectrometer import Crystal
import pandas as pd
ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_johann_spectrometer.ui')
from isstools.elements.figure_update import update_figure_with_colorbar, update_figure, setup_figure
# from isstools.dialogs import (MoveMotorDialog)
from xas.spectrometer import analyze_elastic_scan
import os
from isstools.dialogs.BasicDialogs import message_box
import numpy as np
from xas.spectrometer import analyze_many_elastic_scans
from xas.fitting import Nominal2ActualConverter
from bluesky.callbacks import LivePlot


class UIJohannTools(*uic.loadUiType(ui_path)):
    def __init__(self, parent=None,
                 db=None,
                 RE=None,
                 plan_processor=None,
                 hhm=None,
                 johann_emission=None,
                 motor_dictionary=None,
                 detector_dictionary=None,
                 aux_plan_funcs=None,
                 service_plan_funcs=None,
                 embedded_run_scan_func=None,
                 figure_proc=None,
                 canvas_proc=None,
                 toolbar_proc=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.motor_dictionary = motor_dictionary
        self.detector_dictionary = detector_dictionary
        self.aux_plan_funcs = aux_plan_funcs
        self.service_plan_funcs = service_plan_funcs
        self.RE = RE
        self.plan_processor = plan_processor
        self.db = db

        self.hhm=hhm
        self.johann_emission = johann_emission

        self.figure_proc = figure_proc,
        self.canvas_proc = canvas_proc,
        self.toolbar_proc = toolbar_proc

        self._run_any_scan = embedded_run_scan_func

        self.settings = parent.parent.settings
        self._cur_alignment_motor = None

        self.widget_emission_energy = widget_emission_energy_selector.UIEmissionEnergySelector(parent=self)
        self.layout_emission_energy.addWidget(self.widget_emission_energy)

        self.push_update_crystal_parking.clicked.connect(self.update_crystal_parking)
        self.push_park_crystal.clicked.connect(self.park_crystal)
        self.push_set_default_soft_limits.clicked.connect(self.set_default_soft_limits)
        self.push_compute_crystal_position.clicked.connect(self.compute_crystal_position)
        self.push_move_crystal.clicked.connect(self.move_crystal)
        self.comboBox_johann_tweak_motor.currentIndexChanged.connect(self.update_tweak_motor)

        self.push_tweak_down.clicked.connect(self.tweak_down)
        self.push_tweak_up.clicked.connect(self.tweak_up)

        for chan in self.detector_dictionary['Pilatus 100k']['channels']:
            self.comboBox_pilatus_channels.addItem(chan)

        self.comboBox_pilatus_channels.setCurrentIndex(self.settings.value('johann_alignment_pilatus_channel', defaultValue=0, type=int))
        self.comboBox_pilatus_channels.currentIndexChanged.connect(self.update_pilatus_channel_selection)

        # self.push_scan_crystal_y.clicked.connect(self.scan_crystal_y)
        self.push_scan_energy.clicked.connect(self.scan_energy)

        self.spinBox_crystal_park_x.setValue(self.settings.value('johann_crystal_park_x', defaultValue=0, type=float))
        self.spinBox_crystal_park_y.setValue(self.settings.value('johann_crystal_park_y', defaultValue=0, type=float))

        self.spinBox_bragg_angle_nom.setValue(self.settings.value('johann_bragg_angle_nom', defaultValue=0))
        self.spinBox_crystal_nom_x.setValue(self.settings.value('johann_crystal_x_nom', defaultValue=0))
        self.spinBox_crystal_nom_y.setValue(self.settings.value('johann_crystal_y_nom', defaultValue=0))
        self.spinBox_det_nom_y.setValue(self.settings.value('johann_det_nom_y', defaultValue=0))
        self.spinBox_crystal_stage_nom_x.setValue(self.settings.value('crystal_stage_nom_x', defaultValue=0))
        self.spinBox_crystal_stage_nom_y.setValue(self.settings.value('crystal_stage_nom_y', defaultValue=0))

        self.update_tweak_motor()

        _tweak_motor_list = [self.comboBox_johann_tweak_motor.itemText(i)
                             for i in range(self.comboBox_johann_tweak_motor.count())]
        self._alignment_data = pd.DataFrame(columns=_tweak_motor_list + ['fwhm', 'ecen', 'uid'])
        self._calibration_data = pd.DataFrame(columns=['energy_nom', 'energy_act', 'fwhm', 'uid'])


        self.edit_reg_E.setText(self.settings.value('johann_registration_energy', defaultValue='9000'))
        self.edit_reg_E_lo.setText(self.settings.value('johann_registration_energy_lo', defaultValue='8900'))
        self.edit_reg_E_hi.setText(self.settings.value('johann_registration_energy_hi', defaultValue='9100'))
        self.edit_reg_E.textChanged.connect(self.update_soft_energy_limits)
        self.edit_reg_E_lo.textChanged.connect(self.update_settings_reg_E_lo)
        self.edit_reg_E_hi.textChanged.connect(self.update_settings_reg_E_hi)

        self.lineEdit_current_spectrometer_file.setText(self.settings.value('johann_registration_file_str', defaultValue=''))
        self.lineEdit_current_spectrometer_file.textChanged.connect(self.update_settings_current_spectrometer_file)

        self.align_motor_dict = {'Spectrometer X' : 'johann_x',
                                 'Bender' : 'bender'}

        self.push_initialize_emission_motor.clicked.connect(self.initialize_emission_motor)
        # self.push_save_emission_motor.clicked.connect(self.save_emission_motor)
        self.push_select_config_file.clicked.connect(self.select_config_file)
        self.push_load_emission_motor.clicked.connect(self.load_emission_motor)
        self.push_calibrate_energy.clicked.connect(self.calibrate_energy)
        self.push_save_calibration.clicked.connect(self.save_energy_calibration)
        self.push_select_calibration.clicked.connect(self.select_energy_calibration_file)
        self.push_load_calibration.clicked.connect(self.load_energy_calibration)

        self.edit_E_calib_min.textChanged.connect(self.update_settings_calib_E_min)




        self.lineEdit_current_calibration_file.setText(self.settings.value('johann_calibration_file_str', defaultValue=''))
        self.lineEdit_current_calibration_file.textChanged.connect(self.update_settings_current_calibration_file)

        self._update_crystal_info()

        # if self.johann_emission._initialized:
        #     self.parent.parent.widget_info_beamline.push_set_emission_energy.setEnabled(1)



    def update_crystal_parking(self):
        park_x = self.motor_dictionary['auxxy_x']['object'].user_readback.get()
        park_y = self.motor_dictionary['auxxy_y']['object'].user_readback.get()
        self.spinBox_crystal_park_x.setValue(park_x)
        self.spinBox_crystal_park_y.setValue(park_y)
        self.settings.setValue('johann_crystal_park_x', park_x)
        self.settings.setValue('johann_crystal_park_y', park_y)


    def park_crystal(self):
        x = self.spinBox_crystal_park_x.value()
        y = self.spinBox_crystal_park_y.value()

        self.RE(bps.mv(self.motor_dictionary['auxxy_x']['object'], x))
        self.RE(bps.mv(self.motor_dictionary['auxxy_y']['object'], y))


    def set_default_soft_limits(self, *, dx_hi=50, dx_lo=50, dy_hi=50, dy_lo=50):
        motor_x = self.motor_dictionary['auxxy_x']['object']
        motor_y = self.motor_dictionary['auxxy_y']['object']

        x_cur = motor_x.user_readback.get()
        y_cur = motor_y.user_readback.get()

        motor_x.high_limit_travel.put(x_cur + dx_hi)
        motor_x.low_limit_travel.put(x_cur - dx_lo)

        motor_y.high_limit_travel.put(y_cur + dy_hi)
        motor_y.low_limit_travel.put(y_cur - dy_lo)


    def compute_crystal_position(self):
        energy = float(self.widget_emission_energy.edit_E.text())
        self._update_crystal_info()
        R = float(self.widget_emission_energy.edit_crystal_R.text())
        cr = Crystal(R, 100, self._hkl, self._kind)
        cr.place_E(energy)
        bragg_angle = cr.ba_deg
        cr_x = cr.x
        cr_y = cr.y
        det_y = cr.d_y
        cr_x_stage = self.spinBox_crystal_park_x.value() + (R - cr_x)
        cr_y_stage = self.spinBox_crystal_park_y.value() + cr_y

        self.spinBox_bragg_angle_nom.setValue(bragg_angle)
        self.spinBox_crystal_nom_x.setValue(cr_x)
        self.spinBox_crystal_nom_y.setValue(cr_y)
        self.spinBox_det_nom_y.setValue(det_y)

        self.spinBox_crystal_stage_nom_x.setValue(cr_x_stage)
        self.spinBox_crystal_stage_nom_y.setValue(cr_y_stage)

        self.settings.setValue('johann_bragg_angle_nom', bragg_angle)
        self.settings.setValue('johann_crystal_x_nom', cr_x)
        self.settings.setValue('johann_crystal_y_nom', cr_y)
        self.settings.setValue('johann_det_nom_y', det_y)

        self.settings.setValue('crystal_stage_nom_x', cr_x_stage)
        self.settings.setValue('crystal_stage_nom_y', cr_y_stage)

    def _update_crystal_info(self):
        self._R = float(self.widget_emission_energy.edit_crystal_R.text())
        self._kind = self.widget_emission_energy.comboBox_crystal_kind.currentText()
        _reflection = self.widget_emission_energy.lineEdit_reflection.text()
        _reflection = _reflection.replace(')','').replace('(','').replace(',','')
        self._hkl = [int(i) for i in _reflection]


    def move_crystal(self):
        motor_x = self.motor_dictionary['auxxy_x']['object']
        motor_y = self.motor_dictionary['auxxy_y']['object']

        x = self.spinBox_crystal_stage_nom_x.value()
        y = self.spinBox_crystal_stage_nom_y.value()

        self.RE(bps.mv(motor_x, x))
        self.RE(bps.mv(motor_y, y))

    def update_tweak_motor(self):
        value = self.comboBox_johann_tweak_motor.currentText()
        if value == 'Crystal X':
            motor = self.motor_dictionary['auxxy_x']['object']
            step_size = 2.5
        elif value == 'Bender':
            motor = self.motor_dictionary['bender']['object']
            step_size = 5
        elif value == 'Crystal Z':
            motor = self.motor_dictionary['usermotor1']['object']
            step_size = 2.5

        self.doubleSpinBox_tweak_motor_step.setValue(step_size)
        pos = motor.user_readback.get()
        self.doubleSpinBox_tweak_motor_pos.setValue(pos)
        self._cur_alignment_motor = motor

    def update_pilatus_channel_selection(self):
        idx = self.comboBox_pilatus_channels.currentIndex()
        self.settings.setValue('johann_alignment_pilatus_channel', idx)

    def tweak_up(self):
        self._tweak(1)

    def tweak_down(self):
        self._tweak(-1)

    def _tweak(self, direction):
        motor = self._cur_alignment_motor
        step = self.doubleSpinBox_tweak_motor_step.value()
        self.RE(bps.mvr(motor, direction * step))
        pos = motor.user_readback.get()
        self.doubleSpinBox_tweak_motor_pos.setValue(pos)

    # def scan_crystal_y(self):
    #
    #     detectors = ['Pilatus 100k']
    #     channel = self.comboBox_pilatus_channels.currentText()
    #     liveplot_det_kwargs = {'channel': channel, 'channel_den': '1', 'result_name': channel}
    #
    #     curr_mot = 'Crystal Y'
    #     for motor_key, motor_dict in self.motor_dictionary.items():
    #         if curr_mot == motor_dict['description']:
    #             liveplot_mot_kwargs = {'curr_mot_name': motor_dict['object'].name}
    #             break
    #
    #     scan_range = self.doubleSpinBox_range_crystal_y.value()
    #     scan_step = self.doubleSpinBox_step_crystal_y.value()
    #     self._run_any_scan(detectors, liveplot_det_kwargs, curr_mot, liveplot_mot_kwargs, scan_range, scan_step)


    def scan_energy(self):

        detectors = ['Pilatus 100k']
        channel = self.comboBox_pilatus_channels.currentText()
        liveplot_det_kwargs = {'channel': channel, 'channel_den': '1', 'result_name': channel}

        curr_mot = 'A Monochromator Energy'
        for motor_key, motor_dict in self.motor_dictionary.items():
            if curr_mot == motor_dict['description']:
                liveplot_mot_kwargs = {'curr_mot_name': motor_dict['object'].name}
                break

        scan_range = self.doubleSpinBox_range_energy.value()
        scan_step = self.doubleSpinBox_step_energy.value()
        self._run_any_scan(detectors, liveplot_det_kwargs, curr_mot, liveplot_mot_kwargs, scan_range, scan_step)
        self.analyze_resolution_scan([-1])

        # detector = self.detector_dictionary['Pilatus 100k']['device']
        # channel = self.comboBox_pilatus_channels.currentText()
        # motor = self.motor_dictionary['hhm_energy']['object']
        # scan_range = self.doubleSpinBox_range_energy.value()
        # scan_step = self.doubleSpinBox_step_energy.value()
        # uids = self._run_any_scan(detector, channel, motor, scan_range, scan_step)
        # self.analyze_resolution_scan(uids)



    def analyze_resolution_scan(self, uids):
        uid = uids[0]
        Ecen, fwhm, I_cor, I_fit, I_fit_raw, E = analyze_elastic_scan(self.db, uid)
        print(f'Peak width: {fwhm}\n Estimated resolution: {np.sqrt(fwhm**2 - (1.3e-4 * Ecen)**2)}')
        data_dict = {}
        for k in self.align_motor_dict.keys():
            proper_key = self.align_motor_dict[k]
            motor = self.motor_dictionary[proper_key]['object']
            # data_dict[k] = motor.user_readback.get()
            data_dict[k] = motor.position

        data_dict['fwhm'] = fwhm
        data_dict['ecen'] = Ecen
        data_dict['uid'] = uid

        self._alignment_data = self._alignment_data.append(data_dict, ignore_index=True)

        self.parent.update_scan_figure_for_energy_scan(E, I_fit_raw)
        key = self.comboBox_johann_tweak_motor.currentText()
        self.parent.update_proc_figure(key)

    def update_soft_energy_limits(self, *, dE_lo=50, dE_hi=50):
        current_value = float(self.edit_reg_E.text())
        e_lo = current_value - dE_lo
        e_hi = current_value + dE_hi
        self.edit_reg_E_lo.setText(str(e_lo))
        self.edit_reg_E_hi.setText(str(e_hi))
        self.settings.setValue('johann_registration_energy', str(current_value))


    def update_settings_reg_E_lo(self):
        e_lo = self.edit_reg_E_lo.text()
        self.settings.setValue('johann_registration_energy_lo', str(e_lo))

    def update_settings_reg_E_hi(self):
        e_hi = self.edit_reg_E_hi.text()
        self.settings.setValue('johann_registration_energy_hi', str(e_hi))


    def update_settings_current_spectrometer_file(self):
        value = self.lineEdit_current_spectrometer_file.text()
        self.settings.setValue('johann_registration_file_str', value)

    def _initialize_emission_motor(self, registration_energy, energy_limits=None):
        self.johann_emission.register_energy(registration_energy, energy_limits=energy_limits)
        self.parent.parent.widget_info_beamline.push_set_emission_energy.setEnabled(1)

    def initialize_emission_motor(self):
        registration_energy = float(self.edit_reg_E.text())
        R = self._R
        kind = self._kind
        hkl = self._hkl

        energy_limits_lo = float(self.edit_reg_E_lo.text())
        energy_limits_hi = float(self.edit_reg_E_hi.text())
        energy_limits = (energy_limits_lo, energy_limits_hi)

        self._initialize_emission_motor(registration_energy, R, kind, hkl, energy_limits=energy_limits)
        print('Successfully initialized the emission motor')

    def save_emission_motor(self):
        user_folder_path = (self.motor_dictionary['motor_emission']['object'].spectrometer_root_path +
                                 f"/{self.RE.md['year']}/{self.RE.md['cycle']}/{self.RE.md['proposal']}")
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save spectrometer motor config...', user_folder_path, '*.jcfg',
                                                         options=QtWidgets.QFileDialog.DontConfirmOverwrite)[0]
        if not filename.endswith('.jcfg'):
            filename = filename + '.jcfg'
        print(filename)

        spectrometer_dict = {}

        spectrometer_dict['registration_energy'] = self.johann_emission.energy0
        spectrometer_dict['R'] = self.johann_emission.crystal.R
        spectrometer_dict['kind'] = self.johann_emission.crystal.kind
        spectrometer_dict['hkl'] = self.johann_emission.crystal.hkl
        spectrometer_dict['cr_x0'] = self.johann_emission.cr_x0
        spectrometer_dict['cr_y0'] = self.johann_emission.cr_y0
        spectrometer_dict['det_y0'] = self.johann_emission.det_y0
        spectrometer_dict['energy_limits_lo'] = self.johann_emission.energy.limits[0]
        spectrometer_dict['energy_limits_hi'] = self.johann_emission.energy.limits[1]

        with open(filename, 'w') as f:
            f.write(json.dumps(spectrometer_dict))
        print('Successfully saved the spectrometer config')
        self.lineEdit_current_spectrometer_file.setText(filename)
        # self.settings.setValue('johann_registration_file_str', filename)

    def select_config_file(self):
        user_folder_path = (self.johann_emission.spectrometer_root_path +
                            f"/{self.RE.md['year']}/{self.RE.md['cycle']}/{self.RE.md['proposal']}")
        filename = QtWidgets.QFileDialog.getOpenFileName(directory=user_folder_path,
                                                         filter='*.jcfg', parent=self)[0]
        self.lineEdit_current_spectrometer_file.setText(filename)
        # self.settings.setValue('johann_registration_file_str', filename)

    def load_emission_motor(self):
        filename = self.lineEdit_current_spectrometer_file.text()
        print(filename)
        if filename:
            with open(filename, 'r') as f:
                spectrometer_dict = json.loads(f.read())
                energy_limits = (spectrometer_dict['energy_limits_lo'], spectrometer_dict['energy_limits_hi'])
                self._initialize_emission_motor(spectrometer_dict['registration_energy'],
                                                spectrometer_dict['R'],
                                                spectrometer_dict['kind'],
                                                spectrometer_dict['hkl'],
                                                cr_x0=spectrometer_dict['cr_x0'],
                                                cr_y0=spectrometer_dict['cr_y0'],
                                                det_y0=spectrometer_dict['det_y0'],
                                                energy_limits=energy_limits)

            print('Successfully loaded the spectrometer config')

    def update_settings_calib_E_min(self):
        value = self.edit_E_calib_min.text()
        self.settings.setValue('johann_calibration_energy_min', str(value))

    def update_settings_calib_E_max(self):
        value = self.edit_E_calib_max.text()
        self.settings.setValue('johann_calibration_energy_max', str(value))

    def update_settings_calib_E_step(self):
        value = self.edit_E_calib_step.text()
        self.settings.setValue('johann_calibration_energy_step', str(value))


    def calibrate_energy(self):
        # update the data
        self._calibration_data = pd.DataFrame(columns=['energy_nom', 'energy_act', 'resolution', 'uid'])

        e_min = float(self.edit_E_calib_min.text())
        e_max = float(self.edit_E_calib_max.text())
        e_step = float(self.edit_E_calib_step.text())
        if e_min>e_max:
            message_box('Incorrect energy range','Calibration energy min should be less than max')
            return
        if (e_max - e_min) < e_step:
            message_box('Incorrect energy range','energy step size bigger than range')
            return

        energies = np.arange(e_min, e_max + e_step, e_step)
        each_scan_range = self.doubleSpinBox_range_energy.value()
        each_scan_step = self.doubleSpinBox_step_energy.value()

        detectors = ['Pilatus 100k']
        channel = self.comboBox_pilatus_channels.currentText()
        liveplot_det_kwargs = {'channel': channel, 'channel_den': '1', 'result_name': channel}

        curr_mot = 'A Monochromator Energy'
        for motor_key, motor_dict in self.motor_dictionary.items():
            if curr_mot == motor_dict['description']:
                liveplot_mot_kwargs = {'curr_mot_name': motor_dict['object'].name}
                break

        for energy in energies:
            self.plan_processor.add_plan_and_run_if_idle('move_motor_plan',
                                                         {'motor_attr': self.hhm.energy.name,
                                                          'based_on': 'object_name',
                                                          'position': energy})
            self.plan_processor.add_plan_and_run_if_idle('move_motor_plan',
                                                         {'motor_attr': self.johann_emission.energy.name,
                                                          'based_on': 'object_name',
                                                          'position': energy})
            self._run_any_scan(detectors, liveplot_det_kwargs, curr_mot, liveplot_mot_kwargs, each_scan_range, each_scan_step)

        uids = np.arange(-energies.size, 0)

        energy_converter, energies_act, resolutions, I_fit_raws = analyze_many_elastic_scans(self.db, uids, energies, short_output=False)
        # self.johann_emission.append_energy_converter(energy_converter)
        self.johann_emission.set_spectrometer_calibration(energies, energies_act)

        for each_energy_nom, each_energy_act, each_resolution, each_uid in zip(energies, energies_act, resolutions, uids):
            data_dict = {'energy_nom' : each_energy_nom,
                         'energy_act' : each_energy_act,
                         'resolution' : each_resolution,
                         'uid' : each_uid}
            self._calibration_data = self._calibration_data.append(data_dict, ignore_index=True)
        self.parent.update_proc_figure('calibration')



    def save_energy_calibration(self):
        user_folder_path = (self.motor_dictionary['motor_emission']['object'].spectrometer_root_path +
                            f"/{self.RE.md['year']}/{self.RE.md['cycle']}/{self.RE.md['proposal']}")
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save spectrometer motor config...', user_folder_path, '*.jcalib',
                                                         options=QtWidgets.QFileDialog.DontConfirmOverwrite)[0]
        if not filename.endswith('.jcalib'):
            filename = filename + '.jcalib'
        print(filename)

        self._calibration_data.to_json(filename)
        print('Successfully saved the spectrometer calibration')

    def select_energy_calibration_file(self):
        user_folder_path = (self.johann_emission.spectrometer_root_path +
                            f"/{self.RE.md['year']}/{self.RE.md['cycle']}/{self.RE.md['proposal']}")
        filename = QtWidgets.QFileDialog.getOpenFileName(directory=user_folder_path,
                                                         filter='*.jcalib', parent=self)[0]
        self.lineEdit_current_calibration_file.setText(filename)

    def update_settings_current_calibration_file(self):
        value = self.lineEdit_current_calibration_file.text()
        self.settings.setValue('johann_calibration_file_str', value)

    def load_energy_calibration(self):
        filename = self.lineEdit_current_calibration_file.text()
        self._calibration_data = pd.read_json(filename)
        energies_nom = self._calibration_data['energy_nom'].values
        energies_act = self._calibration_data['energy_act'].values
        energy_converter = Nominal2ActualConverter(energies_nom, energies_act)
        self.johann_emission.append_energy_converter(energy_converter)
        print('Successfully loaded the spectrometer calibration')











