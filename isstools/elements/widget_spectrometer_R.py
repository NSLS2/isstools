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
from isstools.dialogs.BasicDialogs import message_box, question_message_box
ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_spectrometer_R.ui')

class UIWidgetSpectrometerR(*uic.loadUiType(ui_path)):
    def __init__(self,
                 johann_emission=None,
                 spinbox_energy=None,
                 plan_processor=None,
                 parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.johann_emission = johann_emission
        self.spinbox_energy = spinbox_energy
        self.plan_processor = plan_processor
        self.set_current_R_value()
        self.pushButton_johann_set_R.clicked.connect(self.set_R_value)

    def set_current_R_value(self):
        value = self.johann_emission.read_R()
        self.doubleSpinBox_johann_R.setValue(value)

    def read_R_value(self):
        return self.doubleSpinBox_johann_R.value()

    def set_R_value(self):
        ret = question_message_box(self, 'Moving Spectrometer Rowland circle radius',
                                   f'Moving R to  {self.read_R_value()} mm\n'
                                   'Are you sure?')
        if ret:
            plan_name = 'move_rowland_circle_R_plan'
            plan_kwargs = {'new_R': self.read_R_value(),
                           'energy': self.spinbox_energy.value()}
            # print(plan_name, plan_kwargs)
            self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)