import pkg_resources
from qtpy import uic, QtWidgets
from qtpy.QtCore import QThread, QSettings
from qtpy.QtCore import QObject
from bluesky.callbacks import LivePlot
from bluesky.callbacks.mpl_plotting import LiveScatter
import bluesky.plan_stubs as bps
import bluesky.plans as bp
import numpy as np
import pandas as pd
from qtpy import uic, QtGui, QtCore, QtWidgets
from datetime import datetime
import time as ttime
from qtpy.QtWidgets import QLabel, QPushButton, QLineEdit, QSizePolicy, QSpacerItem, QSlider, QToolTip, QCheckBox
import xraydb
import copy
from isstools.dialogs import MoveMotorDialog
from isstools.dialogs.BasicDialogs import question_message_box
from isstools.elements.figure_update import update_figure_with_colorbar, update_figure, setup_figure
from isstools.elements.transformations import range_step_2_start_stop_nsteps
from isstools.widgets import widget_johann_tools
from xas.spectrometer import analyze_elastic_scan
from .widget_spectrometer_motors import UISpectrometerMotors
from isstools.elements.widget_motors import UIWidgetMotors
from isstools.elements.widget_spectrometer_R import UIWidgetSpectrometerR
from .widget_pilatus import UIPilatusMonitor
from ..elements.liveplots import XASPlot, NormPlot  # , XASPlotX
from ..elements.elements import get_spectrometer_line_dict
# from isstools.elements.liveplots import NormPlot
from isstools.widgets import widget_emission_energy_selector

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_spectrometer.ui')


