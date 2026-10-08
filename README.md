# isstools

PyQt5 GUI tools for running the ISS beamline at NSLS-II. The full application is
started from a beamline profile that supplies the RunEngine, devices, scan and
sample managers, database, and other services to `isstools.xlive.XliveGui`.

Use Python 3.10 or newer. PyQt5 remains the Qt binding; this update does not
migrate the application to Qt6.

## Installation

Create a separate environment before updating a deployed beamline environment:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m pip check
```

`requirements.txt` is the single source of public runtime dependencies, consumed
by `setup.py`. Ranges allow dependency updates within the indicated major
versions. Databroker stays on 1.x because the processing code uses its Header API;
pandas stays on 2.x pending validation of the external analysis stack with 3.x.
The old direct `slackclient` and `numexpr` requirements were removed: this repo
has no direct use of them. Cloud and analysis packages must declare their own
requirements.

The beamline must also provide its compatible **ISS `xas`** and
**`isscloudtools`** packages. Use the versions/checkouts from the beamline profile;
do not substitute an unrelated package named `xas` from PyPI. They are not
bundled here. The historical standalone Pilatus device definitions additionally
need `pip install -e '.[legacy-pilatus]'` for `nslsii`.

Qt requires native graphics libraries. QR decoding with `pyzbar` also requires
the native ZBar library (e.g. `libzbar0` on Debian/Ubuntu or `zbar` on AlmaLinux).
A desktop/X server is needed for interactive operation. Existing beamline paths,
credentials, EPICS configuration, and devices are still required for the full GUI.

## Development and validation

```sh
QT_QPA_PLATFORM=offscreen python -m pytest
python -m build
```

Tests exercise resource loading, Qt Designer forms, an energy selector, and the
Pilatus display using synthetic images without connecting to hardware. CI runs
these checks on Python 3.10 and 3.12. Built wheels include UI forms, JSON tables,
icons, and spectrometer images. Versioneer continues to derive versions from Git.

The detector display updates an existing Matplotlib image and ROI rectangles,
retaining zoom between frames and avoiding repeated axes/layout construction.
Dead-pixel display corrections operate on a copy of the detector data. Acquisition
callbacks request image updates through Qt's GUI thread. Scan plot redraws use
`draw_idle()` so Qt can combine pending redraw requests. Bundled JSON tables are
cached while callers receive independent copies.

A local Python 3.12 benchmark with synthetic 195-by-487 detector frames and one
ROI measured median Python frame-update time of 11.2 ms before and 0.14 ms after
the change over 30 updates. This excludes deferred canvas rendering and hardware
access; it is not a measurement of overall acquisition speed.

Before deploying an updated environment, validate full startup, acquisition,
ROI editing, scan plotting, processing, and cloud integrations with the beamline
profile. The headless tests do not validate hardware motion, external analysis
packages, or remote services. Capture the validated deployment with
`python -m pip freeze > beamline-environment.txt`.
