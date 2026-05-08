from qtpy import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/UpdateHHMFeedbackSettings.ui')

class UpdatePiezoDialog(*uic.loadUiType(ui_path)):

    def __init__(self, center, line, nlines, nmeasures, kp, host, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Update Feedback Settings')

        self.lineEdit_1.setText(f'{center}')
        self.lineEdit_2.setText(f'{line}')
        self.lineEdit_3.setText(f'{nlines}')
        self.lineEdit_4.setText(f'{nmeasures}')
        self.lineEdit_5.setText(f'{kp}')
        self.lineEdit_6.setText(f'{host}')

    def getValues(self):
        center = float(self.lineEdit_1.text())
        line = int(self.lineEdit_2.text())
        nlines = int(self.lineEdit_3.text())
        nmeasures = int(self.lineEdit_4.text())
        kp = float(self.lineEdit_5.text())
        host = self.lineEdit_6.text()
        return center, line, nlines, nmeasures, kp, host

