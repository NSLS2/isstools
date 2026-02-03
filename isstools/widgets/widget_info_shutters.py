from qtpy import uic, QtCore, QtWidgets
import pkg_resources


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_info_shutters.ui')


class UIInfoShutters(*uic.loadUiType(ui_path)):
    shutters_sig = QtCore.Signal()
    def __init__(self,
                 shutters=None,
                 plan_processor=None,
                 parent=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.plan_processor = plan_processor

        # self.check_beamline_readiness(self.checkBox_check_vacuum_and_shutters.isChecked())
        self.checkBox_check_vacuum_and_shutters.setChecked(self.plan_processor.beamline_readiness)
        self.checkBox_check_vacuum_and_shutters.clicked.connect(self.check_beamline_readiness)

        # Initialize Ophyd elements
        self.shutters_sig.connect(self.change_shutter_color)
        self.shutters = shutters


        self.shutters_buttons = []
        for key, item in zip(self.shutters.keys(), self.shutters.items()):
            self.shutter_layout = QtWidgets.QVBoxLayout()

            label = QtWidgets.QLabel(key)
            label.setAlignment(QtCore.Qt.AlignCenter)
            self.shutter_layout.addWidget(label)
            label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)

            button = QtWidgets.QPushButton('')
            button.setFixedSize(int(self.height() * 0.4), int(self.height() * 0.4))
            self.shutter_layout.addWidget(button)
            # button.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)

            self.horizontalLayout_shutters.addLayout(self.shutter_layout)

            self.shutters_buttons.append(button)
            button.setFixedWidth(int(button.height() * 1.2))
            QtCore.QCoreApplication.processEvents()

            if hasattr(item[1].state, 'subscribe'):
                item[1].button = button
                item[1].state.subscribe(self.update_shutter)

                def toggle_shutter_call(shutter):
                    def toggle_shutter():
                        if int(shutter.state.value):
                            shutter.open()
                        else:
                            shutter.close()

                    return toggle_shutter

                button.clicked.connect(toggle_shutter_call(item[1]))

                if item[1].state.value == 0:
                    button.setStyleSheet("background-color: lime")
                else:
                    button.setStyleSheet("background-color: red")

            elif hasattr(item[1], 'subscribe'):
                item[1].output.parent.button = button
                item[1].subscribe(self.update_shutter)

                def toggle_shutter_call(shutter):
                    def toggle_shutter():
                        if shutter.state == 'closed':
                            shutter.open()
                        else:
                            shutter.close()

                    return toggle_shutter

                if item[1].state == 'closed':
                    button.setStyleSheet("background-color: red")
                elif item[1].state == 'open':
                    button.setStyleSheet("background-color: lime")

                button.clicked.connect(toggle_shutter_call(item[1]))

        if self.horizontalLayout_shutters.count() <= 1:
            self.groupBox_shutters.setVisible(False)

    def update_shutter(self, pvname=None, value=None, char_value=None, **kwargs):
        if 'obj' in kwargs.keys():
            if hasattr(kwargs['obj'].parent, 'button'):
                self.current_button = kwargs['obj'].parent.button

                if int(value) == 0:
                    self.current_button_color = 'lime'
                elif int(value) == 1:
                    self.current_button_color = 'red'

                self.shutters_sig.emit()

    def change_shutter_color(self):
        self.current_button.setStyleSheet("background-color: " + self.current_button_color)

    def check_beamline_readiness(self, state):
        # self.plan_processor.check_valves = state
        # self.plan_processor.check_shutters = state
        self.plan_processor.beamline_readiness = state
