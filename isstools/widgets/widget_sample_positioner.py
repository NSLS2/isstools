import json
import pkg_resources
from qtpy import uic, QtCore
from isstools.elements.elements import elements_lines_dict

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_sample_positioner.ui')
from xraydb import xray_line
import bluesky.plan_stubs as bps


class UISamplePositioner(*uic.loadUiType(ui_path)):
    def __init__(self, parent=None, settings=None, RE=None, sample_positioner=None, mirror_widget=None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.settings = settings
        self.RE = RE
        self.sample_positioner = sample_positioner

        self.push_move_to_sample.clicked.connect(self.move_to_sample)

        self.mirror_widget = mirror_widget

        self.spinBox_index_stack.setValue(self.settings.value('index_stack', defaultValue=1, type=int))
        self.spinBox_index_holder.setValue(self.settings.value('index_holder', defaultValue=1, type=int))
        self.spinBox_index_sample.setValue(self.settings.value('index_sample', defaultValue=1, type=int))

        self.pushButton_detach.clicked.connect(self.detach)

        self.spinBox_index_stack.valueChanged.connect(self.mirror_value_change)
        self.spinBox_index_holder.valueChanged.connect(self.mirror_value_change)
        self.spinBox_index_sample.valueChanged.connect(self.mirror_value_change)

    def mirror_value_change(self, value):
        if self.mirror_widget is not None:
            sender_object_name = self.sender().objectName()
            object = getattr(self.mirror_widget, sender_object_name)
            object.valueChanged.disconnect(self.mirror_widget.mirror_value_change)
            object.setValue(value)
            object.valueChanged.connect(self.mirror_widget.mirror_value_change)

    def detach(self):
        self.detached_ui = UISamplePositioner(self.parent, self.settings, self.RE, self.sample_positioner, mirror_widget=self)
        self.detached_ui.show()
        self.detached_ui.pushButton_detach.setEnabled(False)
        self.mirror_widget = self.detached_ui

    def move_to_sample(self):
        self._save_sample_index_settings()
        index_stack = self.spinBox_index_stack.value()
        index_holder = self.spinBox_index_holder.value()
        index_sample = self.spinBox_index_sample.value()
        self.sample_positioner.goto_sample(index_stack, index_holder, index_sample)
        self.RE(bps.sleep(0.1))


    def _save_sample_index_settings(self):
        self.settings.setValue('index_stack', self.spinBox_index_stack.value())
        self.settings.setValue('index_holder', self.spinBox_index_holder.value())
        self.settings.setValue('index_sample', self.spinBox_index_sample.value())



# def bind_two_widgets()


