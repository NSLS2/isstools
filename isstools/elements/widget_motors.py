import pkg_resources
from qtpy import uic, QtWidgets
from qtpy.QtCore import QThread, QSettings, Qt
from qtpy.QtGui import QPixmap, QCursor
from qtpy.QtCore import  QObject
from bluesky.callbacks import LivePlot
from bluesky.callbacks.mpl_plotting import LiveScatter
import bluesky.plan_stubs as bps
import bluesky.plans as bp
import numpy as np
from functools import partial
from qtpy.QtWidgets import QLabel, QPushButton, QLineEdit, QSizePolicy, QSpacerItem, QSlider, QToolTip

# from isstools.dialogs import MoveMotorDialog
# from isstools.dialogs.BasicDialogs import question_message_box
# from isstools.elements.figure_update import update_figure_with_colorbar, update_figure, setup_figure
# from isstools.elements.transformations import  range_step_2_start_stop_nsteps
# from isstools.widgets import widget_johann_tools
# from xas.spectrometer import analyze_elastic_scan
# from ..elements.liveplots import XASPlot, NormPlot#, XASPlotX
# from ..elements.elements import get_spectrometer_line_dict
# from isstools.widgets import widget_emission_energy_selector

from isstools.dialogs.UpdateMotorLimit import UIUpdateMotorLimit
#

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_motor_widget.ui')

def try_to_update_gui_decorator(method):
    def wrapper(obj, *args, **kwargs):
        try:
            return method(obj, *args, **kwargs)
        except:
            print('Failed to updated GUI element.')
            return None
    return wrapper

