import time
import random
import numpy as np

from qtpy.QtCore import Signal, QByteArray, QPoint, QPointF, QRect, QSize, QTimer, Qt, QObject, QUrl
from qtpy.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPolygon, QPen
from qtpy.QtWidgets import QWidget
from isstools.dialogs.BasicDialogs import message_box, question_message_box

from qtpy.QtNetwork import QNetworkRequest, QNetworkAccessManager

class Downloader(QObject):
    imageReady = Signal(QByteArray)

    def __init__(self, parent=None):
        super(Downloader, self).__init__(parent)
        self.manager = QNetworkAccessManager()
        self.url = 'http://localhost:9998/jpg/image.jpg'
        self.request = QNetworkRequest()
        self.request.setUrl(QUrl(self.url))
        self.buffer = QByteArray()
        self.reply = None

    def setUrl(self, url):
        self.url = url
        self.request.setUrl(QUrl(self.url))

    def downloadData(self):
        """ Only request a new image if this is the first/last completed. """
        if self.reply is None:
            self.reply = self.manager.get(self.request)
            self.reply.finished.connect(self.finished)

    def finished(self):
        """ Read the buffer, emit a signal with the new image in it. """
        self.buffer = self.reply.readAll()
        self.imageReady.emit(self.buffer)
        self.reply.deleteLater()
        self.reply = None


# class CustomQPoint(QPoint):
#
#     @property
#     def xy(self):
#         return self.x(), self.y()

class CustomQPolygon(QPolygon):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dragging_index = None
        self.dragging_whole = None
        self.whole_ref_point = None

    def distance_to_vertices(self, point : QPoint):

        if self.count() == 0:
            return None

        x, y = point.x(), point.y()

        dist = []
        for i in range(self.count()):
            point_i = self.at(i)
            x_i, y_i = point_i.x(), point_i.y()
            dist_i = np.sqrt((x - x_i) ** 2 + (y - y_i) ** 2)
            dist.append(dist_i)

        return np.array(dist)

    def closest_point_index(self, point : QPoint, margin=30):
        dist = self.distance_to_vertices(point)
        if dist is not None:
            idx = dist.argmin()
            val = dist.min()
            if val < margin:
                return idx

        return None

    def closest_point(self, point):
        index = self.closest_point_index(point)
        if index is not None:
            return self.at(index)
        return None

    def close_to_center(self, point):
        x = point.x()
        y = point.y()

        rect = self.boundingRect()
        cen = rect.center()
        x_cen = cen.x()
        y_cen = cen.y()
        rx = rect.width() / 4
        ry = rect.height() / 4

        dist = np.sqrt(((x - x_cen) / rx)**2 + ((y - y_cen) / ry)**2)

        return (dist < 1) or None

    def start_drag(self, point):
        if self.dragging_index is None:
            self.dragging_index = self.closest_point_index(point)
        if self.dragging_index is None:
            if self.dragging_whole is None:
                self.dragging_whole = self.close_to_center(point)
                self.whole_ref_point = point

    def drag(self, point):
        if self.dragging_index is not None:
            self.drag_point(point)
            return

        if self.dragging_whole is not None:
            self.drag_whole(point)
            return

    def drag_point(self, point):
        print(self.dragging_index)
        self.setPoint(self.dragging_index, point)

    def drag_whole(self, point):
        dx = point.x() - self.whole_ref_point.x()
        dy = point.y() - self.whole_ref_point.y()
        self.translate(dx, dy)
        self.whole_ref_point = point

    def stop_drag(self):
        self.dragging_index = None
        self.dragging_whole = None
        self.whole_ref_point = None

    def remove_point(self, point):
        remove_index = self.closest_point_index(point)
        print(remove_index)
        if remove_index is not None:
            self.remove(remove_index)

    @property
    def coordinate_list(self):
        output = []
        for i in range(self.count()):
            output.append([self.at(i).x(), self.at(i).y()])
        return output

