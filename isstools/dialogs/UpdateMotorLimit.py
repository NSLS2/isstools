from PyQt5 import uic, QtGui, QtCore
from isstools.resources import resource_path

ui_path = resource_path('dialogs/UpdateMotorLimits.ui')

class UIUpdateMotorLimit(*uic.loadUiType(ui_path)):

    def __init__(self, offset, motor_object, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Update Motor Limit')
        self.motor_object = motor_object
        self.lineEdit_low_limit.setText(f"{self.motor_object.low_limit:3.3f}")
        self.lineEdit_high_limit.setText(f"{self.motor_object.high_limit:3.3f}")

        self.pushButton_ok.clicked.connect(self.update_motor_limit)


    def update_motor_limit(self):
        _low_limit = float(self.lineEdit_low_limit.text())
        _high_limit = float(self.lineEdit_high_limit.text())

        self.motor_object.low_limit_travel.put(_low_limit)
        self.motor_object.high_limit_travel.put(_high_limit)