import re
import sys
import numpy as np
import pkg_resources
import math

from qtpy import uic, QtGui, QtCore, QtWidgets
from qtpy.QtGui import QPixmap, QCursor
from qtpy.Qt import QObject, Qt
from qtpy.QtCore import QThread, QSettings
from qtpy.QtWidgets import QMenu, QToolTip, QHBoxLayout, QWidget
from isstools.elements.widget_motors import UIWidgetMotors, UIWidgetMotorsWithSlider
from ..elements.elements import remove_special_characters
from qtpy.QtWidgets import QLabel, QPushButton, QLineEdit, QSizePolicy, QSpacerItem
import time as ttime
from datetime import datetime
from isstools.elements.qmicroscope import Microscope
from isstools.dialogs import UpdateSampleInfo
from isstools.dialogs.BasicDialogs import message_box, question_message_box

import matplotlib.path as mpltPath

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_sample_manager.ui')
coordinate_system_file = pkg_resources.resource_filename('isstools', 'icons/Coordinate system.png')



def time_now_str():
    return datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S.%f')

# def print_to_gui(msg, tag='', add_timestamp=False, ntabs=0, stdout=sys.stdout):
def print_to_gui(msg, tag='', add_timestamp=False, ntabs=0, stdout_alt=sys.stdout):
    # print('THIS IS STDOUT', stdout, stdout is xlive_gui.emitstream_out)
    try:
        stdout = xlive_gui.emitstream_out
    except NameError:
        stdout = stdout_alt

    msg = '\t'*ntabs + msg
    if add_timestamp:
        msg = f'({time_now_str()}) {msg}'
    if tag:
        msg = f'[{tag}] {msg}'

    print(msg, file=stdout, flush=True)

def print_debug(msg):
    print_to_gui(msg, tag='>> DEBUG <<', add_timestamp=True, ntabs=1)

stage_button_widget_dict = {
            'pushButton_move_right':
                {'motor_key': 'sample_stage_x',
                 'tweak_pv': 'twf'},
            'pushButton_move_left':
                {'motor_key': 'sample_stage_x',
                 'tweak_pv': 'twr'},
            'pushButton_move_up':
                {'motor_key': 'sample_stage_y',
                 'tweak_pv': 'twr'},
            'pushButton_move_down':
                {'motor_key': 'sample_stage_y',
                 'tweak_pv': 'twf'},
            'pushButton_move_downstream':
                {'motor_key': 'sample_stage_z',
                 'tweak_pv': 'twr'},
            'pushButton_move_upstream':
                {'motor_key': 'sample_stage_z',
                 'tweak_pv': 'twf'},
            'pushButton_move_clockwise':
                {'motor_key': 'sample_stage_th',
                 'tweak_pv': 'twr'},
            'pushButton_move_counterclockwise':
                {'motor_key': 'sample_stage_th',
                 'tweak_pv': 'twf'},
           }



sample_position_widget_dict = {
            'push_get_sample_position':
                {'x_widget': 'spinBox_sample_x',
                 'y_widget': 'spinBox_sample_y',
                 'z_widget': 'spinBox_sample_z',
                 'th_widget': 'spinBox_sample_th',
                 },
            'push_get_sample_position_map_start':
                {'x_widget': 'spinBox_sample_x_map_start',
                 'y_widget': 'spinBox_sample_y_map_start',
                 'z_widget': 'spinBox_sample_z_map_start',
                 'th_widget': 'spinBox_sample_th_map_start',
                 },
            'push_get_sample_position_map_end':
                {'x_widget': 'spinBox_sample_x_map_end',
                 'y_widget': 'spinBox_sample_y_map_end',
                 'z_widget': 'spinBox_sample_z_map_end',
                 'th_widget': 'spinBox_sample_th_map_end'},
        }




