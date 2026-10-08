import ast
from pathlib import Path

from PyQt5 import uic
import pytest

import isstools
from isstools.resources import _load_json, load_json, resource_path


ROOT = Path(isstools.__file__).parent


def test_referenced_assets_exist():
    for source in ROOT.rglob('*.py'):
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'resource_path' and node.args
                    and isinstance(node.args[0], ast.Constant)):
                assert Path(resource_path(node.args[0].value)).is_file(), source


@pytest.mark.parametrize('name', [
    'ui/ui_pilatus.ui', 'ui/ui_run.ui', 'ui/ui_xlive.ui',
    'ui/ui_energy_selector.ui', 'elements/roi_widget.ui',
])
def test_ui_files_compile(name):
    uic.loadUiType(resource_path(name))


def test_json_is_cached_without_sharing_mutations():
    _load_json.cache_clear()
    first = load_json('edges_lines.json')
    expected_symbol = first[0]['symbol']
    first[0]['symbol'] = 'changed'
    second = load_json('edges_lines.json')
    assert second[0]['symbol'] == expected_symbol
    assert _load_json.cache_info().misses == 1
    assert _load_json.cache_info().hits == 1


def test_energy_selector(qtbot):
    from isstools.widgets.widget_energy_selector import UIEnergySelector

    widget = UIEnergySelector()
    qtbot.addWidget(widget)
    widget.comboBox_element.setCurrentText('Fe')
    widget.comboBox_edge.setCurrentText('K')
    assert int(widget.edit_E0.text()) == 7112
