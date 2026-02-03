from qtpy import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/GetEmailAddress.ui')

class GetEmailAddress(*uic.loadUiType(ui_path)):

    def __init__(self, offset, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Email address')
        self.lineEdit.setText('{}'.format(offset))

    def getValue(self):
        return self.lineEdit.text()
