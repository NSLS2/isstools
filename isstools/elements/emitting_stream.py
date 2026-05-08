from qtpy import QtCore, QtGui
import sys


class EmittingStream(QtCore.QObject):
    textWritten = QtCore.Signal(str)

    # I think this code is writing a new subclass of stdout
    # (julien)
    def __init__(self, text_field, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_field = text_field

        self.buffer = sys.__stdout__.buffer
        self.close = sys.__stdout__.close
        self.closed = sys.__stdout__.closed
        self.detach = sys.__stdout__.detach
        self.encoding = sys.__stdout__.encoding
        self.errors = sys.__stdout__.errors
        self.fileno = sys.__stdout__.fileno
        self.flush = sys.__stdout__.flush
        self.isatty = sys.__stdout__.isatty
        self.line_buffering = sys.__stdout__.line_buffering
        self.mode = sys.__stdout__.mode
        self.name = sys.__stdout__.name
        self.newlines = sys.__stdout__.newlines
        self.read = sys.__stdout__.read
        self.readable = sys.__stdout__.readable
        self.readlines = sys.__stdout__.readlines
        self.seek = sys.__stdout__.seek
        self.seekable = sys.__stdout__.seekable
        # self.softspace = sys.__stdout__.softspace
        self.tell = sys.__stdout__.tell
        self.truncate = sys.__stdout__.truncate
        self.writable = sys.__stdout__.writable
        self.writelines = sys.__stdout__.writelines

        self.textWritten.connect(self.normalOutputWritten)

    def write(self, text):
        self.textWritten.emit(str(text))
        # Comment next line if the output should be printed only in the GUI
        sys.__stdout__.write(text)

    def normalOutputWritten(self, text):
        """Append text to the QtextEdit_terminal."""
        cursor = self.text_field.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)

        if text.find('0;3') >= 0:
            text = text.replace('<', '(')
            text = text.replace('>', ')')
            text = text.replace('[0m', '</font>')
            text = text.replace('[0;31m', '<font color=\"Red\">')
            text = text.replace('[0;32m', '<font color=\"Green\">')
            text = text.replace('[0;33m', '<font color=\"Yellow\">')
            text = text.replace('[0;34m', '<font color=\"Blue\">')
            text = text.replace('[0;36m', '<font color=\"Purple\">')
            text = text.replace('\n', '<br />')
            text += '<br />'
            cursor.insertHtml(text)
        elif text.lower().find('abort') >= 0 or text.lower().find('error') >= 0 or text.lower().find('invalid') >= 0:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.red)
            fmt.setFontWeight(QtGui.QFont.Bold)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
        elif (text.lower().find('starting') >= 0 or text.lower().find('launching')) >= 0:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.blue)
            fmt.setFontWeight(QtGui.QFont.Bold)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
        elif (text.lower().find('complete') >= 0 or text.lower().find('done') or text.lower().find('finished')) >= 0:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.darkGreen)
            fmt.setFontWeight(QtGui.QFont.Bold)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
        elif text.lower().find('storing') >= 0 or text.lower().find('moving') >= 0:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.darkGray)
            fmt.setFontWeight(QtGui.QFont.Bold)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
        else:
            fmt = cursor.charFormat()
            fmt.setForeground(QtCore.Qt.black)
            fmt.setFontWeight(QtGui.QFont.Normal)
            cursor.setCharFormat(fmt)
            cursor.insertText(text)

        self.text_field.setTextCursor(cursor)
        self.text_field.ensureCursorVisible()
