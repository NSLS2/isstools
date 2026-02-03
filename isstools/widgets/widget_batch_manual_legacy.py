import pkg_resources
from qtpy import uic, QtGui, QtCore, QtWidgets
from qtpy.Qt import Qt

from qtpy.QtWidgets import QMenu
from isstools.elements import elements
from isstools.elements.parameter_handler import parse_plan_parameters
# from xas.trajectory import trajectory_manager
from isstools.dialogs.BasicDialogs import message_box
from isstools.elements.batch_elements import *
from isstools.elements.batch_elements import (_create_batch_experiment, _create_new_sample, _create_new_scan, _clone_scan_item, _clone_sample_item)
import json
from isstools.dialogs import UpdateSampleInfo, UpdateScanInfo
from isstools.dialogs.BasicDialogs import question_message_box
import bluesky.plan_stubs as bps
from ..elements.elements import remove_special_characters
ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_batch_manual.ui')


class UIBatchManual(*uic.loadUiType(ui_path)):
    sample_list_changed_signal = QtCore.Signal()
    scan_list_changed_signal = QtCore.Signal()
    batch_list_changed_signal = QtCore.Signal()
    def __init__(self,
                 service_plan_funcs,
                 hhm,
                 trajectory_manager,
                 sample_stage = None,
                 parent_gui = None,
                 sample_positioner = None,
                 RE = None,
                 sample_manager=None,
                 scan_manager=None,
                 scan_sequence_manager=None,
                 batch_manager=None,
                 plan_processor=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.plan_funcs = {'bla' : 'bla'}
        self.service_plan_funcs = service_plan_funcs
        self.plan_funcs_names = self.plan_funcs.keys()
        self.service_plan_funcs_names = service_plan_funcs.keys()
        self.sample_stage = sample_stage
        self.RE = RE
        self.sample_manager = sample_manager
        self.scan_manager = scan_manager
        self.scan_sequence_manager = scan_sequence_manager
        self.batch_manager = batch_manager
        self.plan_processor = plan_processor
        self.batch_mode_uids = []
        self.hhm = hhm
        self.trajectory_manager = trajectory_manager
        self.sample_positioner = sample_positioner
        self.parent_gui = parent_gui

        # self.sample_manager.append_list_update_signal(self.sample_list_changed_signal)
        self.scan_sequence_manager.append_list_update_signal(self.scan_list_changed_signal)
        self.batch_manager.append_list_update_signal(self.batch_list_changed_signal)



        self.update_batch_tree()
        self.batch_list_changed_signal.connect(self.update_batch_tree)


        '''
        WIP add horizontal scrollbar
        self.treeView_batch.header().horizontalScrollBar()
        '''

        # samples
        self.update_sample_tree()
        self.parent_gui.widget_camera.sample_list_changed_signal.connect(self.update_sample_tree)
        # self.sample_list_changed_signal.connect(self.update_sample_tree)

        self.push_create_sample.clicked.connect(self.create_new_sample)

        self.push_delete_sample.clicked.connect(self.delete_sample)
        self.push_delete_all_samples.clicked.connect(self.delete_all_samples)
        self.push_save_samples.clicked.connect(self.save_samples)
        self.push_load_samples.clicked.connect(self.load_samples)
        self.push_check_all.clicked.connect(self.check_all_samples)
        self.push_uncheck_all.clicked.connect(self.uncheck_all_samples)

        self.push_import_from_autopilot.clicked.connect(self.get_sample_info_from_autopilot)
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

        # scans
        self.update_scan_defs()
        self.update_scan_tree()
        self.scan_list_changed_signal.connect(self.update_scan_tree)
        self.push_create_scan.clicked.connect(self.create_new_scan)
        self.push_delete_scan.clicked.connect(self.delete_scan)

        self.comboBox_scans.currentIndexChanged.connect(self.update_n_eff_label)

        # services
        self.push_create_service.clicked.connect(self.create_service)
        self.comboBox_service_plan.addItems(self.service_plan_funcs_names)
        self.comboBox_service_plan.currentIndexChanged.connect(self.populate_service_parameters)
        self.service_parameter_values = []
        self.service_parameter_descriptions = []
        self.populate_service_parameters()
        # batch/measurements
        self.push_create_batch_experiment.clicked.connect(self.create_batch_experiment)
        self.push_create_measurement.clicked.connect(self.create_measurement)
        self.push_batch_delete.clicked.connect(self.delete_batch_element)
        self.push_batch_info.clicked.connect(self.batch_info)

        self.parent_gui = parent_gui
        self.settings = parent_gui.settings




    def update_scan_defs(self):
        scan_defs = [scan['scan_def'] for scan in self.scan_manager.scan_list_local]
        self.comboBox_scans.clear()
        self.comboBox_scans.addItems(scan_defs)
        self.update_n_eff_label(0)
        # self.scan_sequence_manager.reset()


    '''
    General methods used more than once
    '''
    def get_sample_position(self):
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

        sender_object = QObject().sender().objectName()
        x_value = self.sample_stage.x.position
        x_widget = getattr(self, sample_position_widget_dict[sender_object]['x_widget'])
        x_widget.setValue(x_value)

        y_value = self.sample_stage.y.position
        y_widget = getattr(self,sample_position_widget_dict[sender_object]['y_widget'])
        y_widget.setValue(y_value)

        z_value = self.sample_stage.z.position
        z_widget = getattr(self, sample_position_widget_dict[sender_object]['z_widget'])
        z_widget.setValue(z_value)

        th_value = self.sample_stage.th.position
        th_widget = getattr(self, sample_position_widget_dict[sender_object]['th_widget'])
        th_widget.setValue(th_value)

    def modify_item(self):
        sender_object = QObject().sender()
        selection = sender_object.selectedIndexes()
        # sdsdfs
        if len(selection) == 1:
            index = sender_object.currentIndex()
            if sender_object == self.treeWidget_samples:
                item = sender_object.itemFromIndex(index)
        #     else:
        #         item = sender_object.model().item(index.row())
            if item.kind =='sample':
                sample_index = item.index
                sample = self.sample_manager.sample_at_index(sample_index)
                dlg = UpdateSampleInfo.UpdateSampleInfo(sample.name, sample.comment)
                if dlg.exec_():
                    new_name, new_comment = dlg.getValues()
                    self.sample_manager.update_sample_at_index(sample_index, new_name, new_comment)
                    # item.setText(f'{item.name} at X {item.x :0.2f} Y {item.y :0.2f} Z {item.z :0.2f} Th {item.th :0.2f}')
            elif item.kind =='sample_point':
                sample_index = item.parent().index
                sample_name =self.sample_manager.sample_name_at_index(sample_index)
                sample_point_index = item.index
                coordinate_dict = self.sample_manager.sample_coordinate_dict_at_index(sample_index, sample_point_index)
                dlg = UpdateSampleInfo.UpdateSamplePointInfo(sample_name, **coordinate_dict)
                if dlg.exec_():
                    new_coordinate_dict = dlg.getValues()
                    self.sample_manager.update_sample_coordinates_at_index(sample_index, sample_point_index,
                                                                           new_coordinate_dict)
        #             item.setText(f'{item.name} at X {item.x :0.2f} Y {item.y :0.2f} Z {item.z :0.2f} Th {item.th :0.2f}')
        #     elif item.item_type == 'scan':
        #         scan_types = [self.comboBox_scans.itemText(i) for i in range(self.comboBox_scans.count())]
        #         trajectories = [self.comboBox_lut.itemText(i) for i in range(self.comboBox_lut.count())]
        #
        #         dlg = UpdateScanInfo.UpdateScanInfo(str(item.name), str(item.scan_type),
        #                                         item.trajectory, item.repeat, item.delay,
        #                                         scan_types, trajectories,
        #                                         parent=self)
        #
        #         if dlg.exec_():
        #             item.name, item.scan_type, item.trajectory, item.repeat, item.delay = dlg.getValues()
        #             item.setText(f'{item.scan_type} with {item.name} {item.repeat} times with {item.delay} s delay')
        # elif len(selection) > 1:
        #     message_box('Warning', 'Cannot modify multiple samples. Select one sample!')


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
                            plan_kwargs = {'motor_attr' : motor.name, 'based_on' : 'object_name', 'position' : position}
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


    ''' 
    Dealing with sample positioning and definition
    '''

    def _create_list_of_positions(self):
        tab_text = self.tabWidget_sample.tabText(self.tabWidget_sample.currentIndex())
        if tab_text == 'Grid':
            return self._create_grid_of_positions()
        elif tab_text == 'Map':
             return self._create_map_of_positions()
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
        x_mesh, y_mesh = np.meshgrid(x_array * step_size, y_array * step_size)
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
            _d = {'x' : xs[i],
                  'y' : ys[i],
                  'z' : z,
                  'th' : th }
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
            x_spacing = self.spinBox_sample_x_map_spacing.value() / np.cos(np.pi/4)
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
        positions = []#
        for i in range(npt):
            _d = {'x': xs[i],
                  'y': ys[i],
                  'z': np.interp(xs[i], [x_1, x_2], [z_1, z_2]),
                  'th': np.interp(xs[i], [x_1, x_2], [th_1, th_2])}
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

    def _make_scan_item(self, scan_str, scan_index, parent=None, force_unchecked=True, checkable=True):
        if parent is None:
            parent = self.treeWidget_scans
        return self._make_item(parent, scan_str, scan_index, kind='scan', force_unchecked=force_unchecked, checkable=checkable)

    def _make_sample_item(self, sample_str, sample_index):
        return self._make_item(self.treeWidget_samples, sample_str, sample_index, kind='sample', force_unchecked=False)

    def _make_sample_point_item(self, sample_item, point_str, point_index, is_exposed):
        point_item =  self._make_item(sample_item, point_str, point_index, kind='sample_point', force_unchecked=True)
        point_item.is_exposed = is_exposed
        if is_exposed:
            point_item.setForeground(0, QtGui.QColor('red'))


    def _make_batch_item(self, parent, item_str, index, kind=''):
        return self._make_item(parent, item_str, index, kind=kind, force_unchecked=False, checkable=False)

    def _make_batch_element_children(self, parent, element_list):
        for i, element in enumerate(element_list):
            if element['type'] == 'experiment':
                item_str = f"{element['name']} x{element['repeat']} times"
                item = self._make_batch_item(parent, item_str, i, kind='batch_experiment')
            elif element['type'] == 'sample':
                item_str = self.batch_manager.sample_str_from_element(element)
                item = self._make_batch_item(parent, item_str, i, kind='batch_sample')
            elif element['type'] == 'scan':
                item_str = self.batch_manager.scan_str_from_element(element)
                item = self._make_batch_item(parent, item_str, i, kind='batch_scan')
            elif element['type'] == 'service':
                item_str = self.batch_manager.service_str_from_element(element)
                item = self._make_batch_item(parent, item_str, i, kind='batch_service')

            if 'element_list' in element.keys():
                self._make_batch_element_children(item, element['element_list'])


    '''
    Dealing with samples
    '''


    def update_sample_tree(self):
        self.treeWidget_samples.clear()
        for i, sample in enumerate(self.sample_manager.samples):
            name = sample.name
            npts = sample.number_of_points
            npts_fresh = sample.number_of_unexposed_points
            sample_str = f"{name} ({npts_fresh}/{npts})"
            sample_item = self._make_sample_item(sample_str, i)
            # self.treeWidget_samples.addItem(sample_item)
            for j in range(npts):
                coord_dict = sample.index_coordinate_dict(j)
                point_str = ' '.join([(f"{key}={value : 0.2f}") for key,value in coord_dict.items()])
                point_str = f'{j+1:3d} - {point_str}'
                self._make_sample_point_item(sample_item, point_str, j, sample.index_exposed(j))

    def create_new_sample(self):
        sample_name = self.lineEdit_sample_name.text()
        if sample_name == '':
            message_box('Warning', 'Sample name is empty')
            return
        sample_name = remove_special_characters(sample_name)
        sample_comment = self.lineEdit_sample_comment.text()
        positions = self._create_list_of_positions()

        self.sample_manager.add_new_sample(sample_name, sample_comment, positions)

    def delete_sample(self):
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



    def delete_all_samples(self):
        self.sample_manager.reset()


    def save_samples(self):
        default_fpath = self.sample_manager.local_file_default_path
        filename = QtWidgets.QFileDialog.getSaveFileName(self, 'Save samples...', default_fpath, '*.smpl',
                                                         options=QtWidgets.QFileDialog.DontConfirmOverwrite)[0]
        # print(filename)
        if not filename.endswith('.smpl'):
            filename = filename + '.smpl'

        self.sample_manager.save_to_file(filename)

        # with open(filename, 'w') as f:
        #     f.write(json.dumps(samples))


    def load_samples(self):
        default_fpath = self.sample_manager.local_file_default_path
        filename = QtWidgets.QFileDialog.getOpenFileName(directory=default_fpath,
                                                         filter='*.smpl', parent=self)[0]
        self.sample_manager.add_samples_from_file(filename)


    @property
    def treeWidget_samples_root(self):
        return self.treeWidget_samples.invisibleRootItem()


    def _sample_item_iterator(self):
        sample_count = self.treeWidget_samples_root.childCount()
        for i in range(sample_count):
            yield self.treeWidget_samples_root.child(i)

    def _sample_point_item_iterator(self, sample_index):
        sample_item = self.treeWidget_samples_root.child(sample_index)
        for i in range(sample_item.childCount()):
            yield sample_item.child(i)

    def check_all_samples(self):
        for item in self._sample_item_iterator():
            item.setCheckState(0, 2)

    def uncheck_all_samples(self):
        for item in self._sample_item_iterator():
            item.setCheckState(0, 0)

    def get_sample_info_from_autopilot(self):
        try:
            df = self.parent_gui.widget_autopilot.sample_df
            str_to_parse = self.lineEdit_sample_name.text()
            if '_' in str_to_parse:
                try:
                    n_holder, n_sample = [int(i) for i in str_to_parse.split('_')]
                    select_holders = df['Holder ID'].apply(lambda x: int(x)).values == n_holder
                    select_sample_n = df['Sample #'].apply(lambda x: int(x)).values == n_sample
                    line_number = np.where(select_holders & select_sample_n)[0][0]
                except:
                    pass
            else:
                line_number = int(self.lineEdit_sample_name.text()) - 1  # pandas is confusing
            name = df.iloc[line_number]['Name']
            comment = df.iloc[line_number]['Composition'] + ' ' + df.iloc[line_number]['Comment']
            name = name.replace('/', '_')
            self.lineEdit_sample_name.setText(name)
            self.lineEdit_sample_comment.setText(comment)
        except:
            message_box('Error', 'Autopilot table is not defined')


    def check_selected_samples(self, checkstate=2):
        index_list = self.treeWidget_samples.selectedIndexes()
        for index in index_list:
            item = self.treeWidget_samples.itemFromIndex(index)
            item.setCheckState(0, checkstate)


    def check_n_unexposed_samples(self):
        n_to_check = int(self.label_n_eff.text().split('=')[-1])
        index_selected = self.treeWidget_samples.selectedIndexes()[0]
        item = self.treeWidget_samples.itemFromIndex(index_selected)
        if item.kind == 'sample_point':
            item = item.parent()
        n_checked = 0
        for i in range(item.childCount()):
            point = item.child(i)
            if not point.is_exposed:
                point.setCheckState(0, 2)
                n_checked += 1
            if n_checked == n_to_check:
                break


    def get_checked_sample_index_dict(self):
        index_dict = {}
        for i, sample_item in enumerate(self._sample_item_iterator()):
            sample_key = sample_item.index
            for sample_point_item in self._sample_point_item_iterator(i):
                sample_point_index = sample_point_item.index
                point_is_checked = sample_point_item.checkState(0)
                if point_is_checked:
                    if sample_key not in index_dict.keys():
                        index_dict[sample_key] = []
                    index_dict[sample_key].append(sample_point_index)
        return index_dict


    '''
    Dealing with scans
    '''

    def update_scan_tree(self):
        self.treeWidget_scans.clear()
        for i, scan in enumerate(self.scan_sequence_manager.scans):
            scan_item = self._make_scan_item(scan['name'], i, force_unchecked=True, checkable=True)
            if scan['type'] == 'scan_sequence':
                for j, scan_element in scan['scan_list']:
                    self._make_scan_item(scan_element['name'], j, parent=scan_item, force_unchecked=False, checkable=False)


    def create_new_scan(self):
        scan_idx = self.comboBox_scans.currentIndex()
        scan_local_dict = self.scan_manager.scan_list_local[scan_idx]
        name = self.comboBox_scans.currentText()
        repeat = self.spinBox_scan_repeat.value()
        delay = self.spinBox_scan_delay.value()
        scan_str = f'{name} x{repeat} times'
        if delay>0:
            scan_str += f' delay={delay} s'
        self.scan_sequence_manager.add_element({'type' : 'scan',
                                                'name' : scan_str,
                                                'repeat' : repeat,
                                                'delay' : delay,
                                                'scan_idx' : scan_idx,
                                                'scan_local_dict' : scan_local_dict})


    def delete_scan(self):
        index_dict = {}

        index_list = self.treeWidget_scans.selectedIndexes()
        for index in index_list:
            item = self.treeWidget_scans.itemFromIndex(index)
            if item.kind == 'scan':
                idx = item.index
            elif item.kind == 'scan_sequence':
                idx = (item.parent().index, item.index)
        self.scan_sequence_manager.delete_element(idx)
        # view = self.listView_scans
        # index = view.currentIndex()
        # if (view.model().rowCount()>0) and (index.row() < view.model().rowCount()):
        #     view.model().removeRows(index.row(), 1)

    @property
    def treeWidget_scans_root(self):
        return self.treeWidget_scans.invisibleRootItem()

    def _scan_item_iterator(self):
        scan_count = self.treeWidget_scans_root.childCount()
        for i in range(scan_count):
            yield self.treeWidget_scans_root.child(i)

    def get_checked_scan_index_list(self):
        index_list = []
        for scan_item in self._scan_item_iterator():
            if scan_item.checkState(0):
                index_list.append(scan_item.index)
        return index_list

    def update_n_eff_label(self, index):
        try:
            local_scan_dict = self.scan_manager.scan_list_local[index]
            scan_key = local_scan_dict['aux_parameters']['scan_key']
            if scan_key == 'johann_rixs':
                energy_grid = local_scan_dict['aux_parameters']['spectrometer']['scan_parameters']['energy_grid']
                n_eff = len(energy_grid)
            else:
                n_eff = 1
        except:
            n_eff = 1
        self.label_n_eff.setText(f'n_eff={n_eff}')

    '''
    Dealing with services
    '''

    def create_service(self):
        # parse parameters

        service_plan_name = self.comboBox_service_plan.currentText()
        service_plan_kwargs = dict()
        for i in range(len(self.service_parameter_values)):
            variable = self.service_parameter_descriptions[i].text().split('=')[0]
            if (self.service_parameter_types[i] == int) or (self.service_parameter_types[i] == float):
                service_plan_kwargs[f'{variable}'] = self.service_parameter_values[i].value()
            elif (self.service_parameter_types[i] == bool):
                service_plan_kwargs[f'{variable}'] = bool(self.service_parameter_values[i].checkState())
            elif (self.service_parameter_types[i] == str):
                service_plan_kwargs[f'{variable}'] = self.service_parameter_values[i].text()

        index_tuple_list = self.get_selected_batch_item_index_list()
        for index_tuple in index_tuple_list:
            self.batch_manager.add_service_to_element_list(index_tuple, {'type': 'service',
                                                                         'plan_name': service_plan_name,
                                                                         'plan_kwargs': service_plan_kwargs})

        #
    def populate_service_parameters(self):
        for i in range(len(self.service_parameter_values)):
            self.gridLayout_service_parameters.removeWidget(self.service_parameter_values[i])
            self.gridLayout_service_parameters.removeWidget(self.service_parameter_descriptions[i])
            self.service_parameter_values[i].deleteLater()
            self.service_parameter_descriptions[i].deleteLater()
        service_plan_func = self.service_plan_funcs[self.comboBox_service_plan.currentText()]
        if type(service_plan_func) == dict:
            service_plan_func = service_plan_func['func']

        [self.service_parameter_values, self.service_parameter_descriptions, self.service_parameter_types]\
            = parse_plan_parameters(service_plan_func)

        for i in range(len(self.service_parameter_values)):
            self.gridLayout_service_parameters.addWidget(self.service_parameter_values[i], i, 0, QtCore.Qt.AlignTop)
            self.gridLayout_service_parameters.addWidget(self.service_parameter_descriptions[i], i, 1, QtCore.Qt.AlignTop)

    '''
    Dealing with batch and measurements
    '''

    def update_batch_tree(self):
        self.treeWidget_batch.clear()
        self._make_batch_element_children(self.treeWidget_batch, self.batch_manager.experiments)

    def create_batch_experiment(self):
        experiment_name = self.lineEdit_batch_experiment_name.text()
        experiment_rep = self.spinBox_exp_rep.value()
        self.batch_manager.add_new_experiment(experiment_name, experiment_rep)

    def treeWidget_batch_root(self):
        return self.treeWidget_batch.invisibleRootItem()

    def get_selected_experiment_index(self):
        index_list = self.treeWidget_batch.selectedIndexes()

        if len(index_list) > 1:
            message_box('Warning', 'Must select only one experiment!')
            return None
        elif len(index_list) == 0:
            message_box('Warning', 'Must select at least one experiment!')
            return None

        item = self.treeWidget_batch.itemFromIndex(index_list[0])
        if item.kind == 'batch_experiment':
            return item.index
        else:
            message_box('Warning', 'Must select an experiment!')
            return None

    @property
    def measurement_priority(self):
        if self.radioButton_priority_scan.isChecked():
            return 'scan'
        elif self.radioButton_priority_sample.isChecked():
            return 'sample'
        elif self.radioButton_priority_sample_coords.isChecked():
            return 'sample_point'


    def create_measurement(self):
        experiment_index = self.get_selected_experiment_index()
        if experiment_index is None:
            # message boxes are handled upstream
            return

        sample_index_dict = self.get_checked_sample_index_dict()
        if len(sample_index_dict.keys()) == 0:
            message_box('Warning', 'Must select at least one sample point!')
            return

        scan_index_list = self.get_checked_scan_index_list()
        if len(scan_index_list) == 0:
            message_box('Warning', 'Must select at least one scan!')
            return

        priority = self.measurement_priority
        self.batch_manager.add_measurement_to_experiment(experiment_index, sample_index_dict, scan_index_list, priority=priority)


    def get_selected_batch_item_index_list(self):
        index_list = self.treeWidget_batch.selectedIndexes()
        index_tuple_list = []

        for index in index_list:
            item = self.treeWidget_batch.itemFromIndex(index_list[0])
            if item.parent() is None: # this must be experiment
                index_tuple_list.append( (item.index, ) )
            else:
                if item.parent().kind == 'batch_experiment':
                    experiment_index = item.parent().index
                    item_index = item.index
                    index_tuple_list.append((experiment_index, item_index))
                else:
                    experiment_index = item.parent().parent().index
                    element_index = item.parent().index
                    item_index = item.index
                    index_tuple_list.append((experiment_index, element_index, item_index))

        return index_tuple_list



    def delete_batch_element(self):
        index_tuple_list = self.get_selected_batch_item_index_list()
        if len(index_tuple_list) == 0:
            message_box('Warning', 'Select one element in batch list')
        elif len(index_tuple_list) > 2:
            message_box('Warning', 'Select only one element in batch list')
        self.batch_manager.delete_element(index_tuple_list[0])


    def batch_info(self):
        pass
        # if self.treeView_batch.model().rowCount():
        #     if self.treeView_batch.selectedIndexes():
        #         selected_index = self.treeView_batch.selectedIndexes()[0]
        #         item = self.model_batch.itemFromIndex(selected_index)
        #         if item.item_type == 'service':
        #             message_box(f'Batch element: {item.item_type}')



    def update_batch_traj(self):
        self.trajectories = self.trajectory_manager.read_info(silent=True)
        self.comboBox_lut.clear()
        self.comboBox_lut.addItems(
            ['{}-{}'.format(lut, self.trajectories[lut]['name']) for lut in self.trajectories if lut != '9'])


    '''
    Dealing with context menus
    '''

    def sample_context_menu(self,QPos):
        menu = QMenu()
        check_selected_samples = menu.addAction("&Check selected samples")
        uncheck_selected_samples = menu.addAction("&Uncheck selected samples")
        modify = menu.addAction("&Modify")
        move_to_sample = menu.addAction("Mo&ve to sample")
        set_as_exposed = menu.addAction("Set as exposed")
        set_as_unexposed = menu.addAction("Set as unexposed")
        check_n_unexposed_samples = menu.addAction("&Check N unexposed samples")
        parentPosition = self.treeWidget_samples.mapToGlobal(QtCore.QPoint(0, 0))
        menu.move(parentPosition+QPos)
        action = menu.exec_()
        if action == modify:
            self.modify_item()
        elif action == move_to_sample:
            self.move_to_sample()
        elif action == check_selected_samples:
            self.check_selected_samples(checkstate=2)
        elif action == uncheck_selected_samples:
            self.check_selected_samples(checkstate=0)
        elif action == set_as_exposed:
            self.set_as_exposed_selected_samples()
        elif action == set_as_unexposed:
            self.set_as_exposed_selected_samples(exposed=False)
        elif action == check_n_unexposed_samples:
            self.check_n_unexposed_samples()

    def scan_context_menu(self,QPos):
        menu = QMenu()
        modify = menu.addAction("&Modify")
        parentPosition = self.listView_scans.mapToGlobal(QtCore.QPoint(0, 0))
        menu.move(parentPosition+QPos)
        action = menu.exec_()
        if action == modify:
            self.modify_item()

    def scan_batch_menu(self,QPos):
        menu = QMenu()
        modify = menu.addAction("&Modify")
        copy = menu.addAction("&Copy")
        paste = menu.addAction("&Paste")

        parentPosition = self.treeView_batch.mapToGlobal(QtCore.QPoint(0, 0))
        menu.move(parentPosition+QPos)
        action = menu.exec_()
        if action == modify:
            self.modify_item()
        elif action == copy:
            pass
        elif action == paste:
            pass


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