class UISpectrometer(*uic.loadUiType(ui_path)):
    spectrometer_config_list_changed_signal = QtCore.Signal()
    spectrometer_config_changed_signal = QtCore.Signal()

    def __init__(self,
                 RE,
                 plan_processor,
                 hhm,
                 db,
                 johann_emission,
                 johann_spectrometer_manager,
                 detector_dictionary,
                 motor_dictionary,
                 shutter_dictionary,
                 aux_plan_funcs,
                 # ic_amplifiers,
                 service_plan_funcs,
                 # tune_elements,
                 # shutter_dictionary,
                 parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.plan_processor = plan_processor
        self.plan_processor.status_update_signal.connect(self.handle_gui_elements)
        self.hhm = hhm
        self.detector_dictionary = detector_dictionary
        self.motor_dictionary = motor_dictionary
        self.last_motor_used = None

        self.figure_scan, self.canvas_scan, self.toolbar_scan = setup_figure(self, self.layout_plot_scan)
        self.figure_proc, self.canvas_proc, self.toolbar_proc = setup_figure(self, self.layout_plot_processed)

        self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)
        self.cid_proc = self.canvas_proc.mpl_connect('button_press_event', self.getX_proc)

        # PCL
        self.det_list = list(detector_dictionary.keys())
        self.comboBox_pcl_detectors.addItems(self.det_list)
        self.comboBox_pcl_detectors.setCurrentIndex(3)  # make it PIPS by default!
        self.comboBox_pcl_detectors.currentIndexChanged.connect(self.pcl_detector_selected)
        self.pcl_detector_selected()
        self.comboBox_pcl_detectors.addItems(self.det_list)
        self.push_pcl_1D_scan.clicked.connect(self.run_pcl_scan)

        # Legacy Johann
        # self.widget_johann_tools = widget_johann_tools.UIJohannTools(parent=self,
        #                                                              motor_dictionary=motor_dictionary,
        #                                                              db=db,
        #                                                              RE=RE,
        #                                                              plan_processor=plan_processor,
        #                                                              hhm=hhm,
        #                                                              johann_emission=johann_emission,
        #                                                              detector_dictionary=detector_dictionary,
        #                                                              aux_plan_funcs=aux_plan_funcs,
        #                                                              service_plan_funcs=service_plan_funcs,
        #                                                              embedded_run_scan_func=self._run_any_scan,
        #                                                              figure_proc=self.figure_proc,
        #                                                              canvas_proc=self.canvas_proc,
        #                                                              toolbar_proc=self.toolbar_proc)
        # self.layout_johann_tools.addWidget(self.widget_johann_tools)
        ###

        # --- Johann spectrometer ---
        # Johann general
        self.johann_emission = johann_emission
        self.johann_emission.append_gui_update_signal(self.spectrometer_config_changed_signal)
        self.update_johann_spectrometer_gui_elements()
        self.spectrometer_config_changed_signal.connect(self.update_johann_spectrometer_gui_elements)

        self.johann_spectrometer_manager = johann_spectrometer_manager
        self.johann_spectrometer_manager.append_list_update_signal(self.spectrometer_config_list_changed_signal)
        self.update_johann_config_tree()
        self.spectrometer_config_list_changed_signal.connect(self.update_johann_config_tree)
        self.spectrometer_config_list_changed_signal.connect(
            self.parent.widget_scan_manager.update_comboBox_spectrometer_config)

        # Johann parking
        self._prepare_johann_elements()

        self.push_johann_home_crystals.clicked.connect(self.johann_home_crystals)
        self.push_johann_reset_config.clicked.connect(self.johann_reset_config)
        self.push_move_crystals_to_90_deg.clicked.connect(self.move_crystals_to_90_deg)

        self.push_johann_parking_element_update.clicked.connect(self.johann_parking_element_update)
        self.comboBox_johann_element_parking.currentIndexChanged.connect(self.johann_populate_parking_element_widgets)
        self.johann_populate_R_parking_related_widgets()
        self.spinBox_johann_crystal_R_parking.valueChanged.connect(self.johann_update_parking_R)

        # Johann analyzer setup
        self.update_enabled_crystals_checkboxes()
        self.update_comboBox_johann_alignment_crystal()
        self.update_crystal_kind_fields()

        checkBox_enable_list = [self.checkBox_enable_main,
                                self.checkBox_enable_aux2,
                                self.checkBox_enable_aux3,
                                self.checkBox_enable_aux4,
                                self.checkBox_enable_aux5]
        for checkBox_enable in checkBox_enable_list:
            checkBox_enable.toggled.connect(self.enable_crystal)
            checkBox_enable.toggled.connect(self.update_comboBox_johann_alignment_crystal)

        self.widget_johann_line_selector = widget_emission_energy_selector.UIEmissionLineSelectorEnergyOnly(parent=self,
                                                                                                            emin=4500)
        self.layout_johann_emission_line_selector.addWidget(self.widget_johann_line_selector)
        self.comboBox_johann_roll_offset.addItems([str(i) for i in self.johann_emission.allowed_roll_offsets])
        self.push_johann_compute_geometry.clicked.connect(self.johann_compute_geometry)
        self.push_johann_move_motors.clicked.connect(self.johann_move_motors)

        # Johann general scans
        self.johann_motor_list = [motor_dictionary[motor]['description'] for motor in motor_dictionary
                                  if ('group' in self.motor_dictionary[motor].keys()) and
                                  (self.motor_dictionary[motor]['group'] == 'spectrometer') and
                                  ('spectrometer_kind' in self.motor_dictionary[motor].keys()) and
                                  (self.motor_dictionary[motor]['spectrometer_kind'] == 'johann')]

        self.comboBox_johann_scan_motor.addItems(self.johann_motor_list)
        self.push_johann_motor_scan.clicked.connect(self.run_johann_motor_scan)

        # Johann alignment
        self.comboBox_johann_alignment_fom.addItems(['max', 'fwhm'])

        self._johann_alignment_parameter_widget_dict = {}
        self.johann_alignment_tune_widget_list = []
        self.johann_alignment_scan_widget_list = []
        self.comboBox_johann_alignment_strategy.addItems(['Emission', 'Elastic', 'HERFD'])

        if johann_emission.initialized:
            self.doubleSpinBox_johann_alignment_R_energy.setValue(johann_emission.energy.position)
        self._get_default_johann_alignment_parameters()
        self.handle_johann_alignment_widgets(gui_initialized=False)
        self.radioButton_alignment_mode_manual.clicked.connect(self.handle_johann_alignment_widgets)
        self.radioButton_alignment_mode_semi.clicked.connect(self.handle_johann_alignment_widgets)
        self.radioButton_alignment_mode_automatic.clicked.connect(self.handle_johann_alignment_widgets)
        self.radioButton_alignment_mode_fly.clicked.connect(self.handle_johann_alignment_widgets)
        self.radioButton_alignment_mode_step.clicked.connect(self.handle_johann_alignment_widgets)

        self.comboBox_johann_alignment_crystal.currentIndexChanged.connect(self.handle_johann_alignment_widgets)
        self.comboBox_johann_tweak_motor.currentIndexChanged.connect(self.handle_johann_alignment_widgets)
        self.comboBox_johann_alignment_strategy.currentIndexChanged.connect(self.handle_johann_alignment_widgets)

        self.push_johann_alignement_scan.clicked.connect(self.run_johann_alignment_scan)
        self.push_johann_reset_alignement_data.clicked.connect(self.johann_reset_alignment_data)

        # Johann calibration/registration
        self.comboBox_johann_calibration_fom.addItems(['com_loc', 'max_loc'])
        self._johann_calibration_parameter_widget_dict = {}
        self.johann_calibration_scan_widget_list = []
        self.comboBox_johann_calibration_strategy.addItems(['Roll', 'HERFD'])
        self.handle_johann_calibration_widgets()
        self.comboBox_johann_calibration_strategy.currentIndexChanged.connect(self.handle_johann_calibration_widgets)
        self.radioButton_alignment_mode_fly.clicked.connect(self.handle_johann_calibration_widgets)
        self.radioButton_alignment_mode_step.clicked.connect(self.handle_johann_calibration_widgets)
        self.push_johann_calibration_scan.clicked.connect(self.run_johann_calibration_scan)

        self._johann_resolution_parameter_widget_dict = {}
        self.johann_resolution_scan_widget_list = []
        self.handle_johann_resolution_widgets()
        self._johann_resolution_strategy = 'elastic'
        self.checkBox_johann_bender_scan.toggled.connect(self._handle_enabled_johann_resolution_widgets)
        self.radioButton_alignment_mode_fly.clicked.connect(self.handle_johann_resolution_widgets)
        self.radioButton_alignment_mode_step.clicked.connect(self.handle_johann_resolution_widgets)
        self.push_johann_resolution_scan.clicked.connect(self.run_johann_resolution_scan)

        self.push_johann_register_energy.clicked.connect(self.johann_register_energy)
        self.push_johann_set_limits.clicked.connect(self.johann_set_energy_limits)
        self.push_johann_reset_limits.clicked.connect(self.johann_reset_energy_limits)

        # Johann config manager
        self.push_johann_create_config.clicked.connect(self.johann_create_config)
        self.push_johann_set_current_config.clicked.connect(self.johann_set_current_config)

        # Johann additional buttons
        self.push_johann_open_motors_widget.clicked.connect(self.open_motor_widget)
        self.push_johann_put_detector_to_safe_position.clicked.connect(self.johann_put_detector_to_safe_position)

        self._y_offset = 0.5

    # general handling of gui elements, plotting, and scanning
    def handle_gui_elements(self):
        if self.plan_processor.status == 'idle':
            self.figure_scan.tight_layout()
            self.canvas_scan.draw_idle()
            self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)
            self.liveplot_kwargs = {}
        elif self.plan_processor.status == 'running':
            self.canvas_scan.mpl_disconnect(self.cid_scan)

    def make_liveplot_func(self, plan_name, plan_kwargs):
        print(plan_kwargs['liveplot_kwargs'])
        try:
            if plan_kwargs['liveplot_kwargs']['figure'] == 'proc_figure':
                self.start_gen_proc_figure()
        except:
            self.start_gen_scan_figure()

        liveplot_list = []
        try:
            liveplot_kwargs = plan_kwargs['liveplot_kwargs']
            _norm_plot = NormPlot(liveplot_kwargs['channel'],
                                  liveplot_kwargs['channel_den'],
                                  liveplot_kwargs['result_name'],
                                  liveplot_kwargs['curr_mot_name'], ax=self.figure_scan.ax)
            liveplot_list.append(_norm_plot)
            # when the liveplot is created, we also update the canvas motor:
            self._set_canvas_motor_from_name(liveplot_kwargs['curr_mot_name'])
        except:
            print(f'could not make liveplot for scan {plan_name}')
        return liveplot_list

    def _set_canvas_motor_from_name(self, motor_name):
        for motor_key, motor_dict in self.motor_dictionary.items():
            if motor_name == motor_dict['object'].name:
                self.canvas_scan.motor = motor_dict['object']

    def _set_canvas_proc_motor_from_description(self, motor_description):
        for motor_key, motor_dict in self.motor_dictionary.items():
            if motor_description == motor_dict['description']:
                self.canvas_proc.motor = motor_dict['object']

    def start_gen_scan_figure(self):
        update_figure([self.figure_scan.ax], self.toolbar_scan, self.canvas_scan)

    def start_gen_proc_figure(self):
        update_figure([self.figure_proc.ax], self.toolbar_proc, self.canvas_proc)

    def _run_any_scan(self, detectors, liveplot_det_kwargs,
                      motor, liveplot_mot_kwargs,
                      scan_range, scan_step, exposure_time=1):

        rel_start, rel_stop, num_steps = range_step_2_start_stop_nsteps(scan_range, scan_step)

        plan_name = 'general_scan'
        plan_kwargs = {'detectors': detectors,
                       'motor': motor,
                       'rel_start': rel_start,
                       'rel_stop': rel_stop,
                       'num_steps': num_steps,
                       'exposure_time': exposure_time,
                       'liveplot_kwargs': {**liveplot_det_kwargs, **liveplot_mot_kwargs, 'tab': 'spectrometer'}}

        self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)

    def getX_proc(self, event):
        print(f'Event {event.button}')
        if event.button == 3:
            if self.canvas_proc.motor != '':
                dlg = MoveMotorDialog.MoveMotorDialog(new_position=event.xdata, motor=self.canvas_proc.motor,
                                                      parent=self.canvas_proc)
                if dlg.exec_():
                    pass

    def getX_scan(self, event):
        print(f'Event {event.button}')
        if event.button == 3:
            if self.canvas_scan.motor != '':
                dlg = MoveMotorDialog.MoveMotorDialog(new_position=event.xdata, motor=self.canvas_scan.motor,
                                                      parent=self.canvas_scan)
                if dlg.exec_():
                    pass

    def _detector_selected(self, cb_det, cb_chan):
        cb_chan.clear()
        detector_name = cb_det.currentText()
        cb_chan.addItems(self.detector_dictionary[detector_name]['channels'])

    def _update_figure_with_data(self, figure, canvas, x, y, x_fit=None, y_fit=None, x_peak=None, y_peak=None, fwhm=None,
                                 curve_index=0, label='', color=None,
                                 x_label='roll', y_label='intensity',
                                 scan_motor_description=None, plotting_one_curve=True, plotting_many_curves_end=False):

        if plotting_many_curves_end:
            pass
        else:
            print('plotting data')
            y_offset = curve_index * self._y_offset
            if color is None:
                color = f'C{curve_index}' # should depend on index

            figure.ax.plot(x, y - y_offset, '.', label=f'{label}', color=color, ms=15)
            if (x_fit is not None) and (y_fit is not None):
                figure.ax.plot(x_fit, y_fit - y_offset, '-', color=color)

            if (x_peak is not None) and (y_peak is not None):
                figure.ax.plot([x_peak, x_peak], [y.min() - y_offset, y.max() - y_offset], '-', color=color, lw=0.5)

            if (x_peak is not None) and (fwhm is not None):
                x_lo = x_peak - fwhm / 2
                x_hi = x_peak + fwhm / 2
                figure.ax.plot([x_lo, x_hi], [0.5 - y_offset, 0.5 - y_offset], '-', color=color, lw=0.5)
                figure.ax.text(x_peak, 0.55 - y_offset, f'{fwhm:0.3f}', color=color, ha='center', va='center')

        if plotting_one_curve or plotting_many_curves_end:
            print('concluding the data plot')
            figure.ax.set_xlabel(x_label)
            figure.ax.set_ylabel(y_label)
            # figure.ax.set_xlim(x.min(), x.max())

            figure.ax.legend(loc='upper left', frameon=False)
            figure.tight_layout()
            canvas.draw_idle()
            if scan_motor_description is None:
                pass # debug purposes
            elif scan_motor_description == 'Rowland Circle Radius':
                self.canvas_proc.motor = 'Rowland Circle Radius'
            else:
                for motor_key, motor_dict in self.motor_dictionary.items():
                    if motor_dict['description'] == scan_motor_description:
                        canvas.motor = motor_dict['object']

    def _update_figure_with_scan_data(self, *args, **kwargs):
        self._update_figure_with_data(self.figure_scan, self.canvas_scan, *args, **kwargs)

    def _update_figure_with_analysis_data(self, *args, **kwargs):
        self._update_figure_with_data(self.figure_proc, self.canvas_proc, *args, **kwargs)

    # PCL scans
    def pcl_detector_selected(self):
        self._detector_selected(self.comboBox_pcl_detectors, self.comboBox_pcl_channels)

    def run_pcl_scan(self):
        detector = self.comboBox_pcl_detectors.currentText()
        channel = self.comboBox_pcl_channels.currentText()
        liveplot_det_kwargs = {'channel': channel, 'channel_den': '1', 'result_name': channel}

        motor_suffix = self.comboBox_pcl_motors.currentText().split(' ')[-1]
        motor = f'six_axes_stage_{motor_suffix}'
        motor_description = self.motor_dictionary[motor]['description']
        liveplot_mot_kwargs = {'curr_mot_name': motor}

        scan_range = getattr(self, f'doubleSpinBox_pcl_range_{motor_suffix}').value()
        scan_step = getattr(self, f'doubleSpinBox_pcl_step_{motor_suffix}').value()
        exposure_time = self.doubleSpinBox_pcl_exposure_time.value()

        self._run_any_scan([detector], liveplot_det_kwargs,
                           motor_description, liveplot_mot_kwargs,
                           scan_range, scan_step, exposure_time)

    # Johann parking
    def _prepare_johann_elements(self):
        self.johann_parking_elements = {'Main': {'set_parking_func': self.johann_emission.set_main_crystal_parking,
                                                 'read_parking_func': self.johann_emission.read_main_crystal_parking},
                                        'Aux2': {'set_parking_func': self.johann_emission.set_aux2_crystal_parking,
                                                 'read_parking_func': self.johann_emission.read_aux2_crystal_parking},
                                        'Aux3': {'set_parking_func': self.johann_emission.set_aux3_crystal_parking,
                                                 'read_parking_func': self.johann_emission.read_aux3_crystal_parking},
                                        'Aux4': {'set_parking_func': self.johann_emission.set_aux4_crystal_parking,
                                                 'read_parking_func': self.johann_emission.read_aux4_crystal_parking},
                                        'Aux5': {'set_parking_func': self.johann_emission.set_aux5_crystal_parking,
                                                 'read_parking_func': self.johann_emission.read_aux5_crystal_parking},
                                        'Detector': {'set_parking_func': self.johann_emission.set_det_arm_parking,
                                                     'read_parking_func': self.johann_emission.read_det_arm_parking}}

        self.comboBox_johann_element_parking.addItems(self.johann_parking_elements.keys())
        self.johann_populate_parking_element_widgets()
        # self.johann_populate_detector_parking()

    def johann_populate_parking_element_widgets(self):
        _key = self.comboBox_johann_element_parking.currentText()
        read_parking_func = self.johann_parking_elements[_key]['read_parking_func']
        if _key == 'Detector':
            x, th1, th2 = read_parking_func()
            positions = [x, th1, th2, 0.0]
            names = ['X', 'Gon1', 'Gon2', 'NA']
            units = ['mm', 'deg', 'deg', '']
        else:
            x, y, roll, yaw = read_parking_func()
            positions = [x, y, roll, yaw]
            units = ['mm', 'mm', 'deg', 'deg']
            if _key == 'Main':
                names = ['Assy X', 'Assy Y', 'Roll', 'Yaw']
            else:
                names = ['X', 'Y', 'Roll', 'Yaw']

        self._johann_populate_parking_element_widgets(names, positions, units)

    def _johann_populate_parking_element_widgets(self, names, positions, units):
        for i, (name, position, unit) in enumerate(zip(names, positions, units)):
            widget_label_name = getattr(self, f'label_johann_parking_element_name_{i + 1}')
            widget_spinbox_position = getattr(self, f'spinBox_johann_parking_element_position_{i + 1}')
            widget_label_unit = getattr(self, f'label_johann_parking_element_unit_{i + 1}')
            widget_label_name.setText(name)
            widget_spinbox_position.setValue(position)
            widget_label_unit.setText(unit)

    # def johann_populate_detector_parking(self):
    #     x, th1, th2 = self.johann_emission.read_det_arm_parking()
    #     self.spinBox_johann_park_x_detector.setValue(x)
    #     self.spinBox_johann_park_th1_detector.setValue(th1)
    #     self.spinBox_johann_park_th2_detector.setValue(th2)

    def johann_parking_element_update(self):
        ret = question_message_box(self, 'Warning',
                                   'Parking update must be done at bragg angle set to 90 degrees!\n' \
                                   'Are you sure you want to proceed?')
        if ret:
            _key = self.comboBox_johann_element_parking.currentText()
            set_parking_func = self.johann_parking_elements[_key]['set_parking_func']
            set_parking_func()
            self.johann_populate_parking_element_widgets()

    # def johann_update_detector_parking(self):
    #     ret = question_message_box(self, 'Warning',
    #                                'Detector parking update must be done with great care!' \
    #                                'Detector parking update must be done with detector at bragg angle set to 90 degrees!\n' \
    #                                'Are you sure you want to proceed?')
    #     if ret:
    #         self.johann_emission.set_det_arm_parking()
    #         self.johann_populate_detector_parking()

    def johann_populate_R_parking_related_widgets(self):
        self.spinBox_johann_crystal_R_parking.setValue(self.johann_emission.read_R_parking())
        self.johann_deal_with_crystal_aux_z()

    def johann_update_parking_R(self, value):
        print(f'new parking R = {value}')
        self.johann_emission.update_R_parking(value)
        self.johann_deal_with_crystal_aux_z()
        self.edit_johann_crystal_R.setText(f'{value :.0f}')

    def johann_deal_with_crystal_aux_z(self):
        aux2_z, aux4_z = self.johann_emission.read_crystal_aux_dz()
        self.spinBox_johann_crystal_aux2_z.setValue(aux2_z)
        self.spinBox_johann_crystal_aux4_z.setValue(aux4_z)

    def johann_home_crystals(self):
        self.johann_emission.home_crystal_piezos()

    def johann_reset_config(self):
        self.johann_emission.reset_config()

    def move_crystals_to_90_deg(self):
        self.johann_emission.move_crystals_to_90_deg()

    # Johann analyzer setup
    def update_enabled_crystals_checkboxes(self):
        for crystal_key, enable in self.johann_emission.enabled_crystals.items():
            checkBox_widget = getattr(self, f'checkBox_enable_{crystal_key}')  # oh boy
            checkBox_widget.setChecked(enable)

    def enable_crystal(self, enable):
        sender_object = QObject().sender()
        crystal_key = sender_object.text()
        self.johann_emission.enable_crystal(crystal_key, enable)

    def update_crystal_kind_fields(self):
        crystal, R, hkl, roll_offset = self.johann_emission.read_basic_crystal_config()
        for i in range(self.comboBox_johann_crystal_kind.count()):
            if self.comboBox_johann_crystal_kind.itemText(i) == crystal:
                self.comboBox_johann_crystal_kind.setCurrentIndex(i)
                break
        self.lineEdit_johann_hkl.setText('(' + ','.join([str(i) for i in hkl]) + ')')
        self.edit_johann_crystal_R.setText(str(R))
        for i in range(self.comboBox_johann_roll_offset.count()):
            if float(self.comboBox_johann_roll_offset.itemText(i)) == roll_offset:
                self.comboBox_johann_roll_offset.setCurrentIndex(i)
                break

    def update_johann_spectrometer_gui_elements(self):
        self.update_enabled_crystals_checkboxes()
        self.update_crystal_kind_fields()
        for i in range(self.comboBox_johann_roll_offset.count()):
            if self.johann_emission.rowland_circle.roll_offset == float(self.comboBox_johann_roll_offset.itemText(i)):
                self.comboBox_johann_roll_offset.setCurrentIndex(i)
                break
        self.johann_update_energy_limits_fields()

    def _johann_update_crystal_config(self):
        crystal = self.comboBox_johann_crystal_kind.currentText()
        # R = float(self.edit_johann_crystal_R.text())
        hkl = self.lineEdit_johann_hkl.text()
        hkl = hkl.replace(')', '').replace('(', '').replace(']', '').replace('[', '')
        hkl = [int(i) for i in hkl.split(',')]
        self.johann_emission.set_crystal(crystal)
        self.johann_emission.set_hkl(hkl)

    def johann_compute_geometry(self):
        self._johann_update_crystal_config()
        energy = float(self.widget_johann_line_selector.edit_E.text())
        bragg = self.johann_emission.e2bragg(energy)
        roll_offset = self.johann_emission.suggest_roll_offset(bragg)
        reflectivity = self.johann_emission.e2reflectivity(energy)

        self.lineEdit_johann_bragg.setText(f'{bragg:0.2f}')
        self.lineEdit_johann_reflectivity.setText(f'{reflectivity:0.2f}')

        for i in range(self.comboBox_johann_roll_offset.count()):
            if roll_offset == float(self.comboBox_johann_roll_offset.itemText(i)):
                self.comboBox_johann_roll_offset.setCurrentIndex(i)
                break

    def johann_move_motors(self):
        roll_offset = float(self.comboBox_johann_roll_offset.currentText())
        R = float(self.edit_johann_crystal_R.text())
        self.johann_emission.set_R(R)
        self.johann_emission.set_roll_offset(
            roll_offset)  # this will compute all the motor positions and will save the config to settings

        energy = float(self.widget_johann_line_selector.edit_E.text())
        self.johann_emission.move(energy=energy)

        self.johann_emission.initialized = True
        self.parent.widget_info_beamline.push_set_emission_energy.setEnabled(True)

        self.doubleSpinBox_johann_alignment_R_energy.setValue(energy)

    # Johann general scans
    def _get_motor_for_johann_motor_scan(self):
        curr_mot = self.comboBox_johann_scan_motor.currentText()
        for motor_key, motor_dict in self.motor_dictionary.items():
            if curr_mot == motor_dict['description']:
                liveplot_mot_kwargs = {'curr_mot_name': motor_dict['object'].name}
                break
        return curr_mot, liveplot_mot_kwargs

    def _johann_checked_pilatus_rois(self, _ch='checkBox_johann_pilatus_roi'):
        return [(i + 1) for i in range(4) if getattr(self, f'{_ch}{i + 1}').isChecked()]

    def _johann_checked_pilatus_channels(self, _ch='checkBox_johann_pilatus_roi'):
        return [f'pil100k2_stats{i}_total' for i in self._johann_checked_pilatus_rois(_ch=_ch)]

    def run_johann_motor_scan(self):
        detector = 'Pilatus 100k New'
        # _ch = 'checkBox_johann_pilatus_roi'
        # channels = [f'pil100k_stats{i + 1}_total' for i in range(4) if getattr(self, f'{_ch}{i + 1}').isChecked()]
        channels = self._johann_checked_pilatus_channels(_ch='checkBox_johann_motor_scan_pilatus_roi')
        channel = channels[0]
        liveplot_det_kwargs = {'channel': channel, 'channel_den': '1', 'result_name': channel}

        motor, liveplot_mot_kwargs = self._get_motor_for_johann_motor_scan()

        scan_range = self.doubleSpinBox_johann_motor_scan_range.value()
        scan_step = self.doubleSpinBox_johann_motor_scan_step.value()
        exposure_time = self.doubleSpinBox_johann_motor_scan_exp_time.value()

        self._run_any_scan([detector], liveplot_det_kwargs,
                           motor, liveplot_mot_kwargs,
                           scan_range, scan_step, exposure_time)


    # Johann alignment
    def _get_default_johann_alignment_parameters(self):
        _element_guess = self.widget_johann_line_selector.comboBox_element.currentText()
        _edge_guess = "K" if xraydb.atomic_number(_element_guess) < 55 else "L3"
        self._default_johann_alignment_paramters = \
            {'yaw_tune': {'motor_check': True,
                          'scan_range': 1000.0,
                          'scan_duration': 10.0,
                          'scan_step': 10.0,
                          'scan_exposure': 0.25},
             'roll_tune': {'motor_check': False,
                           'scan_range': 1000,
                           'scan_duration': 10,
                           'scan_step': 10,
                           'scan_exposure': 0.25},
             'scan_params': {'emission': {'scan_range': 1000,
                                          'scan_duration': 10,
                                          'scan_step': 10,
                                          'scan_exposure': 0.25},
                             'elastic':  {'scan_range': 15,
                                          'scan_duration': 10,
                                          'scan_step': 0.1,
                                          'scan_exposure': 0.25},
                             'herfd':    {'scan_element': _element_guess,
                                          'scan_edge': _edge_guess,
                                          'scan_range': 200,
                                          'scan_duration': 10,
                                          'scan_step': 0.1,
                                          'scan_exposure': 0.25},
                             }
             }

    def _update_default_johann_alignment_parameters(self):
        try:
            for tune_key in ['yaw_tune', 'roll_tune']:
                values = self._get_johann_scan_parameters_from_relevant_widgets(key=tune_key,
                                                                                scan_kind=self._previous_johann_alignment_scan_kind)
                param_keys = ['motor_check', 'scan_range', 'scan_duration', 'scan_step', 'scan_exposure']
                for param_key, value in zip(param_keys, values):
                    if value is not None:
                        self._default_johann_alignment_paramters[tune_key][param_key] = value

            scan_kwargs = self._johann_alignment_parse_scan_kwargs(alignment_strategy=self._previous_johann_alignment_strategy,
                                                                   scan_kind=self._previous_johann_alignment_scan_kind,
                                                                   add_herfd_prefix=False)
            for key, value in scan_kwargs.items():
                # print(self._previous_johann_alignment_strategy, key, value)
                if value is not None:
                    self._default_johann_alignment_paramters['scan_params'][self._previous_johann_alignment_strategy][key] = value
        except Exception as e:
            print(f'Could not update default widget values. Reason: {e}.')

    def update_comboBox_johann_alignment_crystal(self):
        self.comboBox_johann_alignment_crystal.clear()
        self.comboBox_johann_alignment_crystal.addItems(
            [c for c, enabled in self.johann_emission.enabled_crystals.items() if enabled])

        self.comboBox_johann_calibration_crystal.clear()
        self.comboBox_johann_calibration_crystal.addItems(['all/enabled'] +
            [c for c, enabled in self.johann_emission.enabled_crystals.items() if enabled])

        self.comboBox_johann_resolution_crystal.clear()
        self.comboBox_johann_resolution_crystal.addItems(
            [c for c, enabled in self.johann_emission.enabled_crystals.items() if enabled])

        self.comboBox_johann_tweak_motor.clear()
        self.comboBox_johann_tweak_motor.addItems(['X', 'R'])

    @property
    def _johann_alignment_scan_kind(self):
        return "fly" if self.radioButton_alignment_mode_fly.isChecked() else "step"

    @property
    def _johann_alignment_strategy(self):
        return self.comboBox_johann_alignment_strategy.currentText().lower()

    def _johann_label_row_widget(self, motor_label="Tune motor", with_button=False):
        widgets = []
        widgets.append(QLabel(motor_label))
        widgets.append(QLabel("Range"))
        widgets.append(QLabel(""))
        if self._johann_alignment_scan_kind == 'fly':
            widgets.append(QLabel("Duration"))
            widgets.append(QLabel(""))
        elif self._johann_alignment_scan_kind == 'step':
            widgets.append(QLabel("Step"))
            widgets.append(QLabel(""))
            widgets.append(QLabel("Exposure"))
            widgets.append(QLabel(""))
        return widgets

    def _johann_create_motor_widget_row(self, motor_check: bool = None,
                                        motor_str: str = 'yaw',
                                        motor_unit_str: str = 'mdeg',
                                        scan_range=1000, scan_duration=10,
                                        scan_step=10.0, scan_exposure=0.25,
                                        with_button=False):
        widgets = []
        relevant_widgets = {}
        if motor_check is None:
            _widget_motor = QLabel(motor_str)
        else:
            _widget_motor = QCheckBox(motor_str)
            _widget_motor.setChecked(motor_check)
        widgets.append(_widget_motor)
        relevant_widgets["scan_flag"] = _widget_motor

        _widget_scan_range = QLineEdit(str(scan_range))
        relevant_widgets["scan_range"] = _widget_scan_range
        widgets.append(_widget_scan_range)
        widgets.append(QLabel(motor_unit_str))
        if self._johann_alignment_scan_kind == 'fly':
            _widget_duration = QLineEdit(str(scan_duration))
            relevant_widgets["scan_duration"] = _widget_duration
            widgets.append(_widget_duration)
            widgets.append(QLabel("s"))
        elif self._johann_alignment_scan_kind == 'step':
            _widget_scan_step = QLineEdit(str(scan_step))
            relevant_widgets["scan_step"] = _widget_scan_step
            widgets.append(_widget_scan_step)
            widgets.append(QLabel(motor_unit_str))
            _widget_scan_exposure = QLineEdit(str(scan_exposure))
            relevant_widgets["scan_exposure"] = _widget_scan_exposure
            widgets.append(_widget_scan_exposure)
            widgets.append(QLabel("s"))

        if with_button:
            _widget_scan_button = QPushButton("Tune")
            _widget_scan_button.setObjectName(f"{motor_str}_tune_button")
            _widget_scan_button.clicked.connect(self.run_johann_tune_scan)
            relevant_widgets["scan_button"] = _widget_scan_button
            widgets.append(_widget_scan_button)

        return widgets, relevant_widgets

    def _johann_create_herfd_widget_rows(self, scan_element: str='Fe', scan_edge: str='K',
                                         scan_range: float=200.0, scan_duration: float=10.0,
                                         scan_step: float=0.1, scan_exposure: float=0.25):
        widgets0 = []
        widgets1 = []
        relevant_widgets = {"scan_flag": None}

        # _element_guess = self.widget_johann_line_selector.comboBox_element.currentText()
        # _z = xraydb.atomic_number(_element_guess)
        # _edge_guess = "K" if _z < 55 else "L3"

        _label_element = QLabel("Element")
        widgets0.append(_label_element)
        _label_element.setFixedWidth(int(30))
        _widget_element = QLineEdit(scan_element)
        _widget_element.setFixedWidth(int(30))
        relevant_widgets['scan_element'] = _widget_element
        widgets1.append(_widget_element)

        _label_edge = QLabel("Edge")
        _label_edge.setFixedWidth(int(30))
        widgets0.append(_label_edge)
        _widget_edge = QLineEdit(scan_edge)
        _widget_edge.setFixedWidth(int(30))
        relevant_widgets['scan_edge'] = _widget_edge
        widgets1.append(_widget_edge)

        widgets0.append(QLabel("Range"))
        _widget_range = QLineEdit(str(scan_range))
        relevant_widgets['scan_range'] = _widget_range
        widgets1.append(_widget_range)
        widgets0.append(QLabel(""))
        widgets1.append(QLabel("eV"))

        if self._johann_alignment_scan_kind == 'fly':
            widgets0.append(QLabel("Duration"))
            _widget_duration = QLineEdit(str(scan_duration))
            relevant_widgets['scan_duration'] = _widget_duration
            widgets1.append(_widget_duration)

            widgets0.append(QLabel(""))
            widgets1.append(QLabel("s"))

        elif self._johann_alignment_scan_kind == 'step':
            widgets0.append(QLabel("Step"))

            _widget_step = QLineEdit(str(scan_step))
            relevant_widgets['scan_step'] = _widget_step
            widgets1.append(_widget_step)

            widgets0.append(QLabel(""))
            widgets1.append(QLabel("eV"))

            widgets0.append(QLabel("Exposure"))
            _widget_exposure = QLineEdit(str(scan_exposure))
            relevant_widgets['scan_exposure'] = _widget_exposure
            widgets1.append(_widget_exposure)

            widgets0.append(QLabel(""))
            widgets1.append(QLabel("s"))

        return widgets0, widgets1, relevant_widgets

    def _handle_enabled_johann_alignment_widgets(self):
        if self.radioButton_alignment_mode_manual.isChecked():
            # self.comboBox_johann_alignment_fom.setEnabled(False)
            self.label_johann_alignment_crystal.setEnabled(True)
            self.label_johann_alignment_tweak_motor.setEnabled(True)
            self.comboBox_johann_alignment_crystal.setEnabled(True)
            self.comboBox_johann_tweak_motor.setEnabled(True)

            self.label_johann_alignment_tweak_range.setEnabled(False)
            self.label_johann_alignment_tweak_range_mm.setEnabled(False)
            self.label_johann_alignment_n_steps.setEnabled(False)
            self.doubleSpinBox_johann_alignemnt_tweak_range.setEnabled(False)
            self.spinBox_johann_alignment_n_steps.setEnabled(False)

        elif self.radioButton_alignment_mode_semi.isChecked():
            # self.comboBox_johann_alignment_fom.setEnabled(True)
            self.label_johann_alignment_crystal.setEnabled(True)
            self.label_johann_alignment_tweak_motor.setEnabled(True)
            self.comboBox_johann_alignment_crystal.setEnabled(True)
            self.comboBox_johann_tweak_motor.setEnabled(True)

            self.label_johann_alignment_tweak_range.setEnabled(True)
            self.label_johann_alignment_tweak_range_mm.setEnabled(True)
            self.label_johann_alignment_n_steps.setEnabled(True)
            self.doubleSpinBox_johann_alignemnt_tweak_range.setEnabled(True)
            self.spinBox_johann_alignment_n_steps.setEnabled(True)

        elif self.radioButton_alignment_mode_automatic.isChecked():
            # self.comboBox_johann_alignment_fom.setEnabled(True)
            self.label_johann_alignment_crystal.setEnabled(False)
            self.label_johann_alignment_tweak_motor.setEnabled(True)
            self.comboBox_johann_alignment_crystal.setEnabled(False)
            self.comboBox_johann_tweak_motor.setEnabled(True)

            self.label_johann_alignment_tweak_range.setEnabled(True)
            self.label_johann_alignment_tweak_range_mm.setEnabled(True)
            self.label_johann_alignment_n_steps.setEnabled(True)
            self.doubleSpinBox_johann_alignemnt_tweak_range.setEnabled(True)
            self.spinBox_johann_alignment_n_steps.setEnabled(True)

        if self.comboBox_johann_tweak_motor.currentText().lower() == 'r':
            self.label_johann_alignment_R_energy.setEnabled(True)
            self.label_johann_alignment_R_energy_eV.setEnabled(True)
            self.doubleSpinBox_johann_alignment_R_energy.setEnabled(True)
        else:
            self.label_johann_alignment_R_energy.setEnabled(False)
            self.label_johann_alignment_R_energy_eV.setEnabled(False)
            self.doubleSpinBox_johann_alignment_R_energy.setEnabled(False)

    def _handle_johann_scope_scan_widgets(self, scope='alignment', strategy='emission'):
        scan_widget_list = getattr(self, f'johann_{scope}_scan_widget_list')
        scan_layout = getattr(self, f'johann_{scope}_scan_layout')
        parameter_widget_dict = getattr(self, f'_johann_{scope}_parameter_widget_dict')

        for widget in scan_widget_list:
            scan_layout.removeWidget(widget)
            widget.deleteLater()
        scan_widget_list.clear() # scan_widget_list is a pointer and to clear it up we use clear

        if (strategy == 'emission') or (strategy == 'roll'):
            _widgets0_scan = self._johann_label_row_widget(motor_label="scan motor")
            _widgets1_scan, _johann_scan_dict = self._johann_create_motor_widget_row(motor_check=None,
                                                                                     motor_str='roll',
                                                                                     motor_unit_str='mdeg',
                                                                                     **self._default_johann_alignment_paramters['scan_params']['emission'])
        elif strategy == 'elastic':
            _widgets0_scan = self._johann_label_row_widget(motor_label="scan motor")
            _widgets1_scan, _johann_scan_dict = self._johann_create_motor_widget_row(motor_check=None,
                                                                                     motor_str='energy',
                                                                                     motor_unit_str='eV',
                                                                                     **self._default_johann_alignment_paramters['scan_params']['elastic'])
        elif strategy == 'herfd':
            _widgets0_scan, _widgets1_scan, _johann_scan_dict = self._johann_create_herfd_widget_rows(**self._default_johann_alignment_paramters['scan_params']['herfd'])

        parameter_widget_dict['scan_params'] = _johann_scan_dict
        scan_widget_list.extend(_widgets0_scan + _widgets1_scan)

        for i in range(len(_widgets0_scan)):
            scan_layout.addWidget(_widgets0_scan[i], 0, i)
            scan_layout.addWidget(_widgets1_scan[i], 1, i)

    def handle_johann_alignment_widgets(self, gui_initialized=True):
        # remember the state of old widgets
        if gui_initialized:
            self._update_default_johann_alignment_parameters()

        # clean up old widgets
        self._johann_alignment_parameter_widget_dict = {}

        self._handle_enabled_johann_alignment_widgets()
        for widget in self.johann_alignment_tune_widget_list:
            self.johann_alignment_tune_layout.removeWidget(widget)
            widget.deleteLater()
        self.johann_alignment_tune_widget_list = []

        tweak_motor_widgets = []

        if (self.comboBox_johann_alignment_crystal.count() == 0) or \
           (self.comboBox_johann_tweak_motor.count() == 0):
            # sometimes during widget updates the widgets get polled before being populated raising unnecessary errors
            # this piece allows to skip updates if fields are not populated
            return

        crystal_str = self.comboBox_johann_alignment_crystal.currentText()
        motor_str = self.comboBox_johann_tweak_motor.currentText()
        if motor_str == 'X':
            if crystal_str == 'main':
                motor_key = 'auxxy_x'
            else:
                motor_key = f'johann_cr_{crystal_str}_x'
            widget = UIWidgetMotors(self.motor_dictionary[motor_key], motor_description_width=500,
                                    horizontal_scale=0.9)
        elif motor_str == 'R':
            widget = UIWidgetSpectrometerR(johann_emission=self.johann_emission, spinbox_energy=self.doubleSpinBox_johann_alignment_R_energy,
                                            plan_processor=self.plan_processor, parent=self)
        else:
            raise NotImplementedError('Tweak motor must be either R or X. No other options are implemented!')
            # widget = None

        self.johann_alignment_tune_widget_list.append(widget)
        self._johann_alignment_parameter_widget_dict['tweak_motor'] = widget
        tweak_motor_widgets.append(widget)

        # elif self.radioButton_alignment_mode_semi.isChecked() or self.radioButton_alignment_mode_automatic.isChecked():
        labels_tune_widgets = self._johann_label_row_widget(motor_label="Tune motor")
        yaw_tune_widgets, yaw_tune_relevant_widgets = self._johann_create_motor_widget_row(
            motor_str='yaw', motor_unit_str='mdeg', with_button=True,
            **self._default_johann_alignment_paramters['yaw_tune'])
        self._johann_alignment_parameter_widget_dict['yaw_tune'] = yaw_tune_relevant_widgets

        roll_tune_widgets, roll_tune_relevant_widgets = self._johann_create_motor_widget_row(
            motor_str='roll', motor_unit_str='mdeg', with_button=True,
            **self._default_johann_alignment_paramters['roll_tune'])
        self._johann_alignment_parameter_widget_dict['roll_tune'] = roll_tune_relevant_widgets

        self.johann_alignment_tune_widget_list.extend(labels_tune_widgets + yaw_tune_widgets + roll_tune_widgets)

        for widget in tweak_motor_widgets:
            self.johann_alignment_tune_layout.addWidget(widget, 0, 0, 1, len(labels_tune_widgets) + 1)
            widget.setEnabled(self.radioButton_alignment_mode_manual.isChecked())

        tune_widget_row_offset = len(tweak_motor_widgets)
        for row, _widget_list in enumerate([labels_tune_widgets, yaw_tune_widgets, roll_tune_widgets]):
            for col, _widget in enumerate(_widget_list):
                self.johann_alignment_tune_layout.addWidget(_widget, row + tune_widget_row_offset, col)

        self._handle_johann_scope_scan_widgets(scope='alignment', strategy=self._johann_alignment_strategy)
        self._previous_johann_alignment_strategy = self._johann_alignment_strategy
        self._previous_johann_alignment_scan_kind = self._johann_alignment_scan_kind

    def _get_johann_scan_parameters_from_relevant_widgets(self, key='yaw_tune', scan_kind=None, scan_scope='alignment'):
        d = getattr(self, f'_johann_{scan_scope}_parameter_widget_dict')[key]
        if scan_kind is None:
            scan_kind = self._johann_alignment_scan_kind
        scan_flag = bool(d['scan_flag'].isChecked()) if type(d['scan_flag']) == QCheckBox else True
        scan_range = float(d['scan_range'].text())
        scan_duration = float(d['scan_duration'].text()) if scan_kind == 'fly' else None
        scan_step = float(d['scan_step'].text()) if scan_kind == 'step' else None
        scan_exposure = float(d['scan_exposure'].text()) if scan_kind == 'step' else None
        return (scan_flag, scan_range, scan_duration, scan_step, scan_exposure)

    def _parse_johann_tune_motor_dict(self, motor='yaw_tune', key_prefix=None, scan_kind=None, scan_scope='alignment'):
        if key_prefix is None: key_prefix = motor
        values = self._get_johann_scan_parameters_from_relevant_widgets(key=motor, scan_kind=scan_kind, scan_scope=scan_scope)
        keys = [f'{key_prefix}', f'{key_prefix}_range', f'{key_prefix}_duration', f'{key_prefix}_step', f'{key_prefix}_exposure']
        output = {k: v for k, v in zip(keys, values)}
        return output

    def _johann_alignment_parse_tune_kwargs(self):
        output = {}
        for key in ['yaw_tune', 'roll_tune']:
            if key in self._johann_alignment_parameter_widget_dict.keys():
                tune_kwargs = self._parse_johann_tune_motor_dict(key)
                output = {**output, **tune_kwargs}
        return output

    def _johann_alignment_parse_scan_kwargs(self, alignment_strategy=None, scan_kind=None, add_herfd_prefix=True, scan_scope='alignment'):
        output = self._parse_johann_tune_motor_dict(motor='scan_params', key_prefix='scan', scan_kind=scan_kind, scan_scope=scan_scope)
        output.pop('scan')
        if alignment_strategy is None:
            alignment_strategy = getattr(self, f'_johann_{scan_scope}_strategy')
        if alignment_strategy == 'herfd':
            d = self._johann_alignment_parameter_widget_dict['scan_params']
            if add_herfd_prefix:
                output['herfd_scan_element'] = d['scan_element'].text()
                output['herfd_scan_edge'] = d['scan_edge'].text()
            else:
                output['scan_element'] = d['scan_element'].text()
                output['scan_edge'] = d['scan_edge'].text()
        return output

    def run_johann_tune_scan(self):
        sender_object_name = self.sender().objectName()

        plan_name = 'tune_johann_piezo_plan'

        plan_kwargs = {}
        plan_kwargs['pil100k_roi_num'] = self._johann_checked_pilatus_rois()[0]
        plan_kwargs['scan_kind'] = self._johann_alignment_scan_kind
        plan_kwargs['crystal'] = self.comboBox_johann_alignment_crystal.currentText()

        if sender_object_name == 'yaw_tune_button':
            axis = 'yaw'
        elif sender_object_name == 'roll_tune_button':
            axis = 'roll'
        plan_kwargs['axis'] = axis

        _, scan_range, duration, step_size, exposure_time = self._get_johann_scan_parameters_from_relevant_widgets(key=f'{axis}_tune')
        plan_kwargs['scan_range'] = scan_range
        if self._johann_alignment_scan_kind == 'fly':
            plan_kwargs = {**plan_kwargs,
                           'duration': duration}
            plan_gui_services = ['spectrometer_plot_epics_fly_scan_data']
        elif self._johann_alignment_scan_kind == 'step':
            plan_kwargs = {**plan_kwargs, 'step_size': step_size, 'exposure_time': exposure_time}
            plan_gui_services = None

        # plan_kwargs['plot_func'] = None
        plan_kwargs['liveplot_kwargs'] = {'tab': 'spectrometer'}
        plan_kwargs['md'] = None

        if self.radioButton_alignment_mode_automatic.isChecked():
            plans = []
            for crystal in [c for c, enabled in self.johann_emission.enabled_crystals.items() if enabled]:
                _plan_kwargs = copy.deepcopy(plan_kwargs)
                _plan_kwargs['crystal'] = crystal
                plan_dict = {'plan_name': plan_name, 'plan_kwargs': _plan_kwargs}
                if plan_gui_services is not None:
                    plan_dict['plan_gui_services'] = plan_gui_services
                plans.append(plan_dict)
                # to keep the plots after the first scan in the batch:
                if _plan_kwargs['liveplot_kwargs'] is not None:
                    _plan_kwargs['liveplot_kwargs'] = None
            self.plan_processor.add_plans(plans)
            self.plan_processor.run_if_idle()
        else:
            self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs, plan_gui_services=plan_gui_services)

    def run_johann_alignment_scan(self):
        plan_name = 'johann_spectrometer_alignment_plan_bundle'
        plan_kwargs = {}

        plan_kwargs['alignment_motor'] = self.comboBox_johann_tweak_motor.currentText()
        if self.radioButton_alignment_mode_manual.isChecked():
            plan_kwargs['crystals'] = [self.comboBox_johann_alignment_crystal.currentText()]
            plan_kwargs['motor_range'] = 0
            plan_kwargs['motor_num_steps'] = 1
            plan_kwargs['automatic_mode'] = False
            plan_kwargs['post_tuning'] = False
        elif self.radioButton_alignment_mode_semi.isChecked():
            plan_kwargs['crystals'] = [self.comboBox_johann_alignment_crystal.currentText()]
            plan_kwargs['motor_range'] = float(self.doubleSpinBox_johann_alignemnt_tweak_range.value())
            plan_kwargs['motor_num_steps'] = int(self.spinBox_johann_alignment_n_steps.value())
            plan_kwargs['automatic_mode'] = False
            plan_kwargs['post_tuning'] = False
        elif self.radioButton_alignment_mode_automatic.isChecked():
            plan_kwargs['crystals'] = None
            plan_kwargs['motor_range'] = float(self.doubleSpinBox_johann_alignemnt_tweak_range.value())
            plan_kwargs['motor_num_steps'] = int(self.spinBox_johann_alignment_n_steps.value())
            plan_kwargs['automatic_mode'] = True
            plan_kwargs['post_tuning'] = True

        if self.comboBox_johann_tweak_motor.currentText().lower() == 'r':
            plan_kwargs['spectrometer_nominal_energy'] = float(self.doubleSpinBox_johann_alignment_R_energy.value())

        plan_kwargs['alignment_strategy'] = self._johann_alignment_strategy
        plan_kwargs['scan_kind'] = self._johann_alignment_scan_kind
        plan_kwargs['automatic_fom'] = f'{self.comboBox_johann_alignment_fom.currentText()}_value'
        plan_kwargs['pil100k_roi_num'] = self._johann_checked_pilatus_rois()[0]
        plan_kwargs['scan_tag'] = self.lineEdit_johann_alignment_scan_tag.text()

        plan_kwargs['liveplot_kwargs'] = {'tab': 'spectrometer', 'figure': 'proc_figure'}
        plan_kwargs['plan_gui_services'] = ['spectrometer_plot_alignment_scan_data',
                                            'spectrometer_plot_alignment_analysis_data']
        tune_kwargs = self._johann_alignment_parse_tune_kwargs()
        scan_kwargs = self._johann_alignment_parse_scan_kwargs()
        plan_kwargs = {**plan_kwargs, **tune_kwargs, **scan_kwargs}

        self.plan_processor.add_plans({'plan_name': plan_name, 'plan_kwargs': plan_kwargs})
        # self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)

    def johann_reset_alignment_data(self):
        self.johann_emission.reset_alignment_data()

    def johann_plot_alignment_data(self):
        self.canvas_proc.mpl_disconnect(self.cid_proc)
        update_figure([self.figure_proc.ax], self.toolbar_proc, self.canvas_proc)

        df = pd.DataFrame(self.johann_alignment_data)
        motor_key = self.comboBox_johann_tweak_motor.currentText()
        fwhm = df['fwhm'].values
        ecen = df['ecen'].values
        res = np.sqrt(fwhm ** 2 - (1.3e-4 * ecen) ** 2)
        x = df[motor_key].values
        self.figure_proc.ax.plot(x, fwhm, 'o')
        self.figure_proc.ax.plot(x, res, '+')
        self.figure_proc.ax.set_ylabel('FWHM/resolution, eV')
        self.figure_proc.ax.set_xlabel(motor_key)

        self.figure_proc.tight_layout()
        self.canvas_proc.draw_idle()

        self._set_canvas_proc_motor_from_description(motor_key)

        self.cid_proc = self.canvas_proc.mpl_connect('button_press_event', self.getX_proc)

    # Johann calibration and registration
    @property
    def _johann_calibration_strategy(self):
        return self.comboBox_johann_calibration_strategy.currentText().lower()

    def _handle_enabled_johann_calbration_widgets(self):
        if self._johann_calibration_strategy == 'roll':
            self.label_johann_calibration_roll_range.setEnabled(False)
            self.doubleSpinBox_johann_calibration_roll_range.setEnabled(False)
            self.label_johann_calibration_roll_range_units.setEnabled(False)
            self.label_johann_calibration_roll_nsteps.setEnabled(False)
            self.spinBox_johann_calibration_roll_nsteps.setEnabled(False)
        elif self._johann_calibration_strategy == 'herfd':
            self.label_johann_calibration_roll_range.setEnabled(True)
            self.doubleSpinBox_johann_calibration_roll_range.setEnabled(True)
            self.label_johann_calibration_roll_range_units.setEnabled(True)
            self.label_johann_calibration_roll_nsteps.setEnabled(True)
            self.spinBox_johann_calibration_roll_nsteps.setEnabled(True)

    def handle_johann_calibration_widgets(self):
        self._handle_enabled_johann_calbration_widgets()
        self._handle_johann_scope_scan_widgets(scope='calibration', strategy=self._johann_calibration_strategy)

    def run_johann_calibration_scan(self):
        plan_name = 'johann_spectrometer_calibration_plan_bundle'
        plan_kwargs = {}
        _crystal_str = self.comboBox_johann_calibration_crystal.currentText()
        if _crystal_str == 'all/enabled': plan_kwargs['crystals'] = None
        else: plan_kwargs['crystals'] = [_crystal_str]

        plan_kwargs['mono_energy'] = self.doubleSpinBox_johann_calibration_mono_energy.value()
        plan_kwargs['fom'] = self.comboBox_johann_calibration_fom.currentText()
        plan_kwargs['calibration_strategy'] = self._johann_calibration_strategy
        plan_kwargs['scan_kind'] = self._johann_alignment_scan_kind
        plan_kwargs['pil100k_roi_num'] = self._johann_checked_pilatus_rois()[0]

        plan_kwargs['tweak_roll_range'] = self.doubleSpinBox_johann_calibration_roll_range.value()
        plan_kwargs['tweak_roll_num_steps'] = self.spinBox_johann_calibration_roll_nsteps.value()


        plan_kwargs['liveplot_kwargs'] = {'tab': 'spectrometer', 'figure': 'proc_figure'}
        plan_kwargs['plan_gui_services'] = ['spectrometer_plot_alignment_scan_data',
                                            'spectrometer_plot_alignment_analysis_data']

        scan_kwargs = self._johann_alignment_parse_scan_kwargs(scan_scope='calibration')
        # print(f'{scan_kwargs=}')
        plan_kwargs = {**plan_kwargs, **scan_kwargs}
        self.plan_processor.add_plans({'plan_name': plan_name, 'plan_kwargs': plan_kwargs})
        # self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)

    def _handle_enabled_johann_resolution_widgets(self):
        state = self.checkBox_johann_bender_scan.isChecked()
        self.label_johann_resolution_crystal.setEnabled(state)
        self.comboBox_johann_resolution_crystal.setEnabled(state)
        self.label_johann_bender_scan_range.setEnabled(state)
        self.doubleSpinBox_johann_bender_scan_range.setEnabled(state)
        self.label_johann_bender_scan_range_units.setEnabled(state)
        self.label_johann_bender_n_steps.setEnabled(state)
        self.spinBox_johann_bender_n_steps.setEnabled(state)

    def handle_johann_resolution_widgets(self):
        self._handle_enabled_johann_resolution_widgets()
        self._handle_johann_scope_scan_widgets(scope='resolution', strategy='elastic')

    def run_johann_resolution_scan(self):
        plan_kwargs = {}
        if self.checkBox_johann_bender_scan.isChecked():
            plan_name = 'johann_bender_scan_plan_bundle'
            plan_kwargs['crystal'] = self.comboBox_johann_resolution_crystal.currentText()
            plan_kwargs['bender_tweak_range'] = self.doubleSpinBox_johann_bender_scan_range.value()
            plan_kwargs['bender_tweak_n_steps'] = self.spinBox_johann_bender_n_steps.value()
            plan_kwargs['liveplot_kwargs'] = {'tab': 'spectrometer', 'figure': 'proc_figure'}
        else:
            plan_name = 'johann_spectrometer_resolution_plan_bundle'
            plan_kwargs['liveplot_kwargs'] = {'tab': 'spectrometer'}

        plan_kwargs['mono_energy'] = self.doubleSpinBox_johann_resolution_mono_energy.value()
        plan_kwargs['scan_kind'] = self._johann_alignment_scan_kind
        plan_kwargs['pil100k_roi_num'] = self._johann_checked_pilatus_rois()[0]


        plan_kwargs['plan_gui_services'] = ['spectrometer_plot_alignment_scan_data',
                                            'spectrometer_plot_alignment_analysis_data']

        scan_kwargs = self._johann_alignment_parse_scan_kwargs(scan_scope='resolution')
        plan_kwargs = {**plan_kwargs, **scan_kwargs}
        self.plan_processor.add_plans({'plan_name': plan_name, 'plan_kwargs': plan_kwargs})
        # self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)

    def johann_register_energy(self):
        energy = float(self.lineEdit_johann_energy_init.text())
        self.johann_emission.register_energy(energy)

    def johann_set_energy_limits(self):
        e_lo = float(self.lineEdit_johann_energy_lim_lo.text())
        e_hi = float(self.lineEdit_johann_energy_lim_hi.text())
        self.johann_emission.set_energy_limits(e_lo, e_hi)

    def johann_update_energy_limits_fields(self):
        e_lo, e_hi = self.johann_emission.read_energy_limits()
        self.lineEdit_johann_energy_lim_lo.setText(str(e_lo))
        self.lineEdit_johann_energy_lim_hi.setText(str(e_hi))

    def johann_reset_energy_limits(self):
        self.lineEdit_johann_energy_lim_lo.setText('')
        self.lineEdit_johann_energy_lim_hi.setText('')
        self.johann_emission.reset_energy_limits()

    # Johann config manager
    def _make_spectrometer_config_item(self, item_str, index, kind=''):
        item = QtWidgets.QTreeWidgetItem(self.treeWidget_johann_config)
        item.setText(0, item_str)
        item.setExpanded(True)
        item.kind = kind
        item.index = index
        return item

    def update_johann_config_tree(self):
        self.treeWidget_johann_config.clear()
        for i, config_dict in enumerate(self.johann_spectrometer_manager.configs[::-1]):
            item_str = self.johann_spectrometer_manager.generate_config_str(config_dict)
            self._make_spectrometer_config_item(item_str, i)
            # config = config_dict['config']

    def johann_create_config(self):
        name = self.lineEdit_johann_config_name.text()
        if name != '':
            self.johann_spectrometer_manager.add_current_config(name)

    def johann_set_current_config(self):
        qt_index = self.treeWidget_johann_config.selectedIndexes()[0]
        qt_item = self.treeWidget_johann_config.itemFromIndex(qt_index)
        n_configs = len(self.johann_spectrometer_manager.configs)
        index = n_configs - 1 - qt_item.index
        self.johann_spectrometer_manager.set_config_by_index(index)
        self.parent.widget_info_beamline.push_set_emission_energy.setEnabled(True)

    # Johann additional buttons
    def open_motor_widget(self):
        self.widget_motor_detachable = QtWidgets.QWidget()
        self.widget_motor_detachable.setWindowTitle(f"Spectrometer Motors")
        self.widget_motor_detachable.setGeometry(1100, 1100, 1600, 1000)
        self.layout_spectrometer_motors = QtWidgets.QVBoxLayout(self.widget_motor_detachable)
        self.widget_spectrometer_motors = UISpectrometerMotors(motor_dict=self.motor_dictionary, parent=self)
        self.layout_spectrometer_motors.addWidget(self.widget_spectrometer_motors)
        self.widget_motor_detachable.show()
        print('Done')

    def johann_put_detector_to_safe_position(self):
        self.johann_emission.put_detector_to_safe_position()

    # def update_scan_figure_for_energy_scan(self, E, I_fit_raw):
    #     self.canvas_scan.mpl_disconnect(self.cid_scan)
    #     self.figure_scan.ax.plot(E, I_fit_raw, 'r-')
    #     self.figure_scan.tight_layout()
    #     self.canvas_scan.draw_idle()
    #     self.cid_scan = self.canvas_scan.mpl_connect('button_press_event', self.getX_scan)

    # def update_proc_figure(self, x_key):
    #     # managing figures
    #     self.canvas_proc.mpl_disconnect(self.cid_proc)
    #     if x_key == 'calibration':
    #         update_figure([self.figure_proc.ax], self.toolbar_proc, self.canvas_proc)
    #         data = self.widget_johann_tools._calibration_data
    #         energy_nom = data['energy_nom'].values
    #         energy_act = data['energy_act'].values
    #         energy_error = energy_act - energy_nom
    #         resolution = data['resolution'].values
    #         ax = self.figure_proc.ax
    #         ax.plot(energy_nom, energy_error, 'k.-')
    #         ax.set_xlabel('nominal energy, eV')
    #         ax.set_ylabel('energy error, eV')
    #         ax2 = self.figure_proc.ax.twinx()
    #         ax2.plot(energy_nom, resolution, 'rs-')
    #         ax2.set_ylabel('resolution, eV', color='r')
    #         ax.set_xlim(energy_nom.min() - 10, energy_nom.max() + 10)
    #
    #     else:
    #         motor_pos = self.widget_johann_tools._alignment_data[x_key].values
    #         fwhm = self.widget_johann_tools._alignment_data['fwhm'].values
    #         ecen = self.widget_johann_tools._alignment_data['ecen'].values
    #         res = np.sqrt(fwhm ** 2 - (1.3e-4 * ecen) ** 2)
    #
    #         for each_pos, each_fwhm, each_res in zip(motor_pos, fwhm, res):
    #             self.figure_proc.ax.plot(each_pos, each_fwhm, 'o')
    #             self.figure_proc.ax.plot(each_pos, each_res, '+')
    #
    #         self.figure_proc.ax.set_ylabel('FWHM/resolution, eV')
    #         self.figure_proc.ax.set_xlabel(x_key)
    #
    #     self.figure_proc.tight_layout()
    #     self.canvas_proc.draw_idle()
    #     self.cid_proc = self.canvas_proc.mpl_connect('button_press_event', self.getX_proc)













    # def _update_figure_with_resolution_data(self, energy, intensity, intensity_fit, ecen, fwhm, roi_label='roi1',
    #                                         roi_color='tab:blue'):
    #     self.figure_scan.ax.plot(energy, intensity, '.', label=f'{roi_label}', color=roi_color, ms=15)
    #     self.figure_scan.ax.plot(energy, intensity_fit, '-', color=roi_color)
    #
    #     e_lo = ecen - fwhm / 2
    #     e_hi = ecen + fwhm / 2
    #     self.figure_scan.ax.plot([e_lo, e_hi], [0.5, 0.5], '-', color=roi_color, lw=0.5)
    #     self.figure_scan.ax.text(ecen, 0.55, f'{fwhm:0.3f}', color=roi_color, ha='center', va='center')
    #
    #     self.figure_scan.ax.set_xlabel('Energy')
    #     self.figure_scan.ax.set_ylabel('intensity')
    #     self.figure_scan.ax.set_xlim(energy[0], energy[-1])
    #     self.figure_scan.legend(loc='upper left')
    #     self.figure_scan.tight_layout()
    #     self.canvas_scan.draw_idle()
    #     self.canvas_scan.motor = self.hhm.energy
    #     self.lineEdit_johann_energy_init.setText(f'{ecen :0.3f}')
    #
    #     # self.update_johann_alignment_data(ecen, fwhm)
    #     # self.plot_johann_alignment_data(purpose='alignment')











