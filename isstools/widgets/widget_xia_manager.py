import re
import time as ttime
import bluesky.plan_stubs as bps

import numpy as np
import pkg_resources

from PyQt5 import uic,  QtCore
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor
from PyQt5.Qt import QSplashScreen, QObject
import numpy
from PyQt5 import  QtWidgets
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from PyQt5.QtCore import pyqtSignal

from isstools.dialogs.BasicDialogs import question_message_box, error_message_box, message_box
from isstools.elements.figure_update import update_figure, setup_figure
from isstools.elements.roi_widget import ROIWidget

from isstools.widgets import widget_energy_selector_with_periodic_table


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_xia_manager.ui')


class UIXIAManager(*uic.loadUiType(ui_path)):
    element_selected = pyqtSignal(str)  # Signal to send selected element
    def __init__(self,
                 service_plan_funcs=None,
                 ge_detector = None,
                 RE=None,
                 parent = None,
                 *args,
                 **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.figure_mca, self.canvas_mca,self.toolbar_mca = setup_figure(self, self.layout_plot_mca)
        self.service_plan_funcs = service_plan_funcs
        self.RE = RE
        self.parent = parent
        self.plot_will_reset = False
        self.ge_detector = ge_detector



        self.change_collection_modes = {
            "MCA spectra": 0,
            "MCA mapping": 1,
            "SCA mapping": 2
        }
        self.mcas = []
        self.calibrations = []
        self.dead_channels = {4, 6, 30, 32}  # those channels are PHYSICALLY dead

        self.comboBox_collection_mode.addItems(list(self.change_collection_modes.keys()))
        self.comboBox_collection_mode.currentTextChanged.connect(self.change_collection_mode)
        self.push_acquire.clicked.connect(self.acquire)
        self.push_reorder_rois.clicked.connect(self.reorder_rois_by_lo)
        self.push_ch1_to_all.clicked.connect(self.copy_ch1_to_all)
        self.push_calibrate.clicked.connect(self.calibrate)
        self.push_reset_checkboxes.clicked.connect(self.reset_checkboxes)
        self.pushButton_reset_plot.clicked.connect(self.reset_plot)


        self.spinBox_acq_time.valueChanged.connect(self.set_acquition_time)
        self.ge_detector.settings.acquiring.subscribe(self.on_change_acquisition_status)
        self.label_acquiring.setStyleSheet("")

        self.widget_energy_selector = widget_energy_selector_with_periodic_table.UIEnergySelectorWithPeriodicTable(emission=True)
        self.layout_energy_selector.addWidget(self.widget_energy_selector)

        self.canvas_mca.mpl_connect("button_press_event", self.on_canvas_click)
        self.populate_layouts()

    def reset_plot(self):
        self.plot_will_reset = True

    def populate_layouts(self):


        self.spinBox_acq_time.setValue(self.ge_detector.settings.real_time.get())
        for ch in range(1, 33):
            checkbox = QtWidgets.QCheckBox(f'Channel {ch}')
            checkbox.setCheckState(True)
            checkbox.setTristate(False)
            self.verticalLayout_channels.addWidget(checkbox)
            value = self.parent.settings.value(f'checkbox_ch{ch}', True, type=bool)
            checkbox.setChecked(value)
            if ch in self.dead_channels:
                checkbox.setChecked(False)
                checkbox.setEnabled(False)
            checkbox.stateChanged.connect(lambda state,ch=ch: self.parent.settings.setValue(f'checkbox_ch{ch}', bool(
                state)))
            checkbox.stateChanged.connect(self.plot_data)
            setattr(self, f'checkbox_ch{ch}', checkbox)

        self.roi_widgets = []
        for roi in range(1, 5):
            layout = getattr(self, f'gridLayout_roi{roi}')
            _roi = []
            for ch in range(1, 33):
                roi_widget=ROIWidget(ge_detector=self.ge_detector, roi = roi, channel = ch)
                _roi.append(roi_widget)
                layout.addWidget(roi_widget, ch, 0)
            self.roi_widgets.append(_roi)

    def reset_checkboxes(self):
        for ch in range(1, 33):
            if ch not in self.dead_channels:
                checkbox = getattr(self, f'checkbox_ch{ch}')
                checkbox.setChecked(True)


    def on_canvas_click(self, event):
        if event.button == 3:  # Right-click (1=left, 2=middle, 3=right)
            if event.xdata is not None:
                self.measured_energy = event.xdata
                self.spinBox_measured_energy.setValue(int(self.measured_energy))

    def on_change_acquisition_status(self, *args, **kwargs):
        if self.ge_detector.acquiring == 1:
            self.label_acquiring.setText("Acquiring...")
            self.label_acquiring.setStyleSheet("background-color: red; color: black;")
        elif self.ge_detector.acquiring == 0:
            self.label_acquiring.setText("Idle")
            self.label_acquiring.setStyleSheet("")



        # ✅ Add mode-switching ComboBox logic here


        # Optional: Initialize current mode from detector
        try:
            current_mode = self.ge_detector.mode.get()
            index = self.comboBox_collection_mode.findText(current_mode)
            if index != -1:
                self.comboBox_collection_mode.setCurrentIndex(index)
        except Exception as e:
            print(f"Could not get initial mode: {e}")

    def set_acquition_time(self):
        self.ge_detector.settings.real_time.set(self.spinBox_acq_time.value())
        self.ge_detector.settings.live_time.set(self.spinBox_acq_time.value())

    def copy_ch1_to_all(self):
        # Get the current ROI tab index
        roi_idx = self.tab_rois.currentIndex()

        # Get the reference widget from Channel 1 (index 0)
        source_widget = self.roi_widgets[roi_idx][0]

        # Get values from source (in pixel units or energy if already converted)
        lo = source_widget.spin_roi_lo.value()
        hi = source_widget.spin_roi_hi.value()

        for ch in range(1, 33):  # Channels 1 to 32 (1-based)
            if ch == 1:
                continue  # Skip Channel 1 and disabled ones

            target_widget = self.roi_widgets[roi_idx][ch - 1]  # ch-1 = 0-based index

            # Block signals to avoid triggering updates during set
            target_widget.spin_roi_lo.blockSignals(True)
            target_widget.spin_roi_hi.blockSignals(True)

            target_widget.spin_roi_lo.setValue(lo)
            target_widget.spin_roi_hi.setValue(hi)

            target_widget.spin_roi_lo.blockSignals(False)
            target_widget.spin_roi_hi.blockSignals(False)

            target_widget.update_detector()

    def reorder_rois_by_lo(self):
        for ch in range(1, 33):
            widgets = [self.roi_widgets[roi_idx][ch - 1] for roi_idx in range(4)]

            # Collect current ROI bounds and widget
            roi_data = []
            for w in widgets:
                lo = w.roi_lo.get()
                hi = w.roi_hi.get()
                roi_data.append({'widget': w, 'lo': lo, 'hi': hi})

            # Sort by lo value
            roi_data_sorted = sorted(roi_data, key=lambda x: x['lo'])

            #Reassign R0–R3 based on sorted order
            for unsorted_item, sorted_item in zip(roi_data, roi_data_sorted):
                lo = sorted_item['lo']
                hi = sorted_item['hi']
                widget = unsorted_item['widget']

                # Block signals to prevent triggering update_detector multiple times
                widget.spin_roi_lo.blockSignals(True)
                widget.spin_roi_hi.blockSignals(True)
                widget.spin_roi_lo.setValue(widget.pixel_to_energy(lo))
                widget.spin_roi_hi.setValue(widget.pixel_to_energy(hi))
                widget.spin_roi_lo.blockSignals(False)
                widget.spin_roi_hi.blockSignals(False)

                # update the detector
                widget.update_detector()

    def change_collection_mode(self):
        mode = self.comboBox_collection_mode.currentText()
        self.ge_detector.settings.collection_mode.put(self.change_collection_modes[mode])

    def acquire(self):
        #TODO open shutter self.shutter_dict
        #self.plot_will_reset = True
        print('XIA acquisition starting...')
        self.ge_detector.settings.start.put(1)
        start_time = ttime.time()
        timeout = 0.5  # seconds
        while self.ge_detector.settings.acquiring.get() == 0:
            if ttime.time() - start_time > timeout:
                pass
            ttime.sleep(0.1)
        while self.ge_detector.settings.acquiring.get() == 1:
            ttime.sleep(0.1)
        self.acquired = True
        self.get_mcas()
        print('XIA acquisition complete')
        self.plot_will_reset = False

    def get_mcas(self):
        self.mcas = []
        self.calibrations = []
        for jj in range(1,33):
                _mca = getattr(self.ge_detector._channels, f'mca{jj}').get()
                mca = np.array(_mca[0])
                energy = (np.array(range(len(mca)))*self.ge_detector.settings.max_energy/
                          self.ge_detector.settings.mca_len)
                self.mcas.append((energy[200:],  mca[200:]))
        self.plot_data()



    def calibrate(self):

        def gaussian(x, a, x0, sigma, offset):
            return a * np.exp(-((x - x0) ** 2) / (2 * sigma ** 2)) + offset

        nominal_energy = float(self.widget_energy_selector.edit_E0.text())
        measured_energy = self.spinBox_measured_energy.value()
        if abs(measured_energy - nominal_energy) > 100:
            error_message_box('The difference between the measured energy and the nominal energy is too high. '
                              'Please adjust the gains manually')
            return
        energy_shifts = {}
        self.mcas = []
        self.calibrations = []

        for jj in range(1,33):
            _mca = getattr(self.ge_detector._channels, f'mca{jj}').get()
            mca = np.array(_mca[0])
            energy = (np.array(range(len(mca)))*self.ge_detector.settings.max_energy/
                      self.ge_detector.settings.mca_len)

            center = self.spinBox_measured_energy.value()
            width = 500
            lower_bound = center - width
            upper_bound = center + width
            mask = (energy >= lower_bound) & (energy <= upper_bound)

            energy_filtered = energy[mask]
            mca_filtered = mca[mask]
            a_guess = mca_filtered.max()
            x0_guess = center
            sigma_guess = 10
            offset_guess = np.median(mca_filtered)
            p0 = [a_guess, x0_guess, sigma_guess, offset_guess]
            popt, pcov = curve_fit(gaussian, energy_filtered, mca_filtered, p0=p0)

            # Extract fit parameters
            a_fit, x0_fit, sigma_fit, offset_fit = popt
            checkbox = getattr(self, f'checkbox_ch{jj}')
            if checkbox.isChecked():
                energy_shifts[f'{jj}'] = x0_fit - nominal_energy
                print(f'channel {jj}: center {x0_fit} eV shift {x0_fit - nominal_energy} eV')
            self.mcas.append((energy[200:],  mca[200:]))
            self.calibrations.append((energy_filtered, gaussian(energy_filtered, *popt)))
        self.plot_data()
        message = "Energy shifts:\n" + "\n".join(f"Channel {k}: {v:.2f}" for k, v in energy_shifts.items())
        message += "\n\nProceed with calibration?"
        ret = question_message_box(self,'Calibration', message)
        if ret:
            for channel in  energy_shifts.keys():
                adjustment = (energy_shifts[channel] + nominal_energy) / nominal_energy
                self.adjust_gain(channel, adjustment)


    def adjust_gain(self, channel, adjustment):
        gain_setting = getattr(self.ge_detector.preamps, f'dxp{channel}.gain')
        gain = gain_setting.get()
        new_gain = gain * adjustment
        gain_setting.set(new_gain)


    def plot_data(self):
        if not self.plot_will_reset:
            xlim = self.figure_mca.ax.get_xlim()
        update_figure([self.figure_mca.ax], self.toolbar_mca, self.canvas_mca)
        self.figure_mca.ax.legend().remove()
        if self.mcas:
            color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
            for jj in range(1,33):
                checkbox = getattr(self, f'checkbox_ch{jj}')
                if checkbox.isChecked():
                    color = color_cycle[jj % len(color_cycle)]
                    mca = self.mcas[jj-1]
                    self.figure_mca.ax.plot(mca[0], mca[1], color=color, label=f'Channel {jj}')
                    if self.calibrations:
                        calibration = self.calibrations[jj-1]
                        self.figure_mca.ax.plot(calibration[0], calibration[1],
                        linestyle="--", color=color)

            self.figure_mca.ax.set_xlabel("Energy /eV", fontsize=12)
            self.figure_mca.ax.set_ylabel("Counts", fontsize=12)

            # Place legend *inside* the plot
            handles, labels = self.figure_mca.ax.get_legend_handles_labels()

            # Check if we have more than 10 entries
            if len(labels) > 10:
                # Keep the first 8 labels and add '---' for the rest
                labels = labels[:8] + ['---'] + labels[-1:]
                handles = handles[:8] + [handles[-1]]

            # Now create the legend with the modified labels and your customizations
            self.figure_mca.ax.legend(
                handles=handles,
                labels=labels,
                loc='upper right',  # or 'best', 'lower left', etc.
                frameon=True,
                fontsize='small',  # Smaller font for better readability
                borderpad=1,  # Padding around the legend box
                shadow=True  # Add a shadow for better visibility
            )
            self.figure_mca.tight_layout()
            if not self.plot_will_reset:
                self.figure_mca.ax.set_xlim(xlim)
            self.figure_mca.canvas.draw()


'''
def worker(jj):
    from scipy.optimize import curve_fit
    
    # Define Gaussian model
    def gaussian(x, a, x0, sigma, offset):
        return a * np.exp(-((x - x0) ** 2) / (2 * sigma ** 2)) + offset
    
    # Get MCA spectrum (adjust jj as needed)
    
    _mca = getattr(ge_detector._channels, f'mca{jj}').get()
    mca = np.array(_mca[0])
    
    # Compute energy scale
    energy = (
        np.arange(len(mca)) *
        ge_detector.settings.max_energy /
        ge_detector.settings.mca_len
    )
    
    # Filter region around selected energy
    center = 6350
    width = 500
    lower_bound = center - width
    upper_bound = center + width
    
    mask = (energy >= lower_bound) & (energy <= upper_bound)
    energy_filtered = energy[mask]
    mca_filtered = mca[mask]
    
    # Initial guess for Gaussian parameters
    a_guess = mca_filtered.max()
    x0_guess = center
    sigma_guess = 250
    offset_guess = np.median(mca_filtered)
    p0 = [a_guess, x0_guess, sigma_guess, offset_guess]
    
    # Fit Gaussian
    popt, pcov = curve_fit(gaussian, energy_filtered, mca_filtered, p0=p0)
    a_fit, x0_fit, sigma_fit, offset_fit = popt
    
    fitted_curve = gaussian(energy_filtered, *popt)
    
    # Plot original data and fitted curve
    plt.figure(figsize=(8, 5))
    plt.plot(energy[200:], mca[200:], label='Measured Data', marker='o', linestyle='-', color='blue')
    plt.plot(energy_filtered, fitted_curve, label='Gaussian Fit', linestyle='--', color='red')
    plt.axvline(x0_fit, color='green', linestyle=':', label=f'Center = {x0_fit:.1f} eV')
    
    plt.title(f'Gaussian Fit to Emission Line, channel {jj}')
    plt.xlabel('Energy (eV)')
    plt.ylabel('Counts')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


'''




