from qtpy import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/UpdateUserDialog.ui')

class UpdateUserDialog(*uic.loadUiType(ui_path)):

    def __init__(self, year, cycle, proposal, saf, pi, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Update User Info')

        self.lineEdit.setText('{}'.format(year))
        self.lineEdit_2.setText('{}'.format(cycle))
        self.lineEdit_3.setText('{}'.format(proposal))
        self.lineEdit_4.setText('{}'.format(saf))
        self.lineEdit_5.setText('{}'.format(pi))

    def getValues(self):
        return self.lineEdit.text(), self.lineEdit_2.text(), self.lineEdit_3.text(), self.lineEdit_4.text(), self.lineEdit_5.text()
