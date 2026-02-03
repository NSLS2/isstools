import pkg_resources
from qtpy import uic, QtCore

from matplotlib.widgets import RectangleSelector, Cursor
from qtpy.Qt import QSplashScreen, QObject
from qtpy.QtWidgets import QToolTip, QApplication
from qtpy.QtGui import QPixmap, QCursor
from isstools.dialogs.BasicDialogs import message_box
# from isstools.elements.widget_motors import UIWidgetMotors
from functools import partial
from time import sleep
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
import matplotlib.patches as patches
import time as ttime
import sys
from isstools.elements.figure_update import update_figure

ui_path = '/home/xf08id/Repos/isstools/isstools/ui/ui_pilatus.ui'

# sys.path.append('/home/xf08id/.ipython/profile_collection/startup/')
# sys.path.append('/home/xf08id/Repos/xview/xview/')
# import importlib
#
# # PYTHONPATH=/nsls2/data/iss/shared/config/repos/isscloudtools:/nsls2/data/iss/shared/config/repos/issfactortools:/nsls2/data/iss/shared/config/repos/isstools:/nsls2/data/iss/shared/config/repos/piezo-feedback:/nsls2/data/iss/shared/config/repos/qmicroscope:/nsls2/data/iss/shared/config/repos/xas:/nsls2/data/iss/shared/config/repos/xsample:/nsls2/data/iss/shared/config/repos/xview:/nsls2/data/iss/shared/config/bluesky_overlays/2022-2.1-py39-tiled/lib/python3.9/site-packages
#
# from datetime import datetime
#
# importlib.import_module('00-startup', package='time_now_str')

class UIPilatusMonitor(*uic.loadUiType(ui_path)):
    def __init__(self,
                detector_dict=detector_dict,
                plan_processor=None,
                hhm=hhm,
                parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        # self.detector_dict = detector_dict
        # self.hhm = hhm


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = UIPilatusMonitor()
    main.show()

    sys.exit(app.exec_())