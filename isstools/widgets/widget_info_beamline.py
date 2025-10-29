
from PyQt5 import uic, QtGui, QtCore
import pkg_resources
import requests
import urllib.request
import numpy as np
import os
import re
import time as ttime
import json

from isstools.dialogs import UpdateUserDialog, SetEnergy, GetEmailAddress
from timeit import default_timer as timer
from isstools.dialogs.BasicDialogs import message_box, question_message_box
import bluesky.plan_stubs as bps


import uuid

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_info_beamline.ui')

ROOT_PATH_SHARED = '/nsls2/data/iss/legacy/xf08id'


class UIInfoBeamline(*uic.loadUiType(ui_path)):

    def __init__(self,
                 accelerator=None,
                 front_end=None,
                 hhm = None,
                 hhm_feedback = None,
                 motor_emission=None,
                 inclinometers = None,
                 shutters=None,
                 ic_amplifiers = None,
                 apb=None,
                 RE = None,
                 plan_processor=None,
                 db = None,
                 foil_camera=None,
                 attenuator_camera=None,
                 encoder_pb=None,
                 aux_plan_funcs=None,
                 parent = None,

                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        # Start QTimer to display current day and time




        self.hhm = hhm
        self.hhm_feedback = hhm_feedback
        self.motor_emission = motor_emission
        self.apb = apb
        self.RE = RE
        self.plan_processor = plan_processor
        self.inclinometers = inclinometers
        self.db = db
        self.shutters = shutters
        self.ic_amplifiers = ic_amplifiers
        self.parent = parent
        self.hhm= hhm
        self.foil_camera = foil_camera
        self.attenuator_camera = attenuator_camera
        self.encoder_pb = encoder_pb
        self.aux_plan_funcs = aux_plan_funcs
        # Initialize general settings
        self.accelerator = accelerator
        self.front_end = front_end
        self.accelerator.beam_current.subscribe(self.update_beam_current)
        self.accelerator.status.subscribe(self.update_accelerator_status)

        self.comboBox_set_i0_gain.currentIndexChanged.connect(self.set_i0_gain)
        self.comboBox_set_it_gain.currentIndexChanged.connect(self.set_it_gain)
        self.comboBox_set_ir_gain.currentIndexChanged.connect(self.set_ir_gain)
        self.comboBox_set_if_gain.currentIndexChanged.connect(self.set_if_gain)
        self.push_get_offsets.clicked.connect(self.get_offsets)
        self.push_auto_gains.clicked.connect(self.adjust_gains)
        self.push_set_energy.clicked.connect(self.set_energy)
        self.push_set_emission_energy.setEnabled(self.motor_emission.initialized)
        self.push_set_emission_energy.clicked.connect(self.set_emission_energy)
        self.push_jog_pitch_neg.clicked.connect(self.tweak_pitch_neg)
        self.push_jog_pitch_pos.clicked.connect(self.tweak_pitch_pos)
        self.push_auto_pitch.clicked.connect(self.auto_pitch)
        self.push_recover_pitch.clicked.connect(self.recover_pitch)


        self.timer_update_time = QtCore.QTimer(self)
        self.timer_update_time.setInterval(1000)
        self.timer_update_time.timeout.connect(self.update_status)
        self.timer_update_time.start()

        self.timer_update_slits = QtCore.QTimer(self)
        self.timer_update_slits.setInterval(60000)
        self.timer_update_slits.timeout.connect(self.update_slits)
        self.timer_update_slits.singleShot(0, self.update_slits)
        self.timer_update_slits.start()


        self.push_set_reference_foil.clicked.connect(self.set_reference_foil)

        # self.set_autofoil(self.checkBox_autofoil.isChecked())
        self.checkBox_autofoil.setChecked(self.plan_processor.auto_foil_set)
        self.checkBox_autofoil.clicked.connect(self.set_autofoil)
        self.push_set_attenuator.clicked.connect(self.set_attenuator)

        self.push_pilatus_image.clicked.connect(self.take_pilatus_image)


        with open(f'{ROOT_PATH_SHARED}/settings/json/foil_wheel.json') as fp:
            reference_foils = [item['element'] for item in json.load(fp)]
            reference_foils.append('--')
        for foil in reference_foils:
            self.comboBox_reference_foils.addItem(foil)

        with open(f'{ROOT_PATH_SHARED}/settings/json/attenuator.json') as fp:
            attenuators = [item['attenuator'] for item in json.load(fp)]
        for att in attenuators:
            self.comboBox_attenuator.addItem(att)

    def update_status(self):
        try:
            # print(self.parent.scan_processor.plan_list)
            energy = self.hhm.energy.read()['hhm_energy']['value']
            self.label_energy.setText('Energy is {:.1f} eV'.format(energy))

            if self.motor_emission.initialized:
                emission_energy = self.motor_emission.energy.position
                self.label_emission_energy.setText('Emission Energy is {:.1f} eV'.format(emission_energy))
            else:
                self.label_emission_energy.setText('Emission Energy N/A')

            if self.hhm_feedback.status and self.hhm_feedback.shutters_open:
                if not self.hhm_feedback.status_err: # no error
                    self.label_feedback_status.setText('Feedback on')
                    self.label_feedback_status.setStyleSheet('color: rgb(19, 139, 67)')
                    self.label_feedback_status_indicator.setStyleSheet('background-color: rgb(95, 249, 95)')
                else: # error
                    self.label_feedback_status.setText(f'Feedback error: {self.hhm_feedback.status_msg}')
                    self.label_feedback_status.setStyleSheet('color: rgb(180, 0, 0)')
                    self.label_feedback_status_indicator.setStyleSheet('background-color: rgb(255, 128, 0)')
            else:
                self.label_feedback_status.setText('Feedback off')
                self.label_feedback_status.setStyleSheet('color: rgb(190,190,190)')
                self.label_feedback_status_indicator.setStyleSheet('background-color: rgb(0,94,0)')

            i0_gain = self.ic_amplifiers['i0_amp'].get_gain()[0]
            it_gain = self.ic_amplifiers['it_amp'].get_gain()[0]
            ir_gain = self.ic_amplifiers['ir_amp'].get_gain()[0]
            if_gain = self.ic_amplifiers['iff_amp'].get_gain()[0]

            self.label_gain_i0.setText(f'I<sub>0</sub>: 10<sup>{i0_gain}</sup>')
            self.label_gain_it.setText(f'I<sub>t</sub>: 10<sup>{it_gain}</sup>')
            self.label_gain_ir.setText(f'I<sub>r</sub>: 10<sup>{ir_gain}</sup>')
            self.label_gain_if.setText(f'I<sub>f</sub>: 10<sup>{if_gain}</sup>')
            if (self.RE.state == 'idle'):
                self.label_RE.setText('Run Engine is idle')
                self.label_RE_status_indicator.setStyleSheet('background-color: rgb(0,94,0)')
            elif (self.RE.state == 'running'):
                self.label_RE.setText('Run Engine is running')
                self.label_RE_status_indicator.setStyleSheet('background-color: rgb(95,249,95)')
            elif (self.RE.state == 'paused'):
                self.label_RE.setText('Run Engine is paused')
                self.label_RE_status_indicator.setStyleSheet('background-color: rgb(255,153,51)')
            elif (self.RE.state == 'abort'):
                self.label_RE.setText('Run Engine is aborted')
                self.label_RE_status_indicator.setStyleSheet('background-color: rgb(255,0,0)')

            #reference foil
            barcode = self.foil_camera.barcode1
              
            if barcode:
                if barcode == 'empty':
                    self.label_reference_foil.setText(f'No reference foil set')
                else:
                    self.label_reference_foil.setText(f'Reference {str(barcode)}')
            else:
                self.label_reference_foil.setText(f'Check reference foil')

            
            barcode1 = str(self.attenuator_camera.bar1.get()[:-1], encoding='UTF-8')

            if barcode1 == '0':
                self.label_attenuator.setText(f'No attenuation')
            elif barcode1 == '':
                self.label_attenuator.setText(f'Check attenuation')
            else:
                self.label_attenuator.setText(f'Attenuation {barcode1} um Al')

            #show encoder readout error
            error = 360000*self.hhm.theta.position-self.encoder_pb.pos_I.get()
            self.label_offset_error.setText(f'Encoder error: {int(error)}')

            #inclinometers
            self.label_spectrometer_gonio1_sp.setText('{:.2f}°'.format(self.motor_emission.motor_det_th1.position))
            self.label_spectrometer_gonio1_rb.setText('{:.2f}°'.format(self.inclinometers[0].position_from_sensor))

            #check for detector saturation
            saturation_list = [{'ch':self.apb.ch1.value, 'label':self.label_i0_saturation },
                               {'ch':self.apb.ch2.value, 'label':self.label_it_saturation },
                               {'ch':self.apb.ch3.value, 'label':self.label_ir_saturation },
                               {'ch':self.apb.ch4.value, 'label':self.label_iff_saturation }]
            for element in saturation_list:
                if element['ch'] < 7000:
                    element['label'].setStyleSheet('background-color: rgb(95,249,95)')
                    element['label'].setText('In range')
                else:
                    element['label'].setStyleSheet('background-color: rgb(255,0,0)')
                    element['label'].setText('Saturated')

            #update feedback heartbeat
            self.update_feedback_gui_components()



        except Exception as e:
            print(e)


    def update_beam_current(self, **kwargs):
        # return
        self.label_beam_current.setText('Beam current is {:.1f} mA'.format(kwargs['value']))

    def update_accelerator_status(self, **kwargs):
        # return
        if kwargs['value'] == 0:
            self.label_accelerator_status.setText('Beam available')
            self.label_accelerator_status.setStyleSheet('color: rgb(19,139,67)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(95,249,95)')
        elif kwargs['value'] == 1:
            self.label_accelerator_status.setText('Setup')
            self.label_accelerator_status.setStyleSheet('color: rgb(209,116,42)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(246,229,148)')
        elif kwargs['value'] == 2:
            self.label_accelerator_status.setText('Accelerator studies')
            self.label_accelerator_status.setStyleSheet('color: rgb(209,116,42)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(209,116,42)')
        elif kwargs['value'] == 3:
            self.label_accelerator_status.setText('Beam has dumped')
            self.label_accelerator_status.setStyleSheet('color: rgb(237,30,30)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(237,30,30)')
        elif kwargs['value'] == 4:
            self.label_accelerator_status.setText('Maintenance')
            self.label_accelerator_status.setStyleSheet('color: rgb(209,116,42)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(200,149,251)')
        elif kwargs['value'] == 5:
            self.label_accelerator_status.setText('Shutdown')
            self.label_accelerator_status.setStyleSheet('color: rgb(190,190,190)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(190,190,190)')
        elif kwargs['value'] == 6:
            self.label_accelerator_status.setText('Unscheduled ops')
            self.label_accelerator_status.setStyleSheet('color: rgb(19,139,67)')
            self.label_accelerator_status_indicator.setStyleSheet('background-color: rgb(0,177,0)')


    def set_i0_gain(self):
        self.ic_amplifiers['i0_amp'].set_gain(int(self.comboBox_set_i0_gain.currentText()),0)

    def set_it_gain(self):
        self.ic_amplifiers['it_amp'].set_gain(int(self.comboBox_set_it_gain.currentText()),0)

    def set_ir_gain(self):
        self.ic_amplifiers['ir_amp'].set_gain(int(self.comboBox_set_ir_gain.currentText()),0)

    def set_if_gain(self):
        self.ic_amplifiers['iff_amp'].set_gain(int(self.comboBox_set_if_gain.currentText()), 0)

    def set_energy(self):
        energy = self.hhm.energy.read()['hhm_energy']['value']
        dlg = SetEnergy.SetEnergy(round(energy), parent=self)
        if dlg.exec_():
            try:
                new_energy = float(dlg.getValues())
                print(new_energy)
            except Exception as exc:
                message_box('Incorrect energy','Energy should be numerical')

            if (new_energy > 4700) and (new_energy < 32000):
                self.plan_processor.add_plan_and_run_if_idle('move_mono_energy', {'energy' : new_energy})
                # self.plan_processor.add_execute_pause_plan_at_head('move_mono_energy', {'energy': new_energy})
                # self.RE(bps.mv(self.hhm.energy, new_energy))
            else:
                message_box('Incorrect energy','Energy should be within 4700-32000 eV range')

    def set_emission_energy(self):
        energy = np.round(self.motor_emission.energy.position, 2)
        limits = self.motor_emission.energy.limits
        dlg = SetEnergy.SetEnergy(energy, parent=self)
        if dlg.exec_():
            try:
                new_energy = float(dlg.getValues())
                print(new_energy)
            except Exception as exc:
                message_box('Incorrect energy', 'Energy should be numerical')

            if (new_energy > 4700) and (new_energy < 32000):
                self.plan_processor.add_plan_and_run_if_idle('move_johann_spectrometer_energy', {'energy' : new_energy})
                # self.plan_processor.add_execute_pause_plan_at_head('move_johann_spectrometer_energy', {'energy': new_energy})
                # self.RE(bps.mv(self.hhm.energy, new_energy))
            else:
                message_box('Incorrect energy', f'Energy should be within {limits[0]}-{limits[1]} eV range')

    def tweak_pitch_pos(self):
        self.parent.widget_beamline_setup.pushEnableHHMFeedback.setChecked(False)
        self.hhm.fb_status.put(int(0))
        # self.RE(bps.mv(self.hhm.pitch, pitch+0.025))
        if not self.hhm.pitch.moving:
            pitch = self.hhm.pitch.read()['hhm_pitch']['value']
            self.hhm.pitch.move(pitch + 0.03, wait=False)

    def tweak_pitch_neg(self):
        self.parent.widget_beamline_setup.pushEnableHHMFeedback.setChecked(False)
        self.hhm.fb_status.put(int(0))
        # self.RE(bps.mv(self.hhm.pitch, pitch-0.025))
        if not self.hhm.pitch.moving:
            pitch = self.hhm.pitch.read()['hhm_pitch']['value']
            self.hhm.pitch.move(pitch - 0.03, wait=False)

    def auto_pitch(self):
        kwargs = {}
        if self.hhm_feedback.status_msg == 'empty image':
            ret = question_message_box(self, 'Warning', 'The beam appears to have drifted.\nPress YES to perform a broad pitch scan.\nPress NO if you wish to adjust the pitch manually.')
            if not ret:
                return
            kwargs = {'scan_range' : 10}
        self.plan_processor.add_plan_and_run_if_idle('quick_pitch_optimization', kwargs)


    def recover_pitch(self):
        self.parent.widget_beamline_setup.pushEnableHHMFeedback.setChecked(False)
        self.hhm.fb_status.put(int(0))
        # self.RE(bps.mv(self.hhm.pitch, pitch-0.025))
        if not self.hhm.pitch.moving:
            pitch  = self.parent.widget_beamline_setup.current_pitch_position
            print(pitch)
            self.hhm.pitch.move(pitch, wait=False)
        self.parent.widget_beamline_setup.pushEnableHHMFeedback.setChecked(True)
        self.hhm.fb_status.put(int(1))



    def adjust_gains(self):
        plan_name = 'optimize_gains'
        plan_kwargs = {'n_tries' : 3}
        self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)


    def get_offsets(self):
        plan_name = 'get_offsets'
        plan_kwargs = {'time': 2}
        self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)
        # self.RE(self.service_plan_funcs['get_offsets']())

    # def update_daq_rate(self):
    #     daq_rate = self.spinBox_daq_rate.value()
    #     # 374.94 is the nominal RF frequency
    #     divider = int(374.94/daq_rate)
    #     self.RE(bps.abs_set(self.apb.divide, divider, wait=True))
    #
    # def update_enc_rate(self):
    #     enc_rate = self.spinBox_enc_rate.value()
    #     rate_in_points = (1/(enc_rate*1e3))*1e9/10
    #
    #     rate_in_points_rounded = int(np.ceil(rate_in_points / 100.0) * 100)
    #     self.RE(bps.abs_set(self.hhm.enc.filter_dt, rate_in_points_rounded, wait=True))

        #self.RE(bps.abs_set(self.hhm.enc.filter_dt, rate_in_points, wait=True))

    def set_reference_foil(self):
        foil = self.comboBox_reference_foils.currentText()
        if foil == '--':
            foil = None
        self.plan_processor.add_plan_and_run_if_idle('set_reference_foil', {'element': foil})
        # self.RE(self.aux_plan_funcs['set_reference_foil'](foil))

    def set_autofoil(self, state):
        self.plan_processor.auto_foil_set = state

    def set_attenuator(self):
        attenuator = self.comboBox_attenuator.currentText()
        self.plan_processor.add_plan_and_run_if_idle('set_attenuator', {'thickness': attenuator})
        # self.RE(self.aux_plan_funcs['set_attenuator'](attenuator))


    def update_feedback_gui_components(self):
        self.label_host.setText(f'Host: {self.hhm_feedback.host}')
        heartbeat = self.hhm.fb_heartbeat.get()
        if heartbeat:
            self.label_heartbeat.setStyleSheet('background-color: rgb(95,249,95)')
        else:
            self.label_heartbeat.setStyleSheet('background-color: rgb(0,94,0)')



    def take_pilatus_image(self):
        self.plan_processor.add_plan_and_run_if_idle('take_pil100k_test_image_plan', {})


    def update_slits(self):
        pass
        # self.front_end.sync_slits()
        # self.label_fe_slit_top.setText('{:.2f} mm'.format(self.front_end.slit_top.get()))
        # self.label_fe_slit_bottom.setText('{:.2f} mm'.format(self.front_end.slit_bottom.get()))
        # self.label_fe_slit_inboard.setText('{:.2f} mm'.format(self.front_end.slit_inb.get()))
        # self.label_fe_slit_outboard.setText('{:.2f} mm'.format(self.front_end.slit_outb.get()))
        #
        #
        #





