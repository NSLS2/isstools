from PyQt5 import uic, QtGui, QtCore
import pkg_resources
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QPushButton, QLabel

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/PeriodicTable.ui')

from PyQt5 import uic, QtGui, QtCore
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QMainWindow
from PyQt5.QtCore import pyqtSignal



class ElementLabel(QLabel):

    accessible_elements =[
        'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
        'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr',
        'Rb', 'Sr', 'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',
        'In', 'Sn', 'Sb', 'Te', 'I', 'Xe',
        'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho',
        'Er', 'Tm', 'Yb', 'Lu',
        'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg',
        'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn',
        'Fr', 'Ra', 'Ac', 'Th', 'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm', 'Bk', 'Cf'
    ]


    category_colors = {
        'Alkali metals': '#FF6666',
        'Alkaline earth metals': '#FFDEAD',
        'Transition metals': '#FFD700',
        'Post-transition metals': '#CCCCCC',
        'Metalloids': '#ADEAEA',
        'Reactive nonmetals': '#9AFF9A',
        'Noble gases': '#B0E0E6',
        'Lanthanides': '#FFA07A',
        'Actinides': '#DA70D6',
        'Unknown properties': '#D3D3D3',
    }
    """Custom QLabel to handle mouse clicks and store element data."""
    def __init__(self, symbol, category, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol = symbol  # Store the element symbol

        self.setAlignment(QtCore.Qt.AlignCenter)  # Center the text
        font = QtGui.QFont('Arial', 12)

        if symbol in self.accessible_elements:
            font.setBold(True)  # Make the font bold for accessible elements
            self.setStyleSheet("color: black;")  # Set the text color to black for emphasis
        else:
            font.setBold(False)  # Regular font for non-accessible elements
            self.setStyleSheet("color: darkgray;")  # Set dark gray text color

        self.setFont(font)  # Apply the font settings

        # Set the background color based on the element's category

        color = self.category_colors.get(category, '#FFFFFF')
        self.setStyleSheet(self.styleSheet() + f' background-color: {color}; border: 1px solid black;')

        self.setText(self.symbol)  # Set the symbol as the text
        self.setFixedSize(40, 40)  # Set a fixed size for each label
        #qiotself.setFont(QtGui.QFont('Arial', 12))

    def mousePressEvent(self, event):
        """Handle the mouse click event on an element."""
        if event.button() == QtCore.Qt.LeftButton:
            self.element_clicked(self.symbol)

    def element_clicked(self, symbol):
        """Callback for when an element is clicked."""
        print(f"Element clicked: {symbol}")
        # You can replace this with any other function, e.g., show element details


class PeriodicTableWidget(*uic.loadUiType(ui_path)):
    element_selected = pyqtSignal(str)

    elements = {
        # Main table
        1: (0, 0, 'H', 'Reactive nonmetals'), 2: (0, 17, 'He', 'Noble gases'),
        3: (1, 0, 'Li', 'Alkali metals'), 4: (1, 1, 'Be', 'Alkaline earth metals'), 5: (1, 12, 'B', 'Metalloids'),
        6: (1, 13, 'C', 'Reactive nonmetals'), 7: (1, 14, 'N', 'Reactive nonmetals'),
        8: (1, 15, 'O', 'Reactive nonmetals'),
        9: (1, 16, 'F', 'Reactive nonmetals'), 10: (1, 17, 'Ne', 'Noble gases'),
        11: (2, 0, 'Na', 'Alkali metals'), 12: (2, 1, 'Mg', 'Alkaline earth metals'),
        13: (2, 12, 'Al', 'Post-transition metals'),
        14: (2, 13, 'Si', 'Metalloids'), 15: (2, 14, 'P', 'Reactive nonmetals'), 16: (2, 15, 'S', 'Reactive nonmetals'),
        17: (2, 16, 'Cl', 'Reactive nonmetals'), 18: (2, 17, 'Ar', 'Noble gases'),
        19: (3, 0, 'K', 'Alkali metals'), 20: (3, 1, 'Ca', 'Alkaline earth metals'),
        21: (3, 2, 'Sc', 'Transition metals'),
        22: (3, 3, 'Ti', 'Transition metals'), 23: (3, 4, 'V', 'Transition metals'),
        24: (3, 5, 'Cr', 'Transition metals'),
        25: (3, 6, 'Mn', 'Transition metals'), 26: (3, 7, 'Fe', 'Transition metals'),
        27: (3, 8, 'Co', 'Transition metals'),
        28: (3, 9, 'Ni', 'Transition metals'), 29: (3, 10, 'Cu', 'Transition metals'),
        30: (3, 11, 'Zn', 'Transition metals'),
        31: (3, 12, 'Ga', 'Post-transition metals'), 32: (3, 13, 'Ge', 'Metalloids'), 33: (3, 14, 'As', 'Metalloids'),
        34: (3, 15, 'Se', 'Reactive nonmetals'), 35: (3, 16, 'Br', 'Reactive nonmetals'),
        36: (3, 17, 'Kr', 'Noble gases'),
        37: (4, 0, 'Rb', 'Alkali metals'), 38: (4, 1, 'Sr', 'Alkaline earth metals'),
        39: (4, 2, 'Y', 'Transition metals'),
        40: (4, 3, 'Zr', 'Transition metals'), 41: (4, 4, 'Nb', 'Transition metals'),
        42: (4, 5, 'Mo', 'Transition metals'),
        43: (4, 6, 'Tc', 'Transition metals'), 44: (4, 7, 'Ru', 'Transition metals'),
        45: (4, 8, 'Rh', 'Transition metals'),
        46: (4, 9, 'Pd', 'Transition metals'), 47: (4, 10, 'Ag', 'Transition metals'),
        48: (4, 11, 'Cd', 'Transition metals'),
        49: (4, 12, 'In', 'Post-transition metals'), 50: (4, 13, 'Sn', 'Post-transition metals'),
        51: (4, 14, 'Sb', 'Metalloids'),
        52: (4, 15, 'Te', 'Metalloids'), 53: (4, 16, 'I', 'Reactive nonmetals'), 54: (4, 17, 'Xe', 'Noble gases'),
        55: (5, 0, 'Cs', 'Alkali metals'), 56: (5, 1, 'Ba', 'Alkaline earth metals'), 57: (5, 2, 'La', 'Lanthanides'),
        72: (5, 3, 'Hf', 'Transition metals'), 73: (5, 4, 'Ta', 'Transition metals'),
        74: (5, 5, 'W', 'Transition metals'),
        75: (5, 6, 'Re', 'Transition metals'), 76: (5, 7, 'Os', 'Transition metals'),
        77: (5, 8, 'Ir', 'Transition metals'),
        78: (5, 9, 'Pt', 'Transition metals'), 79: (5, 10, 'Au', 'Transition metals'),
        80: (5, 11, 'Hg', 'Transition metals'),
        81: (5, 12, 'Tl', 'Post-transition metals'), 82: (5, 13, 'Pb', 'Post-transition metals'),
        83: (5, 14, 'Bi', 'Post-transition metals'),
        84: (5, 15, 'Po', 'Metalloids'), 85: (5, 16, 'At', 'Metalloids'), 86: (5, 17, 'Rn', 'Noble gases'),
        87: (6, 0, 'Fr', 'Alkali metals'), 88: (6, 1, 'Ra', 'Alkaline earth metals'), 89: (6, 2, 'Ac', 'Actinides'),
        104: (6, 3, 'Rf', 'Transition metals'), 105: (6, 4, 'Db', 'Transition metals'),
        106: (6, 5, 'Sg', 'Transition metals'),
        107: (6, 6, 'Bh', 'Transition metals'), 108: (6, 7, 'Hs', 'Transition metals'),
        109: (6, 8, 'Mt', 'Unknown properties'),
        110: (6, 9, 'Ds', 'Unknown properties'), 111: (6, 10, 'Rg', 'Unknown properties'),
        112: (6, 11, 'Cn', 'Unknown properties'),
        113: (6, 12, 'Nh', 'Unknown properties'), 114: (6, 13, 'Fl', 'Unknown properties'),
        115: (6, 14, 'Mc', 'Unknown properties'),
        116: (6, 15, 'Lv', 'Unknown properties'), 117: (6, 16, 'Ts', 'Unknown properties'),
        118: (6, 17, 'Og', 'Unknown properties'),

        # Lanthanides (excluding La) in separate row
        58: (8, 0, 'Ce', 'Lanthanides'), 59: (8, 1, 'Pr', 'Lanthanides'), 60: (8, 2, 'Nd', 'Lanthanides'),
        61: (8, 3, 'Pm', 'Lanthanides'), 62: (8, 4, 'Sm', 'Lanthanides'), 63: (8, 5, 'Eu', 'Lanthanides'),
        64: (8, 6, 'Gd', 'Lanthanides'), 65: (8, 7, 'Tb', 'Lanthanides'), 66: (8, 8, 'Dy', 'Lanthanides'),
        67: (8, 9, 'Ho', 'Lanthanides'), 68: (8, 10, 'Er', 'Lanthanides'), 69: (8, 11, 'Tm', 'Lanthanides'),
        70: (8, 12, 'Yb', 'Lanthanides'), 71: (8, 13, 'Lu', 'Lanthanides'),

        # Actinides (excluding Ac) in separate row
        90: (9, 0, 'Th', 'Actinides'), 91: (9, 1, 'Pa', 'Actinides'), 92: (9, 2, 'U', 'Actinides'),
        93: (9, 3, 'Np', 'Actinides'), 94: (9, 4, 'Pu', 'Actinides'), 95: (9, 5, 'Am', 'Actinides'),
        96: (9, 6, 'Cm', 'Actinides'), 97: (9, 7, 'Bk', 'Actinides'), 98: (9, 8, 'Cf', 'Actinides'),
        99: (9, 9, 'Es', 'Actinides'), 100: (9, 10, 'Fm', 'Actinides'), 101: (9, 11, 'Md', 'Actinides'),
        102: (9, 12, 'No', 'Actinides'), 103: (9, 13, 'Lr', 'Actinides'),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        self.setWindowTitle("Periodic Table")
        self.push_close.clicked.connect(self.close)
        self.init_table()

    def init_table(self):
        for _, (row, col, symbol, category) in self.elements.items():
            label = ElementLabel(symbol, category)
            label.element_clicked = self.handle_element_click  # Connect click handler
            self.gridLayout_periodic_table.addWidget(label, row, col)
        self.accessible_elements = label.accessible_elements

    def handle_element_click(self, symbol):
        if symbol in self.accessible_elements:
            self.element_selected.emit(symbol)  # Emit signal
            self.close()