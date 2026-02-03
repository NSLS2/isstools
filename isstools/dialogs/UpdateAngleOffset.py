from qtpy import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/UpdateAngleOffset.ui')

# class UpdateAngleOffset(*uic.loadUiType(ui_path)):
#
#     def __init__(self, offset, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.setupUi(self)
#         self.setWindowTitle('Update Angle Offset')
#
#         self.lineEdit.setText('{}'.format(offset))
#
#     def getValues(self):
#         return self.lineEdit.text()



class UpdateAngleOffset(*uic.loadUiType(ui_path)):

    def __init__(self, offset, energy, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Update Angle Offset')

        self.handle_offset_fields(self.radioButton_new_val_deg.isChecked())
        self.handle_energy_fields(self.radioButton_new_energy.isChecked())

        self.radioButton_new_val_deg.toggled.connect(self.handle_offset_fields)
        self.radioButton_new_energy.toggled.connect(self.handle_energy_fields)

        self.lineEdit_offset.setText(f'{offset}')
        self.lineEdit_old_energy.setText(f'{energy}')
        self.lineEdit_new_energy.setText(f'{energy}')

    def handle_offset_fields(self, value, **kwargs):
        value = bool(value)
        self.label_offset.setEnabled(value)
        self.lineEdit_offset.setEnabled(value)
        self.label_offset_units.setEnabled(value)

    def handle_energy_fields(self, value, **kwargs):
        value = bool(value)
        self.label_old_energy.setEnabled(value)
        self.label_old_energy.setEnabled(value)
        self.lineEdit_old_energy.setEnabled(value)
        self.lineEdit_new_energy.setEnabled(value)
        self.label_old_energy_units.setEnabled(value)
        self.label_new_energy_units.setEnabled(value)

    def getValues(self):
        if self.radioButton_new_val_deg.isChecked():
            return (self.lineEdit_offset.text(),)
        elif self.radioButton_new_energy.isChecked():
            return (self.lineEdit_old_energy.text(), self.lineEdit_new_energy.text())