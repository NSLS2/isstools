from qtpy import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/SelectNNeffPointsDialog.ui')

class SelectNNeffPointsDialog(*uic.loadUiType(ui_path)):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Select N sample points')

        self.lineEdit_repeats.setText('1')
        self.lineEdit_n_eff.setText('1')

    def getValues(self):
        repeats = int(self.lineEdit_repeats.text())
        n_eff = int(self.lineEdit_n_eff.text())
        return repeats * n_eff
