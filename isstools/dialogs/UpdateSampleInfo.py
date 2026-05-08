from qtpy import uic, QtGui, QtCore
import pkg_resources

ui_path_sample = pkg_resources.resource_filename('isstools', 'dialogs/UpdateSampleInfo.ui')
ui_path_sample_point = pkg_resources.resource_filename('isstools', 'dialogs/UpdateSamplePointInfo.ui')

class UpdateSampleInfo(*uic.loadUiType(ui_path_sample)):

    def __init__(self, name, comment, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Update Sample Info')
        self.lineEdit_name.setText(name)
        self.lineEdit_comment.setText(comment)
        # self.doubleSpinBox_x.setValue(x)
        # self.doubleSpinBox_y.setValue(y)
        # self.doubleSpinBox_z.setValue(z)
        # self.doubleSpinBox_theta.setValue(theta)

    def getValues(self):
        return (self.lineEdit_name.text(),
                self.lineEdit_comment.text())
                # self.doubleSpinBox_x.value(),
                # self.doubleSpinBox_y.value(),
                # self.doubleSpinBox_z.value(),
                # self.doubleSpinBox_theta.value())


class UpdateSamplePointInfo(*uic.loadUiType(ui_path_sample_point)):

    def __init__(self, name, x=0, y=0, z=0, th=0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Update Sample Coordinates')
        self.label_sample_name.setText(f'Sample: {name}')
        self.doubleSpinBox_x.setValue(x)
        self.doubleSpinBox_y.setValue(y)
        self.doubleSpinBox_z.setValue(z)
        self.doubleSpinBox_theta.setValue(th)

    def getValues(self):
        return {'x' : self.doubleSpinBox_x.value(),
                'y' : self.doubleSpinBox_y.value(),
                'z' : self.doubleSpinBox_z.value(),
                'th' : self.doubleSpinBox_theta.value()}
