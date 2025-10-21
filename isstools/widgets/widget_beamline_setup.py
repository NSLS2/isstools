import math
import time as ttime
from datetime import datetime

import bluesky.plan_stubs as bps
import numpy as np
import pkg_resources
from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtCore import QThread, QSettings
from bluesky.callbacks import LivePlot
from isstools.dialogs import (UpdateHHMFeedbackSettings, MoveMotorDialog)
from isstools.dialogs.BasicDialogs import question_message_box, error_message_box, message_box
from matplotlib.widgets import Cursor
from isstools.elements.liveplots import NormPlot
import json
# from isstools.widgets import widget_energy_selector
from isstools.widgets import widget_energy_selector_with_periodic_table
from isstools.elements.figure_update import update_figure, setup_figure
# from xas.energy_calibration import validate_calibration, process_calibration
import xraydb
from xas.energy_calibration import find_correct_foil

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_beamline_setup.ui')


class UIBeamlineSetup(*uic.loadUiType(ui_path)):
    def __init__(self,
                    plan_processor,
                    hhm,
                    hhm_encoder,
                    hhm_feedback,
                    apb,
                    apb_trigger_xs,
                    apb_trigger_pil100k,
                    db,
                    detector_dictionary,
                    ic_amplifiers,
                    plan_funcs,
                    service_plan_funcs,
                    aux_plan_funcs,
                    motor_dictionary,
                    tune_elements,
                    shutter_dictionary,
                    parent_gui,
                    *args,

    ** kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.plan_processor = plan_processor
        self.plan_processor.status_update_signal.connect(self.handle_gui_elements)
        self.current_pitch_position = hhm.pitch.position
        self.hhm = hhm
        self.hhm_encoder = hhm_encoder
        self.hhm_feedback = hhm_feedback
        self.apb = apb
        self.apb_trigger_xs = apb_trigger_xs
        self.apb_trigger_pil100k = apb_trigger_pil100k
        self.db = db
        self.detector_dictionary = detector_dictionary
        self.ic_amplifiers = ic_amplifiers
        self.plan_funcs = plan_funcs
        self.service_plan_funcs = service_plan_funcs
        self.aux_plan_funcs = aux_plan_funcs
        self.motor_dictionary = motor_dictionary
        self.shutter_dictionary = shutter_dictionary
        self.parent_gui = parent_gui

        self.settings = QSettings(self.parent_gui.window_title, 'XLive')

        self.tune_elements = tune_elements

        self.motor_list = [self.motor_dictionary[motor]['description'] for motor in self.motor_dictionary]
        self.motor_sorted_list = list(self.motor_list)
        self.motor_sorted_list.sort()

        self.user_motor_list = [self.motor_dictionary[motor]['description'] for motor in self.motor_dictionary
                         if ('user' in  self.motor_dictionary[motor].keys()) and self.motor_dictionary[motor]['user']]

        self.user_motor_sorted_list = list(self.user_motor_list)
        self.user_motor_sorted_list.sort()

        self.push_prepare_beamline.clicked.connect(self.prepare_beamline)

        self.push_bender_scan.clicked.connect(self.bender_scan)

        self.push_gen_scan.clicked.connect(self.run_gen_scan)
        self.push_tune_beamline.clicked.connect(self.tune_beamline)

        self.last_text = '0'
        self.tune_dialog = None
        self.last_gen_scan_uid = ''
        self.detector_dictionary = detector_dictionary
        self.det_list = list(detector_dictionary.keys())

        self.comboBox_detectors.addItems(self.det_list)
        self.comboBox_detectors_den.addItem('1')
        self.comboBox_detectors_den.addItems(self.det_list)

        self.comboBox_detectors.currentIndexChanged.connect(self.detector_selected)
        self.comboBox_detectors_den.currentIndexChanged.connect(self.detector_selected_den)
        self.detector_selected()
        self.detector_selected_den()

        self.pushEnableHHMFeedback.setChecked(self.hhm_feedback.status)
        self.pushEnableHHMFeedback.toggled.connect(self.enable_fb)
        self.hhm.fb_status.subscribe(self.update_pushEnableHHMFeedback_status)

        self.push_update_feedback_settings.clicked.connect(self.update_hhm_feedback_settings)
        self.push_update_feedback_center.clicked.connect(self.update_piezo_center)
        self.push_calibration_scan.clicked.connect(self.energy_calibration)

        if 'Endstation BPM' in self.detector_dictionary:
            self.bpm_es = self.detector_dictionary['Endstation BPM']['device']
        self.setup_figure_in_the_gui()

        self.checkBox_user_motors.toggled.connect(self.add_motors)
        self.add_motors()

        daq_rate = self.apb.acq_rate.get()
        self.spinBox_daq_rate.setValue(daq_rate)
        self.spinBox_daq_rate.valueChanged.connect(self.update_daq_rate)

        self.spinBox_enc_rate.setValue(hhm_encoder.enc_rate)
        self.spinBox_enc_rate.valueChanged.connect(self.update_enc_rate)

        trigger_pil100k_freq = self.apb_trigger_pil100k.freq.get()
        self.spinBox_trigger_pil100k_freq.setValue(trigger_pil100k_freq)
        self.spinBox_trigger_pil100k_freq.valueChanged.connect(self.update_trigger_pil100k_freq)

        trigger_xs_freq = self.apb_trigger_xs.freq.get()
        self.spinBox_trigger_xs_freq.setValue(trigger_xs_freq)
        self.spinBox_trigger_xs_freq.valueChanged.connect(self.update_trigger_xs_freq)

        # self.widget_energy_selector_prepare = widget_energy_selector.UIEnergySelector()
        self.widget_energy_selector_prepare = widget_energy_selector_with_periodic_table.UIEnergySelectorWithPeriodicTable(emission=False)
        self.layout_energy_selector_prepare.addWidget(self.widget_energy_selector_prepare)
        # self.widget_energy_selector_calibration = widget_energy_selector.UIEnergySelector()
        self.widget_energy_selector_calibration = widget_energy_selector_with_periodic_table.UIEnergySelectorWithPeriodicTable(emission=False)
        self.layout_energy_selector_calibration.addWidget(self.widget_energy_selector_calibration)

        self.liveplot_kwargs = {}

    def setup_figure_in_the_gui(self):
        self.figure_gen_scan, self.canvas_gen_scan, self.toolbar_gen_scan = setup_figure(self, self.plot_gen_scan)
        self.cursor_gen_scan = Cursor(self.figure_gen_scan.ax, useblit=True, color='green', linewidth=0.75)
        self.cid_gen_scan = self.canvas_gen_scan.mpl_connect('button_press_event', self.getX_gen_scan)


    def handle_gui_elements(self):
        if self.plan_processor.status == 'idle':
            self.figure_gen_scan.tight_layout()
            self.canvas_gen_scan.draw_idle()
            self.cid_gen_scan = self.canvas_gen_scan.mpl_connect('button_press_event', self.getX_gen_scan)
            self.liveplot_kwargs = {}
        elif self.plan_processor.status == 'running':
            self.canvas_gen_scan.mpl_disconnect(self.cid_gen_scan)

    def add_motors(self):
        self.comboBox_motors.clear()
        if self.checkBox_user_motors.isChecked():
            self.comboBox_motors.addItems(self.user_motor_sorted_list)
        else:
            self.comboBox_motors.addItems(self.motor_sorted_list)

    def detector_selected(self):
        self.comboBox_channels.clear()
        detector = self.comboBox_detectors.currentText()
        self.comboBox_channels.addItems(self.detector_dictionary[detector]['channels'])
        detector_device = self.detector_dictionary[detector]['device']
        self.edit_gen_exp_time.setText(str(detector_device.read_exposure_time()))

    def detector_selected_den(self):
        self.comboBox_channels_den.clear()
        detector = self.comboBox_detectors_den.currentText()
        if detector == '1':
            self.comboBox_channels_den.addItem('1')
        else:
            self.comboBox_channels_den.addItems(self.detector_dictionary[detector]['channels'])


    def make_liveplot_func(self, plan_name, plan_kwargs):
        self.start_gen_scan_figure()
        liveplot_list = []
        try:
            liveplot_kwargs = plan_kwargs['liveplot_kwargs']
            _norm_plot = NormPlot(liveplot_kwargs['channel'],
                                  liveplot_kwargs['channel_den'],
                                  liveplot_kwargs['result_name'],
                                  liveplot_kwargs['curr_mot_name'], ax=self.figure_gen_scan.ax)
            liveplot_list.append(_norm_plot)
            # when the liveplot is created, we also update the canvas motor:
            self._set_canvas_motor_from_name(liveplot_kwargs['curr_mot_name'])
        except:
            print(f'could not make liveplot for scan {plan_name}')
        return liveplot_list

    def _set_canvas_motor_from_name(self, motor_name):
        for motor_key, motor_dict in self.motor_dictionary.items():
            if motor_name == motor_dict['object'].name:
                self.canvas_gen_scan.motor = motor_dict['object']


    @property
    def shutters_open(self):
        for shutter in [self.shutter_dictionary[shutter] for shutter in self.shutter_dictionary if
                        self.shutter_dictionary[shutter].shutter_type != 'SP']:
            if shutter.state.get():
                ret = question_message_box(self,'Photon shutter closed', 'Proceed with the shutter closed?')
                if not ret:
                    print('Aborted!')
                    return False
                break
        return True

    def _get_detectors_for_gen_scan(self):
        curr_det = ''

        detectors = []
        detector = self.comboBox_detectors.currentText()
        detectors.append(detector)
        channels = self.detector_dictionary[detector]['channels']
        channel = channels[self.comboBox_channels.currentIndex()]
        result_name = channel

        detector_den = self.comboBox_detectors_den.currentText()
        if detector_den != '1':
            channels_den = self.detector_dictionary[detector]['channels']
            channel_den = channels_den[self.comboBox_channels_den.currentIndex()]
            detectors.append(detector_den)
            result_name += '/{}'.format(channel_den)
        else:
            channel_den = '1'

        liveplot_det_kwargs = {'channel' : channel, 'channel_den' : channel_den, 'result_name' : result_name}
        return detectors, liveplot_det_kwargs

    def _get_motor_for_gen_scan(self):
        curr_mot = self.comboBox_motors.currentText()
        for motor_key, motor_dict in self.motor_dictionary.items():
            if curr_mot == motor_dict['description']:
                liveplot_mot_kwargs = {'curr_mot_name' : motor_dict['object'].name}
                break
        return curr_mot, liveplot_mot_kwargs


    def run_gen_scan(self):
        if not self.shutters_open: return

        detectors, liveplot_det_kwargs = self._get_detectors_for_gen_scan()
        motor, liveplot_mot_kwargs = self._get_motor_for_gen_scan()

        rel_start = -float(self.edit_gen_range.text()) / 2
        rel_stop = float(self.edit_gen_range.text()) / 2
        num_steps = int(round(float(self.edit_gen_range.text()) / float(self.edit_gen_step.text()))) + 1
        try:
            exposure_time = float(self.edit_gen_exp_time.text())
        except ValueError:
            exposure_time = 1

        update_figure([self.figure_gen_scan.ax], self.toolbar_gen_scan, self.canvas_gen_scan)

        plan_name = 'general_scan'
        plan_kwargs = {'detectors' : detectors,
                       'motor' : motor,
                       'rel_start' : rel_start,
                       'rel_stop' : rel_stop,
                       'num_steps' : num_steps,
                       'exposure_time': exposure_time,
                       'liveplot_kwargs' : {**liveplot_det_kwargs, **liveplot_mot_kwargs}}

        self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)

    def getX_gen_scan(self, event):

        if event.button == 3:
            if self.canvas_gen_scan.motor != '':
                dlg = MoveMotorDialog.MoveMotorDialog(new_position=event.xdata, motor=self.canvas_gen_scan.motor,
                                                      parent=self.canvas_gen_scan)
                if dlg.exec_():
                    pass

    def read_energy_label(self):
        label_text = self.widget_energy_selector_prepare.edit_E0.text()

        try:
            energy = float(label_text)
        except:
            error_message_box('Energy setting is invalid')
            energy = None
        return energy

    def prepare_beamline(self, energy_setting=None):
        if energy_setting:
            self.lineEdit_energy.setText(str(energy_setting))
        energy = self.read_energy_label()
        if energy:
            move_cm_mirror = self.checkBox_move_cm_miirror.isChecked()

            plan_name = 'prepare_beamline_plan'
            plan_kwargs = {'energy' : energy, 'move_cm_mirror' : move_cm_mirror}
            self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)

    def tune_beamline(self):
        if self.checkBox_quick_tune_scanning.isChecked():
            plan_name = 'quick_tune_beamline_plan_bundle'
            plan_gui_services = ['beamline_setup_plot_quick_tune_data']
            plan_kwargs = {'enable_fb_in_the_end' : self.checkBox_autoEnableFeedback.isChecked(),
                           'plan_gui_services' : plan_gui_services}
        else:
            plan_name = 'tune_beamline_plan_bundle'
            plan_kwargs = {'extended_tuning' : False,
                           'enable_fb_in_the_end' : self.checkBox_autoEnableFeedback.isChecked(),
                           'do_liveplot' : True}
        self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)

    def update_hhm_feedback_settings(self):
        pars = self.hhm_feedback.current_fb_parameters()
        pars_str = [str(i) for i in pars]
        dlg = UpdateHHMFeedbackSettings.UpdatePiezoDialog(*pars_str, parent=self)
        if dlg.exec_():
            new_pars = dlg.getValues()
            self.hhm_feedback.set_fb_parameters(*new_pars)
            self.current_pitch_position = self.hhm.pitch.position


    def update_piezo_center(self):
        self.hhm_feedback.update_center()

    def enable_fb(self, value):
        value = value > 0
        self.hhm.fb_status.put(int(value))
        self.pushEnableHHMFeedback.setChecked(value)

    def update_pushEnableHHMFeedback_status(self, value, **kwargs):
        self.pushEnableHHMFeedback.setChecked(value)
        # self.pushEnableHHMFeedback.toggled.connect(self.enable_fb)



    def bender_scan(self):
        energy = float(self.widget_energy_selector_calibration.edit_E0.text())
        element, edge, energy = find_correct_foil(energy=energy)
        if element:
            if element != self.widget_energy_selector_calibration.comboBox_element.currentText():
                ret = question_message_box(self, 'Warning',
                                           f"Element is not available as a calibration foil. {element} "
                                           f"foil, {edge} edge will be used. Proceed?")
                if not ret:
                    return

            ret = question_message_box(self, 'Warning',
                                       'For best results make sure that there is no sample in the beam')
            if ret:
                plan_name = 'bender_scan_plan_bundle'
                plan_kwargs = {'element' : element, 'edge' : edge}
                plan_gui_services = ['error_message_box']
                self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs, plan_gui_services)

    def energy_calibration(self):
        energy = float(self.widget_energy_selector_calibration.edit_E0.text())
        element, edge, energy = find_correct_foil(energy=energy)
        if element:
            if element != self.widget_energy_selector_calibration.comboBox_element.currentText():
                ret = question_message_box(self, 'Warning', f"Element is not available as a calibration foil. {element} "
                                                             f"foil, {edge} edge will be used. Proceed?")
                if not ret:
                    return
            ret = question_message_box(self, 'Warning', 'For best results make sure that there is no sample in the beam')
            if ret:
                propagate_calibration = question_message_box(self, 'Warning', f'Would you like to apply new calibration to all scans performed within {energy - 200}-{energy + 500} eV energy range?')
                plan_name = 'calibrate_mono_energy_plan_bundle'
                plan_gui_services = ['beamline_setup_plot_energy_calibration_data', 'error_message_box']
                plan_kwargs = {'element': element, 'edge': edge, 'propagate_calibration': propagate_calibration, 'plan_gui_services' : plan_gui_services}
                self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs, ['question_message_box'])
        else:
            error_message_box('Calibration standard could not be found within -200 - +600 eV from the edge position' )

    def update_daq_rate(self):
        daq_rate = self.spinBox_daq_rate.value()
        # 374.94 is the nominal RF frequency
        divider = int(374.94/daq_rate)
        self.RE(bps.abs_set(self.apb.divide, divider, wait=True))

    def update_enc_rate(self):
        enc_rate = self.spinBox_enc_rate.value()
        rate_in_points = (1/(enc_rate*1e3))*1e9/10

        rate_in_points_rounded = int(np.ceil(rate_in_points / 100.0) * 100)
        self.RE(bps.abs_set(self.hhm_encoder.filter_dt, rate_in_points_rounded, wait=True))

    def update_trigger_pil100k_freq(self):
        trigger_pil100k_freq = self.spinBox_trigger_pil100k_freq.value()
        self.apb_trigger_pil100k.freq.put(trigger_pil100k_freq)

    def update_trigger_xs_freq(self):
        trigger_xs_freq = self.spinBox_trigger_xs_freq.value()
        self.apb_trigger_xs.freq.put(trigger_xs_freq)

    def start_gen_scan_figure(self):
        for i in reversed(range(self.plot_gen_scan.count())):
            self.plot_gen_scan.itemAt(i).widget().deleteLater()
            self.plot_gen_scan.removeWidget(self.plot_gen_scan.itemAt(i).widget())
        self.setup_figure_in_the_gui()

    def stop_gen_scan_figure(self):
        self.figure_gen_scan.tight_layout()
        self.canvas_gen_scan.draw_idle()

    def _update_figure_with_calibration_data(self, en_ref, mu_ref, mu):
        self.figure_gen_scan.ax.plot(en_ref, mu_ref, label='Reference')
        self.figure_gen_scan.ax.plot(en_ref, mu, label='New spectrum')
        self.figure_gen_scan.ax.set_xlabel('Energy')
        self.figure_gen_scan.ax.set_ylabel('mu')
        self.figure_gen_scan.ax.set_xlim(en_ref[0], en_ref[-1])
        self.figure_gen_scan.legend(loc='upper left')
        self.stop_gen_scan_figure()
        self.canvas_gen_scan.motor = None

    def _update_figure_with_tuning_data(self, positions, values, optimum_position, positions_axis_label='', values_axis_label=''):
        try:
            print('plotting - ', end='')
            self.figure_gen_scan.ax.plot(positions, values)
            self.figure_gen_scan.ax.vlines([optimum_position], values.min(), values.max(), colors='k')
            self.figure_gen_scan.ax.set_xlabel(positions_axis_label)
            self.figure_gen_scan.ax.set_ylabel(values_axis_label)
            self.figure_gen_scan.ax.set_xlim(positions.min(), positions.max())
            self.figure_gen_scan.ax.set_ylim(values.min(), values.max())
            self.stop_gen_scan_figure()
            self.canvas_gen_scan.motor = None
            print('done plotting', end='\n')
        except Exception as e:
            print(e)