class Microscope(QWidget):
    roiClicked = Signal(int, int)
    # polygonDrawingSignal = Signal(QPoint)
    doubleClickSignal = Signal(list)

    def __init__(self, parent=None, mark_direction = 1, camera=None, url=None, fps=10, scale_width=600):
        #mark_direction = 0 for horizontal, 1 for vertical
        super(Microscope, self).__init__(parent)
        self.parent_gui = parent
        self.camera = camera
        self.setMinimumWidth(300)
        self.setMinimumHeight(300)
        self.image = QImage('image.jpg')

        # self.clicks = []
        self.center = QPoint(
            int(self.image.size().width() / 2), int(self.image.size().height() / 2)
        )
        self.mark_direction = mark_direction
        self.mark_location = QPoint(int(self.camera.beam_pos_x),
                                    int(self.camera.beam_pos_y))
        # self.mark_location = QPoint(self.parent_gui.settings.value('beam_position_x', defaultValue=600, type=float),
        #                             self.parent_gui.settings.value('beam_position_y', defaultValue=450, type=float))
        self.mark_location_set = True
        self.color = False


        # self.scaleBar = False

        self.scale_width = scale_width
        self.url = url
        self.fps = fps

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateImage)

        self.downloader = Downloader(self)
        self.downloader.imageReady.connect(self.updateImageData)

        self.sample_polygon = CustomQPolygon()

        self.draw_calibration_grid = False
        self.draw_sample_points = False

        def _func(image):
            return image

        self.external_func = _func

    @property
    def mode(self):
        # return self.parent().parent().interaction_mode
        return self.parent_gui.interaction_mode

    def reset_sample_polygon(self):
        r = self.sample_polygon
        self.sample_polygon = CustomQPolygon()
        del r

    def convertxy_nom2act(self, x, y):
        return (x / self.scale_width * self.camera.image_width,
                y / self.scale_width * self.camera.image_width)

    def convertxy_act2nom(self, x, y):
        return (int(x * self.scale_width / self.camera.image_width),
                int(y * self.scale_width / self.camera.image_width))

    def updatedImageSize(self):
        if self.image.size() != self.minimumSize():
            self.setMinimumSize(self.image.size())
            self.center = QPoint(
                int(self.image.size().width() / 2), int(self.image.size().height() / 2)
            )

    def acquire(self, start=True):
        self.downloader.setUrl(self.url)
        if start:
            self.timer.start(int(1000.0 / self.fps))
        else:
            self.timer.stop()

    def paintEvent(self, event):
        # tic = time.perf_counter()
        painter = QPainter(self)
        rect = event.rect()
        # self.image = self.image.scaledToWidth(200)
        painter.drawImage(rect, self.image, rect, flags=Qt.ThresholdDither)

        # painter.setPen(QColor.fromRgb(0, 255, 0))
        painter.setPen(QColor('yellow'))

        if self.mark_location:
            #print(f' Mark location {self.mark_location.x()} -  {self.mark_location.y()}')
            beam_pos_x, beam_pos_y = self.convertxy_act2nom(self.camera.beam_pos_x, self.camera.beam_pos_y)
            if self.mark_direction == 1:
                #painter.drawLine(beam_pos_x - 25, beam_pos_y,
                #                 beam_pos_x + 25, beam_pos_y)
                painter.drawLine(beam_pos_x, beam_pos_y - 200,
                                 beam_pos_x, beam_pos_y + 200)

            elif self.mark_direction == 0:
                #painter.drawLine(beam_pos_x,       beam_pos_y - 25,
                #                 beam_pos_x,       beam_pos_y + 25)
                painter.drawLine(beam_pos_x - 200, beam_pos_y,
                                 beam_pos_x + 200, beam_pos_y)

        painter.setPen(QColor.fromRgb(0, 255, 0))
        painter.drawPolygon(self.sample_polygon)

        # draw sample_points
        if self.draw_sample_points:
            xy = self.compute_sample_xy_coords()
            if xy is not None:
                pen = QPen(QColor.fromRgb(0, 255, 0))
                pen.setWidth(3)
                painter.setPen(pen)
                for _x, _y in xy:
                    x, y = self.convertxy_act2nom(_x, _y)
                    painter.drawPoint(x, y)
                pen.setWidth(1)


        # draw calibration
        if self.draw_calibration_grid:
            painter.setPen(QColor.fromRgb(0, 0, 255))
            if self.camera.grid_lines is not None:
                for line in self.camera.grid_lines:
                    for i in range(len(line) - 1):
                        x1, y1 = self.convertxy_act2nom(*line[i])
                        x2, y2 = self.convertxy_act2nom(*line[i+1])
                        painter.drawLine(x1, y1, x2, y2)

    def compute_sample_xy_coords(self):
        motxy = self.parent_gui.sample_manager_xy_coords
        if motxy is not None:
            xy = self.camera.compute_point_from_stage(*motxy)
            return xy
        return None


    def mark_beam_location(self, pos):
        if self.mark_location_set:
            ret = question_message_box(self, 'Warning', 'Do you want to redefine beam location mark')
            if not ret:
                return
        self.roiClicked.emit(pos.x(), pos.y())
        self.mark_location = pos
        self.mark_location_set = True
        self.camera.set_beam_coordinates(*self.convertxy_nom2act(self.mark_location.x(), self.mark_location.y()))

        # if self.mark_direction == 1:
            # self.parent_gui.settings.setValue('beam_position_x', self.mark_location.x())
        # elif self.mark_direction == 0:
            # self.parent_gui.settings.setValue('beam_position_y', self.mark_location.y())

    def mousePressEvent(self, event):
        print('MOUSE PRESS EVENT')
        pos = event.pos()

        if event.button() == Qt.LeftButton:
            if self.mode == 'draw':
                self.sample_polygon.append(pos)

        elif event.button() == Qt.RightButton:
            if self.mode == 'default':
                self.mark_beam_location(pos)
            elif self.mode == 'draw':
                self.sample_polygon.start_drag(pos)

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self.mode == 'draw':
            self.sample_polygon.drag(pos)

    def mouseReleaseEvent(self, event):
        pos = event.pos()
        if event.button() == Qt.RightButton:
            if self.mode == 'draw':
                self.sample_polygon.stop_drag()

    def mouseDoubleClickEvent(self, event):
        print('MOUSE DOUBLE CKICK EVENT')
        pos = event.pos()
        x, y = self.convertxy_nom2act(pos.x(), pos.y())

        if event.button() == Qt.LeftButton:
            if self.mode == 'default':
                motx, moty = self.camera.compute_stage_motion_to_beam(x, y).squeeze()
                self.doubleClickSignal.emit([motx, moty])


    @property
    def sample_polygon_motor(self):
        coords = np.array([list(self.convertxy_nom2act(*coord)) for coord in self.sample_polygon.coordinate_list])
        polygon_motor = self.camera.compute_stage_motion_to_beam(coords[:, 0], coords[:, 1]).squeeze()
        return polygon_motor

    #     # print(event, event.button())
    #
    #     print(f'actual coordinates: {x, y}')
    #     motx, moty = self.camera.compute_stage_motion_to_beam(x, y).squeeze()
    #     print(f'stage shifts: {motx, moty}')
    #     self.sample_stage.mvr({'x' : motx, 'y' : moty})
        # if event.button() == Qt.LeftButton:
        #     if self.mode == 'calibration':
        #         self.calibration_polygon.remove_point(pos)


    def sizeHint(self):
        return QSize(400, 400)

    def updateImage(self):
        """ Request an updated image asynchronously. """
        self.downloader.downloadData()


    def updateImageData(self, image):
        """ Triggered when the new image is ready, update the view. """
        # print(f"-----------------------------{type(image)}-------------------------------------")
        # self.image_qbytearray = image
        self.image.loadFromData(image, 'JPG')
        self.image = self.image.scaledToWidth(self.scale_width)


        # for i in range(self.image.size().width()):
        #     for j in range(self.image.size().height()):
        #         _c = self.image.pixelColor(i, j).value()
        #         if _c > 50:
        #             self.image.setPixelColor(i, j, QColor(50))


        self.updatedImageSize()
        self.image = self.external_func(self.image)
        self.update()

    def readFromDict(self, settings):
        """ Read the settings from a Python dict. """
        if settings.has_key('url'):
            self.url = settings['url']
        if settings.has_key('fps'):
            self.fps = settings['fps']
        if settings.has_key('xDivs'):
            self.xDivs = settings['xDivs']
        if settings.has_key('yDivs'):
            self.yDivs = settings['yDivs']
        if settings.has_key('color'):
            self.color = settings['color']

    def writeToDict(self):
        """ Write the widget's settings to a Python dict. """
        settings = {
            'url': self.url,
            'fps': self.fps,
            'xDivs': self.xDivs,
            'yDivs': self.yDivs,
            'color': self.color
        }
        return settings

    def readSettings(self, settings):
        """ Read the settings for this microscope instance. """
        self.url = settings.value('url', 'http://localhost:9998/jpg/image.jpg')
        self.fps = settings.value('fps', 5, type=int)
        self.xDivs = settings.value('xDivs', 5, type=int)
        self.yDivs = settings.value('yDivs', 5, type=int)
        self.color = settings.value('color', False, type=bool)

    def writeSettings(self, settings):
        """ Write the settings for this microscope instance. """
        settings.setValue('url', self.url)
        settings.setValue('fps', self.fps)
        settings.setValue('xDivs', self.xDivs)
        settings.setValue('yDivs', self.yDivs)
        settings.setValue('color', self.color)

    def saveImageAsFile(self, filepath):
        _image = self.image
        if self.mark_location:
            #print(f' Mark location {self.mark_location.x()} -  {self.mark_location.y()}')
            beam_pos_x, beam_pos_y = self.convertxy_act2nom(self.camera.beam_pos_x, self.camera.beam_pos_y)
            if self.mark_direction == 1:
                x1, y1 = beam_pos_x, beam_pos_y - 200
                x2, y2 = beam_pos_x, beam_pos_y + 200

            elif self.mark_direction == 0:
                x1, y1 = beam_pos_x - 200, beam_pos_y
                x2, y2 = beam_pos_x + 200, beam_pos_y
        painter = QPainter(_image)
        pen = QPen(Qt.yellow, 1)  # Yellow color, 3px thick line
        painter.setPen(pen)
        painter.drawLine(x1, y1, x2, y2)
        painter.end()
        _image.save(filepath, "JPEG", quality=95)


