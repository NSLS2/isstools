import re
import time as ttime
import bluesky.plan_stubs as bps

import numpy as np
import pkg_resources

from qtpy import uic,  QtCore
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor
from qtpy.Qt import QSplashScreen, QObject
import numpy

from isstools.dialogs.BasicDialogs import question_message_box, error_message_box, message_box
from isstools.elements.figure_update import update_figure, setup_figure

# from isstools.widgets import widget_energy_selector
from isstools.widgets import widget_energy_selector_with_periodic_table
ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_sdd_manager.ui')


class UISDDManager(*uic.loadUiType(ui_path)):

    def __init__(self,
                 service_plan_funcs,
                 xs,
                 RE,

                 *args,
                 **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.figure_mca, self.canvas_mca,self.toolbar_mca = setup_figure(self, self.layout_plot_mca)
        self.service_plan_funcs = service_plan_funcs
        self.RE = RE
        self.xs = xs
        self.roi_bounds = []
        #self.shutter_dict=shutter_dict
        self.counter = 0

        # self.widget_energy_selector = widget_energy_selector.UIEnergySelector(emission=True)
        # self.layout_energy_selector.addWidget(self.widget_energy_selector)
        self.widget_energy_selector = widget_energy_selector_with_periodic_table.UIEnergySelectorWithPeriodicTable(emission=True)
        self.layout_energy_selector.addWidget(self.widget_energy_selector)

        self.timer_update_time = QtCore.QTimer(self)
        self.timer_update_time.setInterval(1000)
        self.timer_update_time.timeout.connect(self.update_roi_labels)
        self.timer_update_time.start()

        self.push_xs3_acquire.clicked.connect(self.xs3_acquire)

        self.colors = ['r', 'b', 'g', 'm']
        self.num_channels = 4
        self.num_rois = 4
        self.roi_values = numpy.zeros((4, 4, 2))
        self.roi_bounds = []
        self.acquired = 0
        self.checkbox_ch = 'checkBox_ch{}_show'

        for indx in range(self.num_channels):
             getattr(self, self.checkbox_ch.format(indx + 1)).stateChanged.connect(self.plot_traces)

        self.checkbox_roi = 'checkBox_roi{}_show'
        for indx in range(self.num_rois):
             getattr(self, self.checkbox_roi.format(indx + 1)).stateChanged.connect(self.update_roi_bounds)

        self.lo_hi = ['lo','hi']
        self.lo_hi_def = {'lo':'low', 'hi':'high'}
        self.spinbox_roi = 'spinBox_ch{}_roi{}_{}'
        self.label_roi_rbk = 'label_ch{}_roi{}_{}_rbk'
        self.label_roi_counts = 'label_ch{}_roi{}_roi_counts'
        self.update_spinboxes()
        self.connect_roi_spinboxes()
        self.comboBox_roi_index.addItems([str(i+1) for i in range(self.num_rois)])
        self.pushButton_set_roi_hilo.clicked.connect(self.set_roi_hilo)
        self.pushButton_reset_limits.clicked.connect(self.reset_limit)
        self.reset = 0
        self.checkBox_roi_window_auto.toggled.connect(self.enable_doubleSpinBox_energy_window)

    def connect_roi_spinboxes(self):
        for indx_ch in range(self.num_channels):
            for indx_roi in range(self.num_rois):
                for indx_lo_hi in range(2):
                    spinbox_name = self.spinbox_roi.format(indx_ch + 1, indx_roi + 1, self.lo_hi[indx_lo_hi])
                    # print(spinbox_name)
                    spinbox_object = getattr(self, spinbox_name)
                    spinbox_object.editingFinished.connect(self.set_roi_value)

    def disconnect_roi_spinboxes(self):
        for indx_ch in range(self.num_channels):
            for indx_roi in range(self.num_rois):
                for indx_lo_hi in range(2):
                    spinbox_name = self.spinbox_roi.format(indx_ch + 1, indx_roi + 1, self.lo_hi[indx_lo_hi])
                    spinbox_object = getattr(self, spinbox_name)
                    spinbox_object.editingFinished.disconnect(self.set_roi_value)

    def set_roi_value(self):
        go = False
        sender = QObject()
        sender_object = sender.sender().objectName()
        indx_ch = sender_object[10]
        indx_roi = sender_object[15]
        lo_hi = sender_object[17:]
        signal = self.get_roi_signal(indx_ch, indx_roi, self.lo_hi.index(lo_hi))
        value = sender.sender().value()
        if self.lo_hi.index(lo_hi) == 0:
            countervalue =self.roi_values[int(indx_ch)-1, int(indx_roi)-1, 1]
            if value >= countervalue:
                getattr(self,sender_object).setValue(int(countervalue-10))
                error_message_box('Selected low limit is set higher than high limit. Adjust manually')
                return
        else:
            countervalue =self.roi_values[int(indx_ch)-1, int(indx_roi)-1, 0]
            if value <= countervalue:
                getattr(self,sender_object).setValue(int(countervalue+10))
                error_message_box('Selected high limit is set lower than low limit. Adjust manually')
                return

        signal.put(int(value/10))
        #   print(f' Value {value}')
        self.roi_values[int(indx_ch)-1, int(indx_roi)-1, self.lo_hi.index(lo_hi)]= value
        self.update_roi_bounds()

    def get_roi_signal(self, indx_ch,indx_roi,indx_lo_hi):
        signal_ch = getattr(self.xs, 'channel{}'.format(indx_ch))
        signal_roi = getattr(signal_ch.rois, 'roi0{}'.format(indx_roi))
        signal = getattr(signal_roi, 'bin_{}'.format(self.lo_hi_def[self.lo_hi[indx_lo_hi]]))
        return signal

    def get_roi_counts_signal(self, indx_ch, indx_roi):
        signal_ch = getattr(self.xs, 'channel{}'.format(indx_ch))
        signal_roi = getattr(signal_ch.rois, 'roi0{}'.format(indx_roi))
        signal = signal_roi.value_sum
        return signal


    def update_roi_labels(self):
        try:
            for indx_ch in range(self.num_channels):
                for indx_roi in range(self.num_rois):
                    for indx_lo_hi in range(2):
                        label_name =self.label_roi_rbk.format(indx_ch+1, indx_roi+1, self.lo_hi[indx_lo_hi])
                        label_object = getattr(self,label_name)
                        value = self.get_roi_signal( indx_ch+1, indx_roi+1, indx_lo_hi).get()
                        label_object.setText(str(value*10))

                        label_count_name = self.label_roi_counts.format(indx_ch + 1, indx_roi + 1)
                        label_count_object = getattr(self, label_count_name)
                        counts = int(self.get_roi_counts_signal( indx_ch+1, indx_roi+1).get())
                        label_count_object.setText(str(counts))
                        if counts < 400e3:
                            label_count_object.setStyleSheet("background-color: lime")
                        elif 400e3 < counts < 450e3:
                            label_count_object.setStyleSheet("background-color: yellow")
                        else:
                            label_count_object.setStyleSheet("background-color: red")
        except:
            print('Failed to read ROI values')

    def update_spinboxes(self):
       # print('Updating spinboxes')
        for indx_ch in range(self.num_channels):
            for indx_roi in range(self.num_rois):
                for indx_lo_hi in range(2):
                    spinbox_name = self.spinbox_roi.format(indx_ch+1,indx_roi+1,self.lo_hi[indx_lo_hi])
                    spinbox_object = getattr(self,spinbox_name)
                    value = self.get_roi_signal(indx_ch+1, indx_roi+1, indx_lo_hi).get() * 10
                    spinbox_object.setValue(value)
                    self.roi_values[indx_ch,indx_roi,indx_lo_hi] = value
        self.update_roi_bounds()

    def update_roi_bounds(self):
        for roi_bound in self.roi_bounds:
            roi_bound[0].remove()
        self.roi_bounds = []
        ylims=self.figure_mca.ax.get_ylim()
        for indx_ch in range(self.num_channels):
            show_ch = getattr(self, 'checkBox_ch{}_show'.format(indx_ch + 1)).isChecked()
            for indx_roi in range(self.num_rois):
                show_roi = getattr(self, 'checkBox_roi{}_show'.format(indx_roi + 1)).isChecked()
                for indx_hi_lo in range(2):
                    if show_ch and show_roi:
                        #print('plotting')
                        color = self.colors[indx_ch]
                        value = self.roi_values[indx_ch,indx_roi,indx_hi_lo]
                        h = self.figure_mca.ax.plot([value, value], [0, ylims[1] * 0.85], color, linestyle='dashed',
                                                        linewidth=0.5)
                        self.roi_bounds.append(h)
        # self.figure_mca.ax.set_ylim(ylims)
        self.canvas_mca.draw_idle()



    def xs3_acquire(self):
       #TODO open shutter self.shutter_dict
        self.roi_bounds = []
        print('Xspress3 acquisition starting...')
        acq_time = self.spinBox_acq_time.value()
        self.xs.test_exposure(acq_time=acq_time)
        # self.RE(plan(acq_time = acq_time))
        self.acquired = True
        self.plot_traces()
        # self.update_roi_bounds()
        self.canvas_mca.draw_idle()
        print('Xspress3 acquisition complete')

    # TODO close shutter self.shutter_dict

    def plot_traces(self):
        max_mca = []
        #THis method plot the MCA signal
        xlims = self.figure_mca.ax.get_xlim()
        ylims = self.figure_mca.ax.get_ylim()
        update_figure([self.figure_mca.ax], self.toolbar_mca, self.canvas_mca)
        self.roi_bounds = []
        if self.acquired:
            for indx in range(self.num_channels):
                if getattr(self, self.checkbox_ch.format(indx+1)).isChecked():
                    ch = getattr(self.xs,'mca{}'.format(indx+1))
                    mca = ch.get()
                    max_mca.append(max(mca[10:]))
                    # energy = np.array(list(range(len(mca))))*10
                    energy = np.arange(mca.size)*10
                    self.figure_mca.ax.plot(energy[10:], mca[10:], self.colors[indx], label = 'Channel {}'.format(indx+1))
        self.figure_mca.ax.legend(loc=1)
        if self.counter:
            if self.reset:
                self.figure_mca.ax.set_xlim(-200, 40200)
                self.figure_mca.ax.set_ylim(max(max_mca)*-0.1,max(max_mca)*1.1)
                self.reset = 0
            else:
                self.figure_mca.ax.set_xlim(xlims)
                self.figure_mca.ax.set_ylim(ylims)
        self.update_roi_bounds()
        self.counter = 1

    def set_roi_hilo(self):
        self.disconnect_roi_spinboxes()
        energy = float(self.widget_energy_selector.edit_E0.text())
        _roi_index = int(self.comboBox_roi_index.currentText())
        roi = f'roi{_roi_index:02}'
        if self.doubleSpinBox_energy_window.isEnabled():
            window = self.doubleSpinBox_energy_window.value()
        else:
            window = 'auto'
        self.xs.set_limits_for_roi(energy, roi, window=window)
        self.update_spinboxes()
        self.connect_roi_spinboxes()

        element = self.widget_energy_selector.comboBox_element.currentText()
        line = self.widget_energy_selector.comboBox_edge.currentText()

        lineEdit_roi = getattr(self, f'lineEdit_line_label_roi{_roi_index}')
        lineEdit_roi.setText(f'{element} {line}')

    def enable_doubleSpinBox_energy_window(self, state):
        self.doubleSpinBox_energy_window.setEnabled(not state)

    def reset_limit(self):
        self.reset = 1