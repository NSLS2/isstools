from qtpy import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/SetEnergy.ui')

class SetEnergy(*uic.loadUiType(ui_path)):

    def __init__(self, offset, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Set energy')
        self.lineEdit.setText('{}'.format(offset))

    def getValues(self):
        return self.lineEdit.text()
