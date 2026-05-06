"""Test that every .ui file in this directory loads successfully with qtpy + PySide6.

Run with:
    pixi run python isstools/ui/test_ui_compat.py

The script must be executed through ``pixi run`` so that ``pyside6-uic`` (used
internally by ``qtpy.uic.loadUiType``) is available on PATH.
"""

import glob
import os
import sys

# Must be set before any Qt import.
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy import uic  # noqa: E402  (import after env-var setup)
from qtpy.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

ui_dir = os.path.dirname(os.path.abspath(__file__))
ui_files = sorted(glob.glob(os.path.join(ui_dir, "*.ui")))

passed = []
failed = []

for ui_file in ui_files:
    name = os.path.basename(ui_file)
    try:
        cls, base = uic.loadUiType(ui_file)
        print(f"OK    {name}")
        passed.append(name)
    except Exception as exc:
        print(f"FAIL  {name}: {exc}")
        failed.append((name, exc))

print()
print(f"Results: {len(passed)} passed, {len(failed)} failed out of {len(ui_files)} files.")

if failed:
    sys.exit(1)
