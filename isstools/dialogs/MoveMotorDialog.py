from qtpy import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/MoveMotorDialog.ui')

class MoveMotorDialog(*uic.loadUiType(ui_path)):

    def __init__(self, new_position, motor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Menu')
        self.new_position = new_position
        self.motor = motor

        self.pushButton.setText('Move {} to {:.3f}'.format(motor.name, new_position))

        self.pushButton.clicked.connect(self.move_motor)
        self.pushButton_2.clicked.connect(self.done)

    def move_motor(self):
        self.motor.move(self.new_position)
        self.done(1)
