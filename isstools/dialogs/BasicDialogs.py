from qtpy import  QtWidgets

def message_box(title, message):
    messageBox = QtWidgets.QMessageBox()
    messageBox.setText(message)
    messageBox.addButton(QtWidgets.QPushButton('OK'), QtWidgets.QMessageBox.YesRole)
    messageBox.setWindowTitle(title)
    messageBox.exec_()

def error_message_box(message):
    messageBox = QtWidgets.QMessageBox()
    messageBox.setText(message)
    messageBox.addButton(QtWidgets.QPushButton('OK'), QtWidgets.QMessageBox.YesRole)
    messageBox.setWindowTitle('Error')
    messageBox.exec_()



def question_message_box(qwidget,title, question):
    reply = QtWidgets.QMessageBox.question(qwidget,title,
                                           question,
                                           QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
    if reply == QtWidgets.QMessageBox.Yes:
        return True
    elif reply == QtWidgets.QMessageBox.No:
        return False
    else:
        return False