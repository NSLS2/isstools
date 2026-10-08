from types import SimpleNamespace
from unittest.mock import Mock
import threading

import numpy as np
from matplotlib.widgets import RectangleSelector
from PyQt5 import QtCore, QtWidgets
import pytest

from isstools.widgets.widget_pilatus import UIPilatusMonitor


@pytest.fixture
def monitor(qtbot):
    # Construct the actual UI without connecting to or configuring a detector.
    widget = UIPilatusMonitor.__new__(UIPilatusMonitor)
    QtWidgets.QWidget.__init__(widget)
    widget.setupUi(widget)
    qtbot.addWidget(widget)
    widget.addCanvas()
    widget.RS = RectangleSelector(
        widget.figure_pilatus_image.ax, lambda *args: None, useblit=True,
        button=[1, 3], minspanx=5, minspany=5, spancoords='pixels', interactive=True,
    )
    widget._patches = {}
    widget._min, widget._max = 0, 5
    widget.colors = {1: 'r', 2: 'c', 3: 'g', 4: 'y'}
    for i in range(1, 5):
        getattr(widget, f'checkBox_roi{i}').setChecked(False)
    image = np.arange(195 * 487, dtype=np.int32)
    widget.pilatus100k_device = SimpleNamespace(
        image=SimpleNamespace(array_data=SimpleNamespace(value=image)),
        get_roi_coords=Mock(return_value=(10, 20, 30, 40)),
    )
    return widget


def test_frames_reuse_artists_preserve_zoom_and_detector_data(monitor):
    raw = monitor.pilatus100k_device.image.array_data.value
    original = raw.copy()
    monitor.checkBox_roi1.setChecked(True)
    monitor.update_pilatus_image()
    axes = monitor.figure_pilatus_image.ax
    artist = axes.images[0]
    roi = monitor._patches['checkBox_roi1']
    selector_artist_count = len(axes.patches)
    axes.set_xlim(20, 70)
    axes.set_ylim(80, 30)
    monitor.RS.extents = (25, 45, 40, 60)

    monitor._min, monitor._max = 2, 9
    monitor.pilatus100k_device.get_roi_coords.return_value = (11, 21, 31, 41)
    for _ in range(5):
        monitor.update_pilatus_image()

    assert len(axes.images) == 1
    assert axes.images[0] is artist
    assert len(axes.patches) == selector_artist_count
    assert monitor._patches['checkBox_roi1'] is roi
    assert roi.get_bbox().bounds == (21, 11, 41, 31)
    assert axes.get_xlim() == (20, 70)
    assert axes.get_ylim() == (80, 30)
    assert artist.get_clim() == (2, 9)
    assert monitor.RS.extents == (25, 45, 40, 60)
    assert all(artist.axes is axes for artist in monitor.RS.artists)
    np.testing.assert_array_equal(raw, original)
    assert artist.get_array()[11, 158] == 0

    monitor.checkBox_roi1.setChecked(False)
    monitor.update_pilatus_image()
    assert 'checkBox_roi1' not in monitor._patches
    assert roi not in axes.patches


def test_autoscale_tracks_new_frames(monitor):
    monitor.update_pilatus_image()
    monitor._min = monitor._max = None
    monitor.update_pilatus_image()
    artist = monitor._image_artist
    assert artist.get_clim() == (0, 195 * 487 - 1)
    monitor.pilatus100k_device.image.array_data.value[:] = 17
    monitor.update_pilatus_image()
    assert artist.get_clim() == (0, 17)
    monitor._min = 3
    monitor.update_pilatus_image()
    assert artist.get_clim() == (3, 17)


def test_acquisition_callback_queues_to_gui_thread(monitor, qtbot):
    threads = []
    monitor.image_update_requested.connect(
        lambda: threads.append(QtCore.QThread.currentThread()),
        QtCore.Qt.QueuedConnection,
    )
    worker = threading.Thread(
        target=monitor.update_image_widget, kwargs={'value': 0, 'old_value': 1}
    )
    worker.start()
    worker.join()
    assert not threads
    qtbot.waitUntil(lambda: bool(threads))
    assert threads == [QtWidgets.QApplication.instance().thread()]
    with qtbot.assertNotEmitted(monitor.image_update_requested):
        monitor.update_image_widget(value=1, old_value=0)
