from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout,
    QSpinBox, QLabel
)

from PyQt5.QtWidgets import QWidget, QLabel, QSpinBox, QHBoxLayout
from PyQt5 import QtWidgets
from PyQt5.QtCore import QTimer

from PyQt5 import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'elements/roi_widget.ui')

class ROIWidget(*uic.loadUiType(ui_path)):
    def __init__(self, ge_detector, roi = 1, channel=1):
        super().__init__()
        self.setupUi(self)
        self.setLayout(self.layout)
        self.setVisible(True)

        self. roi = roi-1
        self.ge_detector = ge_detector
        self.channel = channel
        self.ch = getattr(self.ge_detector._channels, f"mca{channel}")
        self.roi_lo = getattr(self.ch, f'R{self.roi}low')
        self.roi_hi = getattr(self.ch, f'R{self.roi}high')
        self.counts = getattr(self.ch, f'R{self.roi}')


        # Constants for scaling
        self.ENERGY_MAX = ge_detector.settings.max_energy
        self.PIXEL_MAX = ge_detector.settings.mca_len

        self.spin_roi_lo.setRange(0, self.ENERGY_MAX)
        self.spin_roi_hi.setRange(0, self.ENERGY_MAX)
        self.set_initial_values()

        # Connect logic
        self.counts.subscribe(self.on_counts_change)
        self.spin_roi_lo.valueChanged.connect(self.update_detector)
        self.spin_roi_hi.valueChanged.connect(self.update_detector)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def on_counts_change(self, *args, **kwargs):
        _counts = self.counts.get()
        self.label_counts.setText(str(_counts))

    def pixel_to_energy(self, pixel_val):
        return int(pixel_val * self.ENERGY_MAX / self.PIXEL_MAX)

    def energy_to_pixel(self, energy_val):
        return int(energy_val * self.PIXEL_MAX / self.ENERGY_MAX)

    def set_initial_values(self):
        try:
            lo_pixel = self.roi_lo.get()
            hi_pixel = self.roi_hi.get()
            counts = self.counts.get()
            self.spin_roi_lo.setValue(self.pixel_to_energy(lo_pixel))
            self.spin_roi_hi.setValue(self.pixel_to_energy(hi_pixel))
            self.label_counts.setText(str(counts))
            self.label_channel.setText(str(self.channel))
        except Exception as e:
            print(f"[Channel {self.channel}] init failed: {e}")

    def update_detector(self):
        lo_energy = self.spin_roi_lo.value()
        hi_energy = self.spin_roi_hi.value()
        try:
            lo_pixel = self.energy_to_pixel(lo_energy)
            hi_pixel = self.energy_to_pixel(hi_energy)
            self.roi_lo.put(lo_pixel)
            self.roi_hi.put(hi_pixel)
        except Exception as e:
            print(f"[Channel {self.channel}] update failed: {e}")


        # If values become equal, revert the sender

