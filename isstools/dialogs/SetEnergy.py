from PyQt5 import uic, QtGui, QtCore
from isstools.resources import resource_path

ui_path = resource_path('dialogs/SetEnergy.ui')

class SetEnergy(*uic.loadUiType(ui_path)):

    def __init__(self, offset, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Set energy')
        self.lineEdit.setText('{}'.format(offset))

    def getValues(self):
        return self.lineEdit.text()
