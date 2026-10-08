import os

# Qt widgets and Matplotlib can be exercised without an X server or hardware.
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MPLBACKEND', 'QtAgg')
