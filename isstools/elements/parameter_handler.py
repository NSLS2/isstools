import inspect
import re
from qtpy import QtWidgets


def create_parameter(description, annotation, units=None):

    qitem = None
    qlabel = None
    def_val = ''

    if description.find('=') != -1:
        def_val = re.sub(r'.*=', '', description)
    if annotation == int:
        qitem = QtWidgets.QSpinBox()
        qitem.setMaximum(100000)
        qitem.setMinimum(-100000)
        def_val = int(def_val)
        qitem.setValue(def_val)
    elif annotation == float:
        qitem = QtWidgets.QDoubleSpinBox()
        qitem.setMaximum(100000)
        qitem.setMinimum(-100000)
        def_val = float(def_val)
        qitem.setValue(def_val)
    elif annotation == bool:
        qitem = QtWidgets.QCheckBox()
        # if def_val == 'True':
        if 'True' in def_val:
            def_val = True
        else:
            def_val = False
        qitem.setCheckState(def_val)
        qitem.setTristate(False)
    elif annotation == str:
        qitem = QtWidgets.QLineEdit()
        def_val = str(def_val)
        qitem.setText(def_val)

    if qitem is not None:
        qlabel = QtWidgets.QLabel(description)

    return qitem, qlabel


def parse_plan_parameters(plan_func):


    parameter_values = []
    parameter_descriptions = []
    parameter_types = []

    signature = inspect.signature(plan_func)
    for i in range(0, len(signature.parameters)):

        description = re.sub(r':.*?=', '=', str(signature.parameters[list(signature.parameters)[i]]))
        if description == str(signature.parameters[list(signature.parameters)[i]]):
            description = re.sub(r':.*', '', str(signature.parameters[list(signature.parameters)[i]]))
        parameter_type = signature.parameters[list(signature.parameters)[i]].annotation
        parameter_value, parameter_description = create_parameter(description, parameter_type)

        if parameter_value:
            parameter_values.append(parameter_value)
            parameter_descriptions.append(parameter_description)
            parameter_types.append(parameter_type)

    return parameter_values, parameter_descriptions, parameter_types


def return_parameters_from_widget(parameter_descriptions, parameter_values, parameter_types):
    parameters = {}
    for i in range(len(parameter_values)):
        if parameter_types[i] == int:
            parameters[parameter_descriptions[i].text().split('=')[0]] = parameter_values[i].value()
        elif parameter_types[i] == float:
            parameters[parameter_descriptions[i].text().split('=')[0]] = parameter_values[i].value()
        elif parameter_types[i] == bool:
            parameters[parameter_descriptions[i].text().split('=')[0]] = bool(parameter_values[i].checkState())
        elif parameter_types[i] == str:
            parameters[parameter_descriptions[i].text().split('=')[0]] = parameter_values[i].text()
    return parameters