class UIWidgetMotors(*uic.loadUiType(ui_path)):
    def __init__(self,
                 this_motor_dictionary=None, # "this" is to emphasize that the dict is for a specific motor!
                 parent=None,
                 horizontal_scale=1,
                 motor_description_width=300,
                 add_spacer=True,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.width = int((800 - 200 + motor_description_width) * horizontal_scale)

        self.motor_dict = this_motor_dictionary
        self._motor_object = self.motor_dict['object']

        self.label_motor_description = QLabel("")

        self.layout_motor_widget = self.horizontalLayout_motor
        self.label_motor_description.setText(self.motor_dict['keyword'])
        self.label_motor_description.setFixedWidth(int(motor_description_width * horizontal_scale))
        # self.label_motor_description.setAlignment(Qt.AlignCenter)
        self.layout_motor_widget.addWidget(self.label_motor_description)

        self.label_mov_status = QLabel("      ")
        self.label_mov_status.setFixedWidth(int(23))
        self.label_mov_status.setStyleSheet('background-color: rgb(55,130,60)')
        self.layout_motor_widget.addWidget(self.label_mov_status)

        self.lineEdit_setpoint = QLineEdit("")
        _user_setpoint = f"{self._motor_object.user_setpoint.get():3.3f} { self._motor_object.egu}"
        self.lineEdit_setpoint.setText(_user_setpoint)
        self.lineEdit_setpoint.setFixedWidth(int(100 * horizontal_scale))
        self.lineEdit_setpoint.setAlignment(Qt.AlignCenter)
        self.layout_motor_widget.addWidget(self.lineEdit_setpoint)
        self.lineEdit_setpoint.returnPressed.connect(self.update_set_point)
        self._motor_object.user_setpoint.subscribe(self.update_set_point_value)

        self.label_low_limit = QLabel("      ")
        self.label_low_limit.setFixedWidth(int(23))
        self.label_low_limit.setStyleSheet('background-color: rgb(94,20,20)')
        self._motor_object.low_limit_switch.subscribe(self.update_motor_llim_status)
        self.layout_motor_widget.addWidget(self.label_low_limit)

        self.label_motor_readback = QLabel("")
        self.label_motor_readback.setFixedWidth(int(100 * horizontal_scale))
        self.label_motor_readback.setAlignment(Qt.AlignCenter)
        self._motor_object.user_readback.subscribe(self.update_readback)
        self._motor_object.motor_is_moving.subscribe(self.update_moving_label)
        self.layout_motor_widget.addWidget(self.label_motor_readback)

        self.label_high_limit = QLabel("      ")
        self.label_high_limit.setStyleSheet('background-color: rgb(94,20,20)')
        self.label_high_limit.setFixedWidth(int(23))
        self._motor_object.high_limit_switch.subscribe(self.update_motor_hlim_status)
        self.layout_motor_widget.addWidget(self.label_high_limit)

        self.button_move_decrement = QPushButton("<")
        self.button_move_decrement.setFixedWidth(int(30 * horizontal_scale))
        self.layout_motor_widget.addWidget(self.button_move_decrement)
        self.button_move_decrement.clicked.connect(self.update_decrement)

        self.lineEdit_step = QLineEdit("")
        self.lineEdit_step.setFixedWidth(int(100 * horizontal_scale))
        # self.lineEdit_step.setText(str(1.00) + " " + self._motor_object.egu)
        self._motor_object.twv.subscribe(self.update_step_value)
        self.layout_motor_widget.addWidget(self.lineEdit_step)
        self.lineEdit_step.returnPressed.connect(self.update_step)
        # self._motor_object.tweak_value.subscribe(self.update_step_value)

        self.button_move_increment = QPushButton(">")
        self.button_move_increment.setFixedWidth(int(30 * horizontal_scale))
        self.layout_motor_widget.addWidget(self.button_move_increment)
        self.button_move_increment.clicked.connect(self.update_increment)

        self.button_stop_motor = QPushButton("Stop")
        self.button_stop_motor.setFixedWidth(int(80 * horizontal_scale))
        self.layout_motor_widget.addWidget(self.button_stop_motor)
        self.button_stop_motor.clicked.connect(self.stop_the_motor)

        self.button_change_limts = QPushButton("Change limit")
        self.button_change_limts.setFixedWidth(int(125 * horizontal_scale))
        self.layout_motor_widget.addWidget(self.button_change_limts)
        self.button_change_limts.clicked.connect(self.update_lo_hi_limit)

        if add_spacer:
            self.spacer = QSpacerItem(100, 24, QSizePolicy.Minimum, QSizePolicy.Expanding)
            self.layout_motor_widget.addSpacerItem(self.spacer)

    @try_to_update_gui_decorator
    def update_moving_label(self, value, **kwargs):
        if value == 1:
            self.label_mov_status.setStyleSheet('background-color: rgb(95,249,95)')
        else:
            self.label_mov_status.setStyleSheet('background-color: rgb(55,130,60)')

    def update_set_point(self):
        _read_desired_setpoint = self.lineEdit_setpoint.text()
        _desired_setpoint = float(_read_desired_setpoint.split()[0])
        _set_obj = self._motor_object.set(_desired_setpoint)

    def update_set_point_value(self, value, **kwargs):
        self.lineEdit_setpoint.setText(f"{value:3.3f} {self._motor_object.egu}")


    # def update_step_value(self, value, **kwargs):
    #     self.lineEdit_step.setText(f"{value:3.3f} {self._motor_object.egu}")

    def update_readback(self, value, **kwargs):
        self.label_motor_readback.setText(f"{value:3.3f} {self._motor_object.egu}")

    @try_to_update_gui_decorator
    def update_motor_hlim_status(self, value, **kwargs):
        if value == 1:
            self.label_high_limit.setStyleSheet('background-color: rgb(255,0,0)')
        else:
            self.label_high_limit.setStyleSheet('background-color: rgb(94,20,20)')

    @try_to_update_gui_decorator
    def update_motor_llim_status(self, value, **kwargs):
        if value == 1:
            self.label_low_limit.setStyleSheet('background-color: rgb(255,0,0)')
        else:
            self.label_low_limit.setStyleSheet('background-color: rgb(94,20,20)')

    def update_decrement(self):
        self._motor_object.twr.put(1)
        # _current_step_reading = self.lineEdit_step.text()
        # _step = float(_current_step_reading.split()[0])
        #
        # _current_readback = self._motor_object.position
        # _set_obj = self._motor_object.set(_current_readback - _step)

    def update_step_value(self, value, **kwargs):
        self.lineEdit_step.setText(f'{value:.3f} {self._motor_object.egu}')

    def update_step(self):
        _user_step_reading = self.lineEdit_step.text()
        _step_convert = float(_user_step_reading.split()[0])
        _step_text = f"{_step_convert:3.3f} {self._motor_object.egu}"
        self.lineEdit_step.setText(_step_text)
        self._motor_object.twv.set(_step_convert)

    def update_increment(self):
        self._motor_object.twf.put(1)
        # _current_step_reading = self.lineEdit_step.text()
        # _step = float(_current_step_reading.split()[0])
        # _current_readback = self._motor_object.position
        # _set_obj = self._motor_object.set(_current_readback + _step)

    def stop_the_motor(self):
        self._motor_object.stop()

    def update_lo_hi_limit(self):
        dlg = UIUpdateMotorLimit("", self._motor_object, parent=self)

        if dlg.exec_():
            pass


class UIWidgetMotorsWithSlider(UIWidgetMotors):

    def __init__(self, *args, ticks=[0.1, 1, 10, 50], **kwargs):
        kwargs['add_spacer'] = False
        super().__init__(*args, **kwargs)


        self.ticks = np.array([i for i in ticks])
        self.compute_slider_grid()

        self.slider = QSlider(1) # horizontal
        self.slider.setMinimum(0)
        self.slider.setMaximum(99)
        self.slider.setSingleStep(1)
        self.slider.setTickInterval(33)
        self.slider.setTickPosition(3)

        self._update_slider(self._motor_object.twv.get())
        self._motor_object.twv.subscribe(self.update_slider)
        self.slider.valueChanged.connect(self.update_step_from_slider)

        self.layout_motor_widget.addWidget(self.slider)

        # self.spacer = QSpacerItem(100, 24, QSizePolicy.Minimum, QSizePolicy.Expanding)
        # self.layout_motor_widget.addSpacerItem(self.spacer)

    def compute_slider_grid(self):
        ticks_log = np.log10(self.ticks)
        slide_tick_spacing = int(99 / (self.ticks.size - 1))

        ranges = []
        for i in range(self.ticks.size - 1):
            _r = 10 ** np.linspace(ticks_log[i], ticks_log[i + 1], slide_tick_spacing + 1)
            ranges.append(_r)

        self.slider_grid = np.round(np.unique(np.hstack((ranges))), 2)

    def step_to_slider_units(self, value):
        return np.argmin(np.abs(value - self.slider_grid))

    def update_slider(self, value, old_value, atol=5e-3, **kwargs):
        if not np.isclose(value, old_value, atol=atol):
            self._update_slider(value)

    def _update_slider(self, value):
        slider_units = self.step_to_slider_units(value)
        self.slider.setValue(slider_units)

    def update_step_from_slider(self, idx):
        slider_value = self.slider.value()
        step_value = self.slider_grid[slider_value]
        self.slider.valueChanged.disconnect(self.update_step_from_slider)
        self._motor_object.twv.put(step_value)
        self.slider.valueChanged.connect(self.update_step_from_slider)
        QToolTip.showText(QCursor.pos(), f'{step_value}', self)

