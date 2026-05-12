
import json

import pkg_resources
from PyQt5 import uic
from isstools.dialogs import PeriodicTable
from redis_json_dict import RedisJSONDict

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_energy_selector_with_periodic_table.ui')
ui_path_without_e0 = pkg_resources.resource_filename('isstools', 'ui/ui_energy_selector_without_e0.ui')

ROOT_PATH_SHARED = '/nsls2/data/iss/legacy/xf08id'


class UIEnergySelectorWithPeriodicTable(*uic.loadUiType(ui_path)):
    def __init__(self, emission = None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        if emission:
           json_data = open(pkg_resources.resource_filename('isstools', 'fluorescence_lines.json')).read()
        else:
            json_data = open(pkg_resources.resource_filename('isstools', 'absorption_edges2.json')).read()
            self.label_edge_line.setText('Line')

        self.elements_data = json.loads(json_data)
        self.pushButton_element.pressed.connect(self.show_periodic_table)
        self.comboBox_edge.currentIndexChanged.connect(self.update_e0_value)


        self.update_combo_edge(self.pushButton_element.text())

    def get_energy_list(self, symbol):
        for element in self.elements_data:
            if element["symbol"] == symbol:
                return {k: v for k, v in element.items() if k not in ("symbol", "name")}
        return None

    def update_combo_edge(self, symbol):
        self.comboBox_edge.clear()
        self.energy_dict = self.get_energy_list(symbol)
        self.comboBox_edge.addItems(self.energy_dict.keys())

    def update_e0_value(self):
        if self.comboBox_edge.count() > 0:
            energy = self.energy_dict[self.comboBox_edge.currentText()]
            self.edit_E0.setText(str(int(energy)))

    def show_periodic_table(self):
        self.periodic_table_window = PeriodicTable.PeriodicTableWidget()
        self.periodic_table_window.element_selected.connect(self.set_element_from_table)
        self.periodic_table_window.show()

    def set_element_from_table(self, symbol):
        self.pushButton_element.setText(symbol)  # Set the button text
        self.update_combo_edge(symbol)




class UIEnergySelectorFoil(*uic.loadUiType(ui_path_without_e0)):
    def __init__(self, emission = None, redis_settings_client=None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.setupUi(self)
        if emission:
           json_data = open(pkg_resources.resource_filename('isstools', 'fluorescence_lines.json')).read()
        else:
            json_data = open(pkg_resources.resource_filename('isstools', 'edges_lines.json')).read()
            self.label_edge_line.setText('Line')

        self.elements_data = json.loads(json_data)
        self.comboBox_element.currentIndexChanged.connect(self.update_combo_edge)
        # self.comboBox_edge.currentIndexChanged.connect(self.update_e0_value)



        _foil_wheel_store = RedisJSONDict(redis_settings_client, prefix='foil_wheel')
        foil_info = _foil_wheel_store['foil_wheel']
        foils = [item['element'] for item in foil_info]

        self.elements_data = [item for item in self.elements_data if item['symbol'] in foils]

        elems = [item['symbol'] for item in self.elements_data]
        self.comboBox_element.addItems(elems)

    def update_combo_edge(self, index):
        self.comboBox_edge.clear()
        edges = [key for key, value in list(self.elements_data[index].items()) if key != 'name' and key != 'symbol' and value>4500]
        edges.sort()
        self.comboBox_edge.addItems(edges)

    @property
    def element(self):
        return self.comboBox_element.currentText()

    @property
    def edge(self):
        return self.comboBox_edge.currentText()

    @property
    def element_edge(self):
        return self.element, self.edge

    # def update_e0_value(self):
    #     if self.comboBox_edge.count() > 0:
    #         energy = self.elements_data[self.comboBox_element.currentIndex()][self.comboBox_edge.currentText()]


            # self.edit_E0.setText(str(int(energy)))