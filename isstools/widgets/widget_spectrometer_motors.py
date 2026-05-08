import pkg_resources
from qtpy import uic, QtCore
from qtpy.QtGui import QPixmap
from isstools.elements.widget_motors import UIWidgetMotors
from isstools.elements.widget_spectrometer_R import UIWidgetSpectrometerR
from isstools.dialogs.BasicDialogs import message_box, question_message_box

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_spectrometer_motors.ui')
spectrometer_image1 = pkg_resources.resource_filename('isstools', 'Resources/spec_image1.png')
spectrometer_image2 = pkg_resources.resource_filename('isstools', 'Resources/spec_image2.png')

class UISpectrometerMotors(*uic.loadUiType(ui_path)):
    def __init__(self,
                motor_dict = None,
                parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.motor_dict=motor_dict
        pixmap = QPixmap(spectrometer_image1)
        pixmap = pixmap.scaled(1000, 700, QtCore.Qt.KeepAspectRatio)
        self.label_spectrometer_image_1.setPixmap(pixmap)

        pixmap = QPixmap(spectrometer_image2)
        pixmap = pixmap.scaled(900, 400, QtCore.Qt.KeepAspectRatio)
        self.label_spectrometer_image_2.setPixmap(pixmap)
        self.widget_list=[]

        self._motor_group_dict = {
            'pushButton_detector_arm':  ['motor_det_x', 'motor_det_th1', 'motor_det_th2'],
            'pushButton_crystal_assembly': ['auxxy_x', 'auxxy_y'],
            'pushButton_stack1': ['johann_cr_main_roll', 'johann_cr_main_yaw'],
            'pushButton_stack2': ['johann_cr_aux2_roll', 'johann_cr_aux2_yaw', 'johann_cr_aux2_x', 'johann_cr_aux2_y'],
            'pushButton_stack3': ['johann_cr_aux3_roll', 'johann_cr_aux3_yaw', 'johann_cr_aux3_x', 'johann_cr_aux3_y'],
            'pushButton_stack4': ['johann_cr_aux4_roll', 'johann_cr_aux4_yaw', 'johann_cr_aux4_x', 'johann_cr_aux4_y'],
            'pushButton_stack5': ['johann_cr_aux5_roll', 'johann_cr_aux5_yaw', 'johann_cr_aux5_x', 'johann_cr_aux5_y'],
            }
        for button in self._motor_group_dict.keys():
            getattr(self,button).clicked.connect(self.show_motors)

        self.johann_emission = self.parent.johann_emission
        self.plan_processor = self.parent.plan_processor

        self.update_doubleSpinBox_johann_R()
        self.update_doubleSpinBox_johann_nominal_energy()

        self.pushButton_set_johann_R.clicked.connect(self.set_R_value)



    def show_motors(self):
        sender_object_name = self.sender().objectName()
        for widget in self.widget_list:
            self.verticalLayout_currentMotors.removeWidget(widget)
            widget.deleteLater()
        self.widget_list=[]

        for motor in self._motor_group_dict[sender_object_name]:
            widget = UIWidgetMotors(self.motor_dict[motor], motor_description_width=500, horizontal_scale=1.0)
            widget.setFixedWidth(900)
            widget.setFixedHeight(24)
            self.verticalLayout_currentMotors.addWidget(widget)
            self.widget_list.append(widget)

    def update_doubleSpinBox_johann_R(self):
        value = self.johann_emission.read_R()
        self.doubleSpinBox_johann_R.setValue(value)

    def update_doubleSpinBox_johann_nominal_energy(self):
        value = self.johann_emission.energy.position
        self.doubleSpinBox_johann_nominal_energy.setValue(value)

    def read_R_value(self):
        return self.doubleSpinBox_johann_R.value()

    def set_R_value(self):
        new_R_value = self.read_R_value()
        ret = question_message_box(self, 'Moving Spectrometer Rowland circle radius',
                                   f'Moving R to  {new_R_value} mm\n'
                                   'Are you sure?')
        if ret:
            plan_name = 'move_rowland_circle_R_plan'
            plan_kwargs = {'new_R': new_R_value,
                           'energy': self.doubleSpinBox_johann_nominal_energy.value()}
            # print(plan_name, plan_kwargs)
            self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)

    #
    #
    # def launch_stack_motors_widget(self, stack_number=1):
    #     _stack_motors = {1: ['johann_cr_main_roll', 'johann_cr_main_yaw'],
    #                      2: ['johann_cr_aux2_roll', 'johann_cr_aux2_yaw', 'johann_cr_aux2_x', 'johann_cr_aux2_y'],
    #                      3: ['johann_cr_aux3_roll', 'johann_cr_aux3_yaw', 'johann_cr_aux3_x', 'johann_cr_aux3_y']}
    #
    #
    #     self.widget_stack_motors.setWindowTitle(f"Stack {stack_number} Motors")
    #     self.layout_stack = QtWidgets.QVBoxLayout(self.widget_stack_motors)
    #
    #
    #     for motor_name in _stack_motors[stack_number]:
    #         widget = UIWidgetMotors(self.motor_dictonary[motor_name])
    #         widget.setFixedWidth(800)
    #         self.layout_stack.addWidget(widget)
    #     self.widget_stack_motors.show()
    #     # self.motor_list.append(self.widget_stack_motors)
    #
    # def launch_det_arm_motor_widget(self):
    #     _det_arm_motors = ['motor_det_x', 'motor_det_th1', 'motor_det_th2']
    #
    #     self.widget_det_motors = QtWidgets.QWidget()
    #     self.widget_det_motors.setGeometry(1100, 1100, 900, 140)
    #     self.widget_det_motors.setWindowTitle(f"Detector arm Motors")
    #     self.layout_det = QtWidgets.QVBoxLayout(self.widget_det_motors)
    #
    #
    #     for motor_name in _det_arm_motors:
    #         widget = UIWidgetMotors(self.motor_dictonary[motor_name])
    #         widget.setFixedWidth(800)
    #         self.layout_det.addWidget(widget)
    #     self.motor_list.append(self.widget_det_motors)
    #     self.widget_det_motors.show()
    #
    #
    # def launch_cry_assy_widget(self):
    #     _cry_assy_motors = ['auxxy_x', 'auxxy_y']
    #     # ['johann_bragg_angle', 'johann_energy']
    #
    #     self.widget_cry_assy_motors = QtWidgets.QWidget()
    #     self.widget_cry_assy_motors.setGeometry(1200, 1200, 900, 140)
    #     self.widget_cry_assy_motors.setWindowTitle(f"Detector arm Motors")
    #     self.layout_cry_assy = QtWidgets.QVBoxLayout(self.widget_cry_assy_motors)
    #
    #     for motor_name in _cry_assy_motors:
    #         widget = UIWidgetMotors(self.motor_dictonary[motor_name])
    #         widget.setFixedWidth(800)
    #         self.layout_cry_assy.addWidget(widget)
    #
    #     self.motor_list.append(self.widget_cry_assy_motors)
    #     self.widget_cry_assy_motors.show()
    #
    #
