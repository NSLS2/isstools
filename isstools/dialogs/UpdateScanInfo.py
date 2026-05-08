from qtpy import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/UpdateScanInfo.ui')

class UpdateScanInfo(*uic.loadUiType(ui_path)):

    def __init__(self, name, scan_type, trajectory, repeat, delay, scan_types,trajectories,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Update Scan Info')

        self.lineEdit_name.setText(name)


        self.comboBox_scan_type.addItems(scan_types)
        index = self.comboBox_scan_type.findText(scan_type)
        self.comboBox_scan_type.setCurrentIndex(index)

        self.comboBox_trajectory.addItems(trajectories)
        self.comboBox_trajectory.setCurrentIndex(trajectory)

        self.spinBox_repeat.setValue(repeat)
        self.spinBox_delay.setValue(delay)


    def getValues(self):
        return self.lineEdit_name.text(), \
               self.comboBox_scan_type.currentText(), \
               self.comboBox_trajectory.currentIndex(), \
               self.spinBox_repeat.value(), \
               self.spinBox_delay.value()
