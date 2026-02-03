import json
import pkg_resources
from qtpy import uic
from isstools.elements.elements import elements_lines_dict
from ..elements.elements import get_spectrometer_line_dict

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_emission_energy_selector.ui')
ui_path_no_optics = pkg_resources.resource_filename('isstools', 'ui/ui_emission_energy_selector_no_optics.ui')
# ui_path_no_optics = pkg_resources.resource_filename('isstools', 'ui/ui_emission_energy_selector_no_optics.ui')
from xraydb import xray_line

class UIEmissionEnergySelector(*uic.loadUiType(ui_path)):
    def __init__(self, parent=None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.settings = parent.parent.parent.settings
        # json_data = open(pkg_resources.resource_filename('isstools', 'edges_lines.json')).read()
        # self.elements_data = json.loads(json_data)
        self.elements_data = elements_lines_dict
        elems = [k for k in self.elements_data.keys()]
        self.comboBox_element.addItems(elems)
        self.comboBox_element.setCurrentIndex(self.settings.value('johann_emission_element', defaultValue=0, type=int))

        self.update_combo_line(1)
        self.comboBox_line.setCurrentIndex(self.settings.value('johann_emission_line', defaultValue=0, type=int)) #

        self.update_e_value(save_settings=False)

        self.comboBox_element.currentIndexChanged.connect(self.update_combo_line)
        self.comboBox_line.currentIndexChanged.connect(self.update_e_value)

        self.comboBox_crystal_kind.setCurrentIndex(self.settings.value('johann_crystal_kind', defaultValue=1, type=int)) #
        self.lineEdit_reflection.setText(self.settings.value('johann_crystal_refl', defaultValue='(4,4,4)', type=str)) #

    def _save_johann_settings(self):
        element_index = self.comboBox_element.currentIndex()
        self.settings.setValue('johann_emission_element', element_index)
        line_index = self.comboBox_line.currentIndex()
        self.settings.setValue('johann_emission_line', line_index)
        energy_str = self.edit_E.text()
        self.settings.setValue('johann_emission_energy_nom', energy_str)
        crystal_kind_index = self.comboBox_crystal_kind.currentIndex()
        self.settings.setValue('johann_crystal_kind', crystal_kind_index)
        refl_str = self.lineEdit_reflection.text()
        self.settings.setValue('johann_crystal_refl', refl_str)

    def update_combo_line(self, index):
        self.comboBox_line.clear()
        cur_element = str(self.comboBox_element.currentText())
        if cur_element:
            lines = self.elements_data[cur_element]
            lines.sort()
            self.comboBox_line.addItems(lines)

    def update_e_value(self, save_settings=True):
        if self.comboBox_line.count() > 0:
            element = self.comboBox_element.currentText()
            line = self.comboBox_line.currentText()
            try:
                self.edit_E.setText(
                    str(xray_line(element, line).energy))
            except:
                pass

        if save_settings:
            self._save_johann_settings()


class UIEmissionEnergySelectorEnergyOnly(*uic.loadUiType(ui_path_no_optics)):
    def __init__(self, parent=None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.settings = parent.parent.settings
        # json_data = open(pkg_resources.resource_filename('isstools', 'edges_lines.json')).read()
        # self.elements_data = json.loads(json_data)
        self.elements_data = elements_lines_dict
        elems = [k for k in self.elements_data.keys()]
        self.comboBox_element.addItems(elems)
        self.comboBox_element.setCurrentIndex(self.settings.value('johann_emission_element', defaultValue=0, type=int))

        self.update_combo_line(None)
        self.comboBox_line.setCurrentIndex(self.settings.value('johann_emission_line', defaultValue=0, type=int)) #

        self.update_e_value(save_settings=False)

        self.comboBox_element.currentIndexChanged.connect(self.update_combo_line)
        self.comboBox_line.currentIndexChanged.connect(self.update_e_value)


    def _save_johann_settings(self):
        element_index = self.comboBox_element.currentIndex()
        self.settings.setValue('johann_emission_element', element_index)
        line_index = self.comboBox_line.currentIndex()
        self.settings.setValue('johann_emission_line', line_index)
        energy_str = self.edit_E.text()
        self.settings.setValue('johann_emission_energy_nom', energy_str)


    def update_combo_line(self, index):
        self.comboBox_line.clear()
        cur_element = str(self.comboBox_element.currentText())
        if cur_element:
            lines = self.elements_data[cur_element]
            lines.sort()
            self.comboBox_line.addItems(lines)

    def update_e_value(self, save_settings=True):
        if self.comboBox_line.count() > 0:
            element = self.comboBox_element.currentText()
            line = self.comboBox_line.currentText()
            try:
                self.edit_E.setText(
                    str(xray_line(element, line).energy))
            except:
                pass

        if save_settings:
            self._save_johann_settings()



class UIEmissionLineSelectorEnergyOnly(*uic.loadUiType(ui_path_no_optics)):
    def __init__(self, parent=None, emin=4500, emax=30000, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.settings = parent.parent.settings
        # json_data = open(pkg_resources.resource_filename('isstools', 'edges_lines.json')).read()
        # self.elements_data = json.loads(json_data)
        df = get_spectrometer_line_dict()
        self.elements_data = df
        elems = df[(df.energy > emin) & (df.energy < emax)].element.unique().tolist()
        self.comboBox_element.addItems(elems)
        self.comboBox_element.setCurrentIndex(self.settings.value('johann_emission_element', defaultValue=0, type=int))

        self.update_combo_line(None)
        self.comboBox_line.setCurrentIndex(self.settings.value('johann_emission_line', defaultValue=0, type=int)) #

        self.update_e_value(save_settings=False)

        self.comboBox_element.currentIndexChanged.connect(self.update_combo_line)
        self.comboBox_line.currentIndexChanged.connect(self.update_e_value)


    def _save_johann_settings(self):
        element_index = self.comboBox_element.currentIndex()
        self.settings.setValue('johann_emission_element', element_index)
        line_index = self.comboBox_line.currentIndex()
        self.settings.setValue('johann_emission_line', line_index)
        energy_str = self.edit_E.text()
        self.settings.setValue('johann_emission_energy_nom', energy_str)


    def update_combo_line(self, index):
        self.comboBox_line.clear()

        current_element = self.comboBox_element.currentText()
        df = self.elements_data
        lines = df[df.element == current_element].symbol.tolist()
        # lines.sort()
        self.comboBox_line.addItems(lines)

    def update_e_value(self, save_settings=True):
        if self.comboBox_line.count() > 0:
            current_element = self.comboBox_element.currentText()
            current_line = self.comboBox_line.currentText()
            try:
                df = self.elements_data
                energy = float(df[(df.element == current_element) & (df.symbol == current_line)].energy.values)
                self.edit_E.setText(f'{energy : .1f}')
            except:
                pass

        if save_settings:
            self._save_johann_settings()