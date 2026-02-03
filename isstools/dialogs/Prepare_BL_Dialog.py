from qtpy import uic, QtGui, QtCore, QtWidgets
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/Prepare_BL_Dialog.ui')

class PrepareBLDialog(*uic.loadUiType(ui_path)):

    def __init__(self, curr_energy, dic_info, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Prepare BL')

        beamline_prep = dic_info[0]
        fb_positions = dic_info[1]['FB Positions']

        curr_range = [ran for ran in beamline_prep if ran['energy_end'] > curr_energy and ran['energy_start'] <= curr_energy][0]

        self.label_en_range.setText('{} <= {:.2f} < {}'.format(curr_range['energy_start'], curr_energy, curr_range['energy_end']))
        self.label_ic_gas_he.setText('{}'.format(curr_range['pvs']['IC Gas He']['value']))
        self.label_ic_gas_n2.setText('{}'.format(curr_range['pvs']['IC Gas N2']['value']))
        self.label_i0_voltage.setText('{}'.format(curr_range['pvs']['I0 Voltage']['value']))
        self.label_it_voltage.setText('{}'.format(curr_range['pvs']['It Voltage']['value']))
        self.label_ir_voltage.setText('{}'.format(curr_range['pvs']['Ir Voltage']['value']))
        self.label_fb_pos.setText('{}'.format(curr_range['pvs']['Filterbox Pos']['value']))
        self.label_hhrm_hor_trans.setText('{}'.format(curr_range['pvs']['HHRM Hor Trans']['value']))

        for index, bpm in enumerate(curr_range['pvs']['BPMs']):
            label = QtWidgets.QLabel(bpm['name'])
            pol = label.sizePolicy()
            pol.setHorizontalPolicy(QtWidgets.QSizePolicy.Maximum)
            self.gridLayout_2.addWidget(label, index + 1, 0)
            label = QtWidgets.QLabel(bpm['value'])
            pol = label.sizePolicy()
            pol.setHorizontalPolicy(QtWidgets.QSizePolicy.Maximum)
            self.gridLayout_2.addWidget(label, index + 1, 1)