class UISampleManager(*uic.loadUiType(ui_path)):
    # sample_list_changed_signal = QtCore.Signal()

    def __init__(self,
                 sample_stage=None,
                 motor_dict=None,
                 camera_dict=None,
                 sample_manager=None,
                 plan_processor=None,
                 parent=None,
                 cam1_url='http://10.66.59.30:8731/FfmStream1.jpg', #8083 old ports
                 cam2_url='http://10.66.59.30:8732/FfmStream1.jpg', #8084 old ports
                 detached=False,
                 *args, **kwargs):


        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.sample_stage = sample_stage
        self.motor_dict = motor_dict
        self.camera_dict = camera_dict
        self.settings = parent.settings

        # self.model_sample_tree = QtGui.QStandardItemModel(self)

        if not detached:
            self.sample_list_changed_signal = self.parent.widget_user_manager.sample_list_changed_signal
        else:
            self.sample_list_changed_signal = self.parent.parent.widget_user_manager.sample_list_changed_signal
        self.camera1 = self.camera_dict['camera_sample1']
        self.camera2 = self.camera_dict['camera_sample2']

        self.sample_manager = sample_manager
        if not detached:
            self.sample_manager.append_list_update_signal(self.sample_list_changed_signal)
        self.plan_processor = plan_processor

        # motion controls and stages

        pixmap = QPixmap(coordinate_system_file)
        self.label_coordinate_system.setPixmap(pixmap)

        self.pushButton_move_up.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_down.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_left.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_right.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_downstream.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_upstream.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_counterclockwise.clicked.connect(self.move_sample_stage_rel)
        self.pushButton_move_clockwise.clicked.connect(self.move_sample_stage_rel)

        self.populate_motor_widget_layout()

        # sample management
        self._currently_selected_index = -1
        self.update_sample_tree()
        if not detached:
            self.sample_list_changed_signal.connect(self.update_sample_tree)

        # self.push_import_from_autopilot.clicked.connect(self.get_sample_info_from_autopilot)
        # self.push_create_sample.clicked.connect(self.create_new_sample)
        self.push_define_sample_points.clicked.connect(self.define_sample_points)

        # self.push_delete_sample.clicked.connect(self.delete_sample)
        # self.push_delete_all_samples.clicked.connect(self.delete_all_samples)

        self.push_get_sample_position.clicked.connect(self.get_sample_position)
        self.push_get_sample_position_map_start.clicked.connect(self.get_sample_position)
        self.push_get_sample_position_map_end.clicked.connect(self.get_sample_position)
        self.checkBox_auto_position.toggled.connect(self.enable_user_position_input)
        self.radioButton_sample_map_1D.toggled.connect(self.enable_map_spinboxes)
        self.radioButton_map_steps.toggled.connect(self.enable_map_spinboxes)
        self.enable_user_position_input()
        self.enable_map_spinboxes()

        self.treeWidget_samples.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeWidget_samples.customContextMenuRequested.connect(self.sample_context_menu)

        # cameras and visualization

        self.interaction_mode = 'default'
        self._sample_stage_polygon = None

        self.pushButton_visualize_sample.clicked.connect(self.visualize_sample)
        self.pushButton_visualize_beam.clicked.connect(self.visualize_beam)

        self.spinBox_image_min.valueChanged.connect(self.update_image_limits)
        self.spinBox_image_max.valueChanged.connect(self.update_image_limits)

        self.widget_camera1 = Microscope(parent = self, mark_direction=1, camera=self.camera1,
                                         fps=10, url=cam1_url)

        self.layout_sample_cam1.addWidget(self.widget_camera1)
        self.widget_camera1.acquire(True)

        self.widget_camera2 = Microscope(parent=self, mark_direction=0, camera=self.camera2,
                                         fps=10, url=cam2_url)
        self.layout_sample_cam2.addWidget(self.widget_camera2)
        self.widget_camera2.acquire(True)

        self.widget_camera1.doubleClickSignal.connect(self.handle_camera_double_click)
        self.widget_camera2.doubleClickSignal.connect(self.handle_camera_double_click)

        # self.widget_camera1.polygonDrawingSignal.connect(self.widget_camera2.calibration_polygon.append)
        # self.widget_camera2.polygonDrawingSignal.connect(self.widget_camera1.calibration_polygon.append)

        self.pushButton_calibrate_cameras.clicked.connect(self.calibrate_cameras)
        self.checkBox_show_calibration_grid.toggled.connect(self.show_calibration_grid)

        self.pushButton_draw_sample_polygon.toggled.connect(self.draw_sample_polygon)
        self.checkBox_show_samples.toggled.connect(self.show_samples)
        # self.pushButton_calibration_mode.clicked.connect(self.set_to_calibration_mode)

        # self.calibration_data = []
        # self.pushButton_register_calibration_point.clicked.connect(self.register_calibration_point)
        # self.pushButton_process_calibration.clicked.connect(self.process_calibration_data)
        if not detached:
            self.detached_ui = UISampleManager(sample_stage=self.sample_stage,
                                               motor_dict=motor_dict,
                                               camera_dict=self.camera_dict,
                                               sample_manager=self.sample_manager,
                                               plan_processor=self.plan_processor,
                                               parent=self,
                                               cam1_url='http://10.66.59.30:8731/FfmStream1.jpg', #8083 old ports
                                               cam2_url='http://10.66.59.30:8732/FfmStream1.jpg', #8082 old ports
                                               detached=True)
            self.detached_ui.setWindowTitle('Sample Manager - XLive @ISS/08-ID NSLS-II')
            self.detached_ui.push_detach_tab.setEnabled(False)
            self.sample_list_changed_signal.connect(self.detached_ui.update_sample_tree)

        self.push_detach_tab.clicked.connect(self.detach_tab)

    # widget setup

    def populate_motor_widget_layout(self):
        FIXED_WIDTH = 800

        spacer = QSpacerItem(FIXED_WIDTH, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.verticalLayout_sample_stage_motors.addSpacerItem(spacer)

        # step size line
        layout = QHBoxLayout()
        spacer = QSpacerItem(FIXED_WIDTH, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addSpacerItem(spacer)
        label = QLabel('      Step size      ')
        label.setFixedHeight(20)
        layout.addWidget(label)
        self.widget_step_size_label = QWidget()
        self.widget_step_size_label.setLayout(layout)
        self.widget_step_size_label.setFixedWidth(FIXED_WIDTH)
        self.verticalLayout_sample_stage_motors.addWidget(self.widget_step_size_label)

        # actual motor widgets
        self.sample_motor_widgets = {}
        for _motor in ['sample_stage_x', 'sample_stage_y', 'sample_stage_z', 'sample_stage_th']:
            widget = UIWidgetMotorsWithSlider(self.motor_dict[_motor], horizontal_scale=0.8,
                                              motor_description_width=125)
            widget.setFixedWidth(FIXED_WIDTH)
            widget.setFixedHeight(24)
            self.sample_motor_widgets[_motor] = widget
            self.verticalLayout_sample_stage_motors.addWidget(widget)
            # s

        # tick label line
        layout = QHBoxLayout()
        spacer = QSpacerItem(FIXED_WIDTH, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addSpacerItem(spacer)
        for label_str in ['0.1 ', ' 1  ', ' 10 ', '50']:
            label = QLabel(label_str)
            label.setFixedHeight(20)
            layout.addWidget(label)
        self.widget_tick_label = QWidget()
        self.widget_tick_label.setLayout(layout)
        self.widget_tick_label.setFixedWidth(FIXED_WIDTH)
        self.verticalLayout_sample_stage_motors.addWidget(self.widget_tick_label)

        spacer = QSpacerItem(FIXED_WIDTH, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.verticalLayout_sample_stage_motors.addSpacerItem(spacer)


    def detach_tab(self):
        self.detached_ui.show()


    # motion control methods

    def move_sample_stage_rel(self):
        sender_object = QObject().sender().objectName()
        motor_key = stage_button_widget_dict[sender_object]['motor_key']
        tweak_pv_str = stage_button_widget_dict[sender_object]['tweak_pv']
        motor_object = self.motor_dict[motor_key]['object']
        tweak_pv = getattr(motor_object, tweak_pv_str)
        tweak_pv.put(1)

    # sample/sample coordinates management methods

    def enable_user_position_input(self):
        manual_positoioning_flag = not self.checkBox_auto_position.isChecked()
        self.spinBox_sample_x.setEnabled(manual_positoioning_flag)
        self.spinBox_sample_y.setEnabled(manual_positoioning_flag)
        self.spinBox_sample_z.setEnabled(manual_positoioning_flag)
        self.spinBox_sample_th.setEnabled(manual_positoioning_flag)
        self.push_get_sample_position.setEnabled(manual_positoioning_flag)

    def enable_map_spinboxes(self):
        is_1d = self.radioButton_sample_map_1D.isChecked()
        is_steps = self.radioButton_map_steps.isChecked()

        self.spinBox_sample_x_map_steps.setEnabled(is_steps)
        self.spinBox_sample_x_map_spacing.setEnabled((not is_steps))

        self.spinBox_sample_y_map_steps.setEnabled((is_steps) and (not is_1d))
        self.spinBox_sample_y_map_spacing.setEnabled(((not is_steps) and (not is_1d)))


    ''' 
    Dealing with sample positioning and definition
    '''

    def get_sample_position(self):
        sender_object = QObject().sender().objectName()
        x_value = self.sample_stage.x.position
        x_widget = getattr(self, sample_position_widget_dict[sender_object]['x_widget'])
        x_widget.setValue(x_value)

        y_value = self.sample_stage.y.position
        y_widget = getattr(self, sample_position_widget_dict[sender_object]['y_widget'])
        y_widget.setValue(y_value)

        z_value = self.sample_stage.z.position
        z_widget = getattr(self, sample_position_widget_dict[sender_object]['z_widget'])
        z_widget.setValue(z_value)

        th_value = self.sample_stage.th.position
        th_widget = getattr(self, sample_position_widget_dict[sender_object]['th_widget'])
        th_widget.setValue(th_value)

    def _create_list_of_positions(self):
        tab_text = self.tabWidget_sample.tabText(self.tabWidget_sample.currentIndex())
        if tab_text == 'Grid':
            return self._create_grid_of_positions()
        elif tab_text == 'Map':
            return self._create_map_of_positions()
        elif tab_text == 'Draw':
            return self._create_polygon_of_positions()
        return

    def _get_stage_coordinates(self, tolerance=0.005):
        self.spinBox_sample_x.setValue(self.sample_stage.x.position)
        self.spinBox_sample_y.setValue(self.sample_stage.y.position)
        self.spinBox_sample_z.setValue(self.sample_stage.z.position)
        # print('!!!!!! WARNING TTH MOTOR WAS DISABLED IN GUI')
        self.spinBox_sample_th.setValue(self.sample_stage.th.position)

    def _create_grid_of_positions(self):
        step_size = self.spinBox_grid_spacing.value()
        n_x = self.spinBox_grid_x_points.value()
        n_y = self.spinBox_grid_y_points.value()
        x_array = np.arange(n_x, dtype=float)
        x_array -= np.median(x_array)
        y_array = np.arange(n_y, dtype=float)
        y_array -= np.median(y_array)
        x_mesh, y_mesh = np.meshgrid(x_array * step_size / np.cos(np.pi / 4), y_array * step_size)
        x_mesh = x_mesh.ravel()
        y_mesh = y_mesh.ravel()

        radius = self.spinBox_sample_radius.value()
        if radius > 0:
            r_mesh = np.sqrt(x_mesh ** 2 + y_mesh ** 2)
            x_mesh = x_mesh[r_mesh <= radius]
            y_mesh = y_mesh[r_mesh <= radius]

        if self.checkBox_auto_position.isChecked():
            self._get_stage_coordinates()

        xs = self.spinBox_sample_x.value() + x_mesh
        ys = self.spinBox_sample_y.value() + y_mesh
        z = self.spinBox_sample_z.value()
        th = self.spinBox_sample_th.value()
        npt = xs.size
        positions = []
        for i in range(npt):
            _d = {'x': xs[i],
                  'y': ys[i],
                  'z': z,
                  'th': th}
            positions.append(_d)
        return positions

    def _create_map_of_positions(self):
        x_1 = self.spinBox_sample_x_map_start.value()
        y_1 = self.spinBox_sample_y_map_start.value()
        z_1 = self.spinBox_sample_z_map_start.value()
        th_1 = self.spinBox_sample_th_map_start.value()

        x_2 = self.spinBox_sample_x_map_end.value()
        y_2 = self.spinBox_sample_y_map_end.value()
        z_2 = self.spinBox_sample_z_map_end.value()
        th_2 = self.spinBox_sample_th_map_end.value()

        if self.radioButton_map_steps.isChecked():
            n_x = self.spinBox_sample_x_map_steps.value()
            n_y = self.spinBox_sample_y_map_steps.value()
        elif self.radioButton_map_spacing.isChecked():
            x_spacing = self.spinBox_sample_x_map_spacing.value() / np.cos(np.pi / 4)
            y_spacing = self.spinBox_sample_y_map_spacing.value()
            n_x = int(np.floor(np.abs(x_1 - x_2) / x_spacing))
            n_y = int(np.floor(np.abs(y_1 - y_2) / y_spacing))

        if self.radioButton_sample_map_1D.isChecked():
            xs = np.linspace(x_1, x_2, n_x)
            ys = np.linspace(y_1, y_2, n_x)
        elif self.radioButton_sample_map_2D.isChecked():
            _x = np.linspace(x_1, x_2, n_x)
            _y = np.linspace(y_1, y_2, n_y)
            xs, ys = np.meshgrid(np.linspace(x_1, x_2, n_x),
                                 np.linspace(y_1, y_2, n_y))
            xs = xs.ravel()
            ys = ys.ravel()

        npt = xs.size
        positions = []  #
        for i in range(npt):
            _d = {'x': xs[i],
                  'y': ys[i],
                  'z': np.interp(xs[i], [x_1, x_2], [z_1, z_2]),
                  'th': np.interp(xs[i], [x_1, x_2], [th_1, th_2])}
            positions.append(_d)
        return positions

    def _get_polygon_from_cameras(self):
        if self.widget_camera1.sample_polygon.count():
            output = self.widget_camera1.sample_polygon_motor
        elif self.widget_camera2.sample_polygon.count():
            output = self.widget_camera2.sample_polygon_motor
        else:
            output = None
        return output

    def _create_polygon_of_positions(self):
        polygon = self._get_polygon_from_cameras()
        if polygon is None:
            return

        pos0_dict = self.sample_stage.positions()

        xmin = polygon[:, 0].min()
        xmax = polygon[:, 0].max()
        ymin = polygon[:, 1].min()
        ymax = polygon[:, 1].max()

        dy = float(self.spinBox_draw_spacing.value())
        dx = dy * np.sqrt(2)
        xgrid, ygrid = np.meshgrid(np.arange(xmin, xmax + dx, dx), np.arange(ymin, ymax + dy, dy))
        xgrid = xgrid.ravel()
        ygrid = ygrid.ravel()
        path = mpltPath.Path(polygon)
        is_inside_polygon = path.contains_points([(x, y) for (x, y) in zip(xgrid, ygrid)])

        xs = xgrid[is_inside_polygon] + pos0_dict['x']
        ys = ygrid[is_inside_polygon] + pos0_dict['y']
        z = pos0_dict['z']
        th = pos0_dict['th']

        npt = xs.size
        positions = []

        for i in range(npt):
            _d = {'x':  xs[i],
                  'y':  ys[i],
                  'z':  z,
                  'th': th}
            positions.append(_d)
        return positions

    '''
    Dealing with making qt items of all sorts
    '''

    def _make_item(self, parent, item_str, index, kind='', force_unchecked=False, checkable=True):
        item = QtWidgets.QTreeWidgetItem(parent)
        item.setText(0, item_str)
        item.setExpanded(True)
        if checkable:
            item.setFlags(item.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
        if force_unchecked:
            item.setCheckState(0, Qt.Unchecked)
        item.kind = kind
        item.index = index
        return item

    def _make_sample_item(self, sample_str, sample_index):
        return self._make_item(self.treeWidget_samples, sample_str, sample_index, kind='sample', force_unchecked=False, checkable=False)

    def _make_sample_point_item(self, sample_item, point_str, point_index, is_exposed):
        point_item = self._make_item(sample_item, point_str, point_index, kind='sample_point', force_unchecked=False, checkable=False)
        point_item.is_exposed = is_exposed
        if is_exposed:
            point_item.setForeground(0, QtGui.QColor('red'))
        return point_item

    '''
    Dealing with samples
    '''

    # def _get_currently_selected_sample_index(self):
    #     index_list = self.treeWidget_samples.selectedIndexes()
    #     sample_index = None
    #     if len(index_list) == 1:
    #         index = index_list[0]
    #         item = self.treeWidget_samples.itemFromIndex(index)
    #         if item.kind == 'sample':
    #             sample_index = item.index
    #         elif item.kind == 'sample_point':
    #             sample_index = item.parent().index
    #     return sample_index

    def update_sample_tree(self):
        # print_debug('updating treeWidget_samples: start')
        self.treeWidget_samples.clear()
        self.treeWidget_samples.setUpdatesEnabled(False)
        for i, sample in enumerate(self.sample_manager.samples):

            if not sample.archived:
                # print_debug(f'{i=}, {sample.name=}')
                # print_debug(f'making sample item: start')
                name = sample.name
                npts = sample.number_of_points
                npts_fresh = sample.number_of_unexposed_points
                sample_str = f"{name} ({npts_fresh}/{npts})"
                sample_item = self._make_sample_item(sample_str, i)
                # self.treeWidget_samples.addItem(sample_item)

                if (i == self._currently_selected_index) or ((i == len(self.sample_manager.samples)) and
                                                             (self._currently_selected_index == -1)):
                    sample_item.setExpanded(True)
                else:
                    sample_item.setExpanded(False)

                for j in range(npts):
                    # point_data = sample.index_point_data(j)
                    # point_idx = sample.index_position_index(j)
                    # point_str = sample.index_coordinate_str(j)
                    # point_exposed = sample.index_exposed(j)
                    # point_idx = int(point_data.name)
                    # coord_dict = {k: point_data[k] for k in ['x', 'y', 'z', 'th']}
                    # point_str = ' '.join([(f"{key}={value : 0.2f}") for key, value in coord_dict.items()])
                    # point_exposed = point_data['exposed']
                    # point_str = f'{point_idx + 1:3d} - {point_str}'
                    # print_debug(f'making sample point item: start')
                    point_str, point_exposed = sample.index_point_info_for_qt_item(j)
                    self._make_sample_point_item(sample_item, point_str, j, point_exposed)
                    # print_debug(f'making sample point item: end')
                # print_debug(f'making sample item: end')
        # print_debug('updating treeWidget_samples: end')
        self.treeWidget_samples.setUpdatesEnabled(True)



    # def create_new_sample(self):
    #     sample_name = self.lineEdit_sample_name.text()
    #     if (sample_name == '') or (sample_name.isspace()):
    #         message_box('Warning', 'Sample name is empty')
    #         return
    #     sample_name = remove_special_characters(sample_name)
    #     sample_comment = self.lineEdit_sample_comment.text()
    #     # positions = self._create_list_of_positions()
    #     self._currently_selected_index = -1
    #     self.sample_manager.add_new_sample(sample_name, sample_comment, [])


    def define_sample_points(self):
        index_list = self.treeWidget_samples.selectedIndexes()
        if len(index_list) == 1:
            index = index_list[0]
            item = self.treeWidget_samples.itemFromIndex(index)
            if item.kind == 'sample':
                sample_index = item.index
                positions = self._create_list_of_positions()
                self._currently_selected_index = sample_index
                self.sample_manager.add_points_to_sample_at_index(sample_index, positions)
                if self.interaction_mode == 'draw':
                    self.pushButton_draw_sample_polygon.setChecked(False)
        else:
            message_box('Error', 'Please select one sample')


    # def get_sample_info_from_autopilot(self):
    #     try:
    #         df = self.parent_gui.widget_autopilot.sample_df
    #         str_to_parse = self.lineEdit_sample_name.text()
    #         if '_' in str_to_parse:
    #             try:
    #                 n_holder, n_sample = [int(i) for i in str_to_parse.split('_')]
    #                 select_holders = df['Holder ID'].apply(lambda x: int(x)).values == n_holder
    #                 select_sample_n = df['Sample #'].apply(lambda x: int(x)).values == n_sample
    #                 line_number = np.where(select_holders & select_sample_n)[0][0]
    #             except:
    #                 pass
    #         else:
    #             line_number = int(self.lineEdit_sample_name.text()) - 1  # pandas is confusing
    #         name = df.iloc[line_number]['Name']
    #         comment = df.iloc[line_number]['Composition'] + ' ' + df.iloc[line_number]['Comment']
    #         name = name.replace('/', '_')
    #         self.lineEdit_sample_name.setText(name)
    #         self.lineEdit_sample_comment.setText(comment)
    #     except:
    #         message_box('Error', 'Autopilot table is not defined')
    #
    def delete_sample_points(self):
        index_dict = {}

        index_list = self.treeWidget_samples.selectedIndexes()
        for index in index_list:
            item = self.treeWidget_samples.itemFromIndex(index)
            if item.kind == 'sample':
                sample_index = item.index
                point_index_list = [item.child(i).index for i in range(item.childCount())]
            elif item.kind == 'sample_point':
                sample_index = item.parent().index
                point_index_list = [item.index]
            if sample_index in index_dict.keys():
                index_dict[sample_index].extend(point_index_list)
            else:
                index_dict[sample_index] = point_index_list
        self.sample_manager.delete_samples_with_index_dict(index_dict)
        self._currently_selected_index = -1
    #
    # def delete_all_samples(self):
    #     self.sample_manager.reset()
    #     self._currently_selected_index = -1

    '''
    Sample Context menu
    '''

    def sample_context_menu(self, QPos):
        menu = QMenu()
        modify = menu.addAction("&Modify")
        move_to_sample = menu.addAction("Mo&ve to sample")
        set_as_exposed = menu.addAction("Set as exposed")
        set_as_unexposed = menu.addAction("Set as unexposed")
        sort_by_x = menu.addAction("Sort positions by X")
        sort_by_y = menu.addAction("Sort positions by Y")
        delete_points = menu.addAction("Delete points")
        parentPosition = self.treeWidget_samples.mapToGlobal(QtCore.QPoint(0, 0))
        menu.move(parentPosition + QPos)
        action = menu.exec_()
        if action == modify:
            self.modify_item()
        elif action == move_to_sample:
            self.move_to_sample()
        elif action == set_as_exposed:
            self.set_as_exposed_selected_samples()
        elif action == set_as_unexposed:
            self.set_as_exposed_selected_samples(exposed=False)
        elif action == sort_by_x:
            self.sort_sample_positions_by(['x', 'y'])
        elif action == sort_by_y:
            self.sort_sample_positions_by(['y', 'x'])
        elif action == delete_points:
            self.delete_sample_points()

    def modify_item(self):
        sender_object = QObject().sender()
        selection = sender_object.selectedIndexes()
        if len(selection) == 1:
            index = sender_object.currentIndex()
            if sender_object == self.treeWidget_samples:
                item = sender_object.itemFromIndex(index)
            else:
                return

            if item.kind == 'sample':
                sample_index = item.index
                sample = self.sample_manager.sample_at_index(sample_index)
                dlg = UpdateSampleInfo.UpdateSampleInfo(sample.name, sample.comment)
                if dlg.exec_():
                    new_name, new_comment = dlg.getValues()
                    self.sample_manager.update_sample_at_index(sample_index, new_name, new_comment)
            elif item.kind == 'sample_point':
                sample_index = item.parent().index
                sample_name = self.sample_manager.sample_name_at_index(sample_index)
                sample_point_index = item.index
                coordinate_dict = self.sample_manager.sample_coordinate_dict_at_index(sample_index, sample_point_index)
                dlg = UpdateSampleInfo.UpdateSamplePointInfo(sample_name, **coordinate_dict)
                if dlg.exec_():
                    new_coordinate_dict = dlg.getValues()
                    self.sample_manager.update_sample_coordinates_at_index(sample_index, sample_point_index,
                                                                           new_coordinate_dict)

    def move_to_sample(self):
        sender_object = QObject().sender()
        selection = sender_object.selectedIndexes()
        if len(selection) == 1:
            index = sender_object.currentIndex()
            item = sender_object.itemFromIndex(index)
            if item.kind == 'sample_point':
                sample_index = item.parent().index
                sample_point_index = item.index
                name = self.sample_manager.sample_name_at_index(sample_index)
                coordinate_dict = self.sample_manager.sample_coordinate_dict_at_index(sample_index, sample_point_index)
                ret = question_message_box(self, 'Moving to sample',
                                           f'Moving to sample {name} at \n' +
                                           f'x = {coordinate_dict["x"]:.2f}\n' +
                                           f'y = {coordinate_dict["y"]:.2f}\n' +
                                           f'z = {coordinate_dict["z"]:.2f}\n' +
                                           f'th = {coordinate_dict["th"]:.2f}\n' +
                                           'Are you sure?')
                if ret:
                    for axis, position in coordinate_dict.items():
                        plan = 'move_motor_plan'
                        motor = getattr(self.sample_stage, axis)
                        plan_kwargs = {'motor_attr': motor.name, 'based_on': 'object_name', 'position': position}
                        self.plan_processor.add_plan_and_run_if_idle(plan, plan_kwargs)

            else:
                message_box('Warning', 'Please select sample point')
        elif len(selection) > 1:
            message_box('Warning', 'Cannot move to multiple sample positions. Select one sample!')

    def set_as_exposed_selected_samples(self, exposed=True):
        index_dict = {}

        index_list = self.treeWidget_samples.selectedIndexes()
        for index in index_list:
            item = self.treeWidget_samples.itemFromIndex(index)
            if item.kind == 'sample':
                sample_index = item.index
                point_index_list = [item.child(i).index for i in range(item.childCount())]
            elif item.kind == 'sample_point':
                sample_index = item.parent().index
                point_index_list = [item.index]
            if sample_index in index_dict.keys():
                index_dict[sample_index].extend(point_index_list)
            else:
                index_dict[sample_index] = point_index_list
        self.sample_manager.set_as_exposed_with_index_dict(index_dict, exposed=exposed)

    def sort_sample_positions_by(self, keys):
        index = self.treeWidget_samples.selectedIndexes()[0]
        item = self.treeWidget_samples.itemFromIndex(index)
        if item.kind == 'sample':
            sample_index = item.index
        elif item.kind == 'sample_point':
            sample_index = item.parent().index
        else:
            return
        self._currently_selected_index = sample_index
        self.sample_manager.sort_sample_positions_by_at_index(sample_index, keys)

    # sample visualization methods

    def visualize_beam(self):
        exposure = self.doubleSpinBox_exposure_beam.value()
        self.camera1.exp_time.set(exposure)
        self.camera2.exp_time.set(exposure)

    def visualize_sample(self):
        exposure = self.doubleSpinBox_exposure_sample.value()
        self.camera1.exp_time.set(exposure)
        self.camera2.exp_time.set(exposure)

    def update_image_limits(self):
        vmin = self.spinBox_image_min.value()
        vmax = self.spinBox_image_max.value()
        print(vmin, vmax)

    def calibrate_cameras(self):
        plan_name = 'calibrate_sample_cameras_plan'
        plan_kwargs = {}
        self.plan_processor.add_plan_and_run_if_idle(plan_name, plan_kwargs)

    def show_calibration_grid(self, state):
        if state:
            self.camera1.compute_calibration_grid_lines()
            self.camera2.compute_calibration_grid_lines()

        self.widget_camera1.draw_calibration_grid = state
        self.widget_camera2.draw_calibration_grid = state

    def show_samples(self, state):
        self.widget_camera1.draw_sample_points = state
        self.widget_camera2.draw_sample_points = state

    def handle_camera_double_click(self, input_list):
        if self.interaction_mode == 'default':
            motx, moty = input_list
            self.sample_stage.mvr({'x': motx, 'y': moty})


    def draw_sample_polygon(self, state):
        if state:
            self.interaction_mode = 'draw'
        else:
            self.interaction_mode = 'default'
            # commented out for testing
            self.widget_camera1.reset_sample_polygon()
            self.widget_camera2.reset_sample_polygon()

    @property
    def sample_manager_xy_coords(self):
        index_list = self.treeWidget_samples.selectedIndexes()
        if len(index_list) == 1:
            index = index_list[0]
            item = self.treeWidget_samples.itemFromIndex(index)
            if item.kind == 'sample':
                sample_index = item.index
            elif item.kind == 'sample_point':
                sample_index = item.parent().index
            else:
                return
            sample = self.sample_manager.sample_at_index(sample_index)
            motx = self.sample_stage.x.position - sample.position_data['x'].values
            moty = self.sample_stage.y.position - sample.position_data['y'].values
            if motx.size == 0:
                return
            return motx, moty



