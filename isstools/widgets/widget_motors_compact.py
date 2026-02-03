import pkg_resources
from qtpy import uic, QtWidgets
from qtpy.QtCore import QThread, QSettings
from qtpy.QtCore import  QObject
from bluesky.callbacks import LivePlot
from bluesky.callbacks.mpl_plotting import LiveScatter
import bluesky.plan_stubs as bps
import bluesky.plans as bp
import numpy as np
from functools import partial
from qtpy.QtWidgets import QLabel, QPushButton, QLineEdit
from qtpy.QtCore import Qt

# from isstools.dialogs import MoveMotorDialog
# from isstools.dialogs.BasicDialogs import question_message_box
# from isstools.elements.figure_update import update_figure_with_colorbar, update_figure, setup_figure
# from isstools.elements.transformations import  range_step_2_start_stop_nsteps
# from isstools.widgets import widget_johann_tools
# from xas.spectrometer import analyze_elastic_scan
# from ..elements.liveplots import XASPlot, NormPlot#, XASPlotX
# from ..elements.elements import get_spectrometer_line_dict
# from isstools.widgets import widget_emission_energy_selector
#
# from isstools.dialogs.UpdateMotorLimit import UIUpdateMotorLimit
#

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_motor_widget_compact.ui')



class UIWidgetMotorsCompact(*uic.loadUiType(ui_path)):
    def __init__(self,
                 this_motor_dictionary=None, # "this" is to emphasize that the dict is for a specific motor!
                 parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.setWindowFlag(Qt.FramelessWindowHint)

        self.motor_dict = this_motor_dictionary
        self._motor_object = self.motor_dict['object']

        # self.label_motor_description = self.label_status
        #
        # self.layout_motor_widget = self.horizontalLayout_motor
        # self.label_motor_description.setText(self.motor_dict['description'])
        # self.layout_motor_widget.addWidget(self.label_motor_description)

        self.label_mov_status = self.label_status
        self.label_mov_status.setStyleSheet('background-color: rgb(55,130,60)')
        self._motor_object.motor_is_moving.subscribe(self.update_moving_label)

        self.button_move_decrement = self.pushButton_decrease
        self.button_move_decrement.clicked.connect(self.update_decrement)

        self.lineEdit_step = self.lineEdit_step
        self.lineEdit_step.setText(str(1.0) + " " + self._motor_object.egu)
        self.lineEdit_step.returnPressed.connect(self.update_step)

        self.button_move_increment = self.pushButton_increase
        self.button_move_increment.clicked.connect(self.update_increment)


    def update_moving_label(self, value, **kwargs):
        if value == 1:
            self.label_mov_status.setStyleSheet('background-color: rgb(95,249,95)')
        else:
            self.label_mov_status.setStyleSheet('background-color: rgb(55,130,60)')

    def update_decrement(self):
        _current_step_reading = self.lineEdit_step.text()
        _step = float(_current_step_reading.split()[0])

        _current_readback = self._motor_object.position
        _set_obj = self._motor_object.set(_current_readback - _step)

    def update_step(self):
        _user_step_reading = self.lineEdit_step.text()
        _step_convert = float(_user_step_reading.split()[0])
        _step_text = f"{_step_convert:1.1f} {self._motor_object.egu}"
        self.lineEdit_step.setText(_step_text)

    def update_increment(self):
        _current_step_reading = self.lineEdit_step.text()
        _step = float(_current_step_reading.split()[0])

        _current_readback = self._motor_object.position
        _set_obj = self._motor_object.set(_current_readback + _step)