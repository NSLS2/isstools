import datetime
from timeit import default_timer as timer

import numpy as np
import pkg_resources
from qtpy import uic, QtCore
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from xas.xray import generate_energy_grid

from isstools.dialogs.BasicDialogs import question_message_box, message_box
from isstools.elements.figure_update import update_figure, setup_figure

from bluesky.callbacks import LivePlot

from ..elements.liveplots import XASPlot#, XASPlotX
from ..elements.elements import remove_special_characters

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_run.ui')



class UIRun(*uic.loadUiType(ui_path)):
    # plansAdded = QtCore.Signal()

    def __init__(self,
                 scan_manager = None,
                 sample_manager=None,
                 plan_processor=None,
                 sample_env_dict=None,
                 hhm=None,
                 johann_spectrometer_motor=None,
                 parent=None,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.scan_manager = scan_manager
        self.sample_manager = sample_manager
        self.plan_processor = plan_processor
        self.sample_env_dict = sample_env_dict
        self.hhm = hhm
        self.johann_spectrometer_motor = johann_spectrometer_motor
        self.push_run_scan.clicked.connect(self.run_scan)
        self.push_run_test_scan.clicked.connect(self.run_test_scan)
        self.push_queue_scan.clicked.connect(self.queue_scan)
        self.plan_processor.status_update_signal.connect(self.handle_execution_buttons)
        self.update_scan_defs()
        self.update_sample_defs()
        # self.update_conditions()

        self.figure, self.canvas, self.toolbar = setup_figure(self, self.layout_plot)
        self.figure.ax1 = self.figure.ax
        self.figure.ax2 = self.figure.ax1.twinx()
        self.figure.ax3 = self.figure.ax1.twinx()

        # Move ax1 to the left
        self.figure.ax1.spines['left'].set_position(('axes', 0))
        self.figure.ax1.spines['right'].set_visible(False)
        self.figure.ax1.yaxis.set_label_position("left")
        self.figure.ax1.yaxis.tick_left()

        # Move ax2 to the left further out
        self.figure.ax2.spines['left'].set_position(('axes', -0.05))
        self.figure.ax2.spines['right'].set_visible(False)
        self.figure.ax2.yaxis.set_label_position("left")
        self.figure.ax2.yaxis.tick_left()

        # Move ax3 even further left
        self.figure.ax3.spines['left'].set_position(('axes', -0.10))
        self.figure.ax3.spines['right'].set_visible(False)
        self.figure.ax3.yaxis.set_label_position("left")
        self.figure.ax3.yaxis.tick_left()

    def update_scan_defs(self):
        self.comboBox_scan_defs.clear()
        for scan in self.scan_manager.scan_list_local:
            if not scan['archived']:
                scan_defs = scan['scan_def']
                self.comboBox_scan_defs.addItem(scan_defs)




    def update_sample_defs(self):
        self.comboBox_sample_defs.clear()
        for s in self.sample_manager.samples:
            if not s.archived:
                self.comboBox_sample_defs.addItem(s.name)

    # def update_conditions(self):
    #     cond_tuples = [(k, v['shortcut']) for k, v in self.sample_env_dict.items()]
    #     conds_keys = [i[0] for i in cond_tuples]
    #     conds_shortcuts = [i[1] for i in cond_tuples]
    #     self.comboBox_condition.clear()
    #     self.comboBox_condition.addItems(conds_shortcuts)

    def make_plans(self):
        sample_idx = self.comboBox_sample_defs.currentIndex()
        scan_idx = self.comboBox_scan_defs.currentIndex()
        sample_condition = self.lineEdit_condition.text()
        sample_condition = remove_special_characters(sample_condition)
        # name = self.lineEdit_exp_name.text()

        sample_name = self.sample_manager.sample_name_at_index(sample_idx)
        sample_comment = self.sample_manager.sample_comment_at_index(sample_idx)
        sample_uid = self.sample_manager.sample_uid_at_index(sample_idx)
        metadata = {'sample_uid' : sample_uid, 'sample_name' : sample_name, 'sample_comment' : sample_comment,
                    'sample_condition': sample_condition}

        if (sample_condition == '') or (sample_condition.isspace()):
            name = sample_name
        else:
            name = f'{sample_name} {sample_condition}'

        # name = remove_special_characters(name)
        comment = self.lineEdit_exp_comment.text()
        repeat = self.spinBox_scan_repeat.value()
        delay = self.spinBox_scan_delay.value()
        return self.scan_manager.generate_plan_list(name, comment, repeat, delay, scan_idx, metadata=metadata)
        # if name:
        #
        # else:
        #     message_box('Error', 'Please provide the name for the sample')

    def _queue_scan(self, add_at='tail'):
        plans = self.make_plans()
        if plans:
            self.plan_processor.add_plans(plans, add_at=add_at)

    def queue_scan(self):
        self._queue_scan()

    def run_scan(self):
        self._queue_scan(add_at='head')
        self.plan_processor.run()

    def run_test_scan(self):
        condition = self.lineEdit_condition.text()
        repeat = self.spinBox_scan_repeat.value()
        self.lineEdit_condition.setText(f'{condition} test')
        self.spinBox_scan_repeat.setValue(1)
        self._queue_scan(add_at='head')
        self.lineEdit_condition.setText(condition)
        self.spinBox_scan_repeat.setValue(repeat)
        self.plan_processor.run()

    def handle_execution_buttons(self):
        if self.plan_processor.status == 'idle':
            self.push_run_test_scan.setEnabled(True)
            self.push_run_scan.setEnabled(True)
        elif (self.plan_processor.status == 'running') or (self.plan_processor.status == 'paused'):
            self.push_run_test_scan.setEnabled(False)
            self.push_run_scan.setEnabled(False)

    def draw_data(self, df_interp, df_binned):
        update_figure([self.figure.ax2, self.figure.ax1, self.figure.ax3], self.toolbar, self.canvas)

        # Clear previous legends if any
        for leg in self.figure.legends:
            leg.remove()

        graph_list = []
        channel_list = [
            {'num': 'i0', 'den': 'it', 'log': True,
             'label': 'Transmission', 'axis': self.figure.ax1, 'color': 'r'},
            {'num': 'iff', 'den': 'i0', 'log': False,
             'label': 'Total Fluorescence', 'axis': self.figure.ax2, 'color': 'g'},
            {'num': 'it', 'den': 'ir', 'log': True,
             'label': 'Reference', 'axis': self.figure.ax3, 'color': 'b'},
        ]

        energy_interp = np.array(df_interp['energy'])
        energy_binned = np.array(df_binned['energy'])

        for channel in channel_list:
            num = channel['num']
            den = channel['den']
            if num in df_interp and den in df_interp and 'energy' in df_interp:
                # First (interpolated, transparent)
                signal = np.array(df_interp[num] / df_interp[den])
                if channel['log']:
                    signal = np.log(signal)
                channel['axis'].plot(
                    energy_interp,
                    signal,
                    color=channel['color'],
                    alpha=0.2)

                # Second (binned, solid) → for legend
                signal = np.array(df_binned[num] / df_binned[den])
                if channel['log']:
                    signal = np.log(signal)
                line, = channel['axis'].plot(
                    energy_binned,
                    signal,
                    color=channel['color'],
                    label=channel['label']
                )
                graph_list.append(line)  # ← now using the solid line for the legend

        self.figure.ax1.set_xlabel('Energy, eV',fontsize = 14)


        # Add the legend
        self.figure.ax1.legend(
            handles = graph_list,
            loc='upper right',
            framealpha=0.8,
            frameon=False
        )
        self.figure.tight_layout()
        self.canvas.draw()

    def draw_interpolated_data(self, df_interp, df_binned):
        update_figure([self.figure.ax2, self.figure.ax1, self.figure.ax3], self.toolbar, self.canvas)

        energy = np.array(df_interp['energy'])
        edge = int(len(energy) * 0.02)

        if 'i0' in df_interp and 'it' in df_interp and 'energy' in df_interp:
            transmission = np.array(np.log(df_interp['i0'] / df_interp['it']))
            self.figure.ax1.plot(energy, transmission, color='r', alpha=0.2,
                                 label='Transmission')
            self.figure.ax1.legend(loc=2)
        if 'i0' in df_interp and 'iff' in df_interp and 'energy' in df_interp:
            fluorescence = np.array(df_interp['iff'] / df_interp['i0'])
            self.figure.ax2.plot(energy, fluorescence, color='g', alpha=0.2,
                                 label='Total fluorescence')
            self.figure.ax2.legend(loc=1)
        if 'it' in df_interp and 'ir' in df_interp and 'energy' in df_interp:
            reference = np.array(np.log(df_interp['it'] / df_interp['ir']))
            self.figure.ax3.plot(energy, reference, color='b', alpha=0.2, label='Reference')
            self.figure.ax3.legend(loc=3)

        energy = np.array(df_binned['energy'])
        edge = int(len(energy) * 0.02)
        if 'i0' in df_binned and 'it' in df_binned and 'energy' in df_binned:
            transmission = np.array(np.log(df_binned['i0'] / df_binned['it']))
            self.figure.ax1.plot(energy, transmission, color='r')
        if 'i0' in df_binned and 'iff' in df_binned and 'energy' in df_binned:
            fluorescence = np.array(df_binned['iff'] / df_binned['i0'])
            self.figure.ax2.plot(energy, fluorescence, color='g')
        if 'it' in df_binned and 'ir' in df_binned and 'energy' in df_binned:
            reference = np.array(np.log(df_binned['it'] / df_binned['ir']))
            self.figure.ax3.plot(energy, reference, color='b')

        self.figure.ax3.set_xlabel('Energy, eV', fontsize=14)
        self.figure.tight_layout()
        self.canvas.draw_idle()



    def make_xasplot_func(self, plan_name, plan_kwargs):

        detectors = plan_kwargs['detectors']

        if plan_name in ['step_scan_plan', 'step_scan_von_hamos_plan', 'step_scan_johann_herfd_plan']:
            motor_name = self.hhm.energy.name
        elif plan_name in ['step_scan_johann_xes_plan']:
            motor_name = self.johann_spectrometer_motor.energy.name
        elif plan_name in ['fly_scan_plan', 'fly_scan_von_hamos_plan', 'fly_scan_johann_herfd_plan', 'epics_fly_scan_johann_xes_plan']:
            return []
        else:
            motor_name = 'time'

        update_figure([self.figure.ax2, self.figure.ax1, self.figure.ax3], self.toolbar, self.canvas)

        xasplot_list = []
        liveplot_kwargs_list = [{'num_name': 'apb_ave_ch1_mean', 'den_name': 'apb_ave_ch2_mean', 'result_name': 'Transmission',
                                'log': True, 'ax': self.figure.ax1, 'color': 'r', 'legend_keys': ['Transmission']},
                               {'num_name': 'apb_ave_ch2_mean', 'den_name': 'apb_ave_ch3_mean', 'result_name': 'Reference',
                                'log': True, 'ax': self.figure.ax2, 'color': 'b', 'legend_keys': ['Reference']},
                               {'num_name': 'apb_ave_ch4_mean', 'den_name': 'apb_ave_ch1_mean', 'result_name': 'PIPS TFY',
                                'log': False, 'ax': self.figure.ax3, 'color': 'g', 'legend_keys': ['PIPS TFY']}, ]
        if 'Pilatus 100k' in detectors:
            liveplot_kwargs_list.append(
                {'num_name': 'pil100k_stats1_total', 'den_name': 'apb_ave_ch1_mean', 'result_name': 'HERFD',
                 'log': False, 'ax': self.figure.ax3, 'color': 'm', 'legend_keys': ['HERFD']})
        if 'Xspress3' in detectors:
            liveplot_kwargs_list.append(
                {'num_name': 'xs_channel1_rois_roi01_value', 'den_name': 'apb_ave_ch2_mean', 'result_name': 'SDD',
                 'log': False, 'ax': self.figure.ax3, 'color': 'm', 'legend_keys': ['SDD']})
        if 'Ge detector' in detectors:
            liveplot_kwargs_list.append(
                {'num_name': 'ge_detector_channels_mca1_R0', 'den_name': 'apb_ave_ch1_mean', 'result_name': 'Ge detector',
                 'log': False, 'ax': self.figure.ax3, 'color': 'm', 'legend_keys': 'Ge detector'})

        for liveplot_kwargs in liveplot_kwargs_list:
            _xasplot = self._xasplot_from_dict(liveplot_kwargs, motor_name)
            xasplot_list.append(_xasplot)
        print('.........................................')
        print(liveplot_kwargs_list)
        print('.........................................')
        return xasplot_list

    def _xasplot_from_dict(self, kwargs, motor_name):
        return XASPlot(kwargs['num_name'], kwargs['den_name'], kwargs['result_name'], motor_name, log=kwargs['log'],
                       ax=kwargs['ax'], color=kwargs['color'], legend_keys=kwargs['legend_keys'])




