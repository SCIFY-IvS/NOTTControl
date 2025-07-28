from PyQt5.QtWidgets import QWidget
from PyQt5.uic import loadUi
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QFrame
from nottcontrol.camera.utils.utils import BrightnessResults
from nottcontrol.camera.roi import Roi
import pyqtgraph as pg
from collections import deque

class RoiWidget(QWidget):
    def __init__(self, parent, index: int, color : QColor, deque_length = 6000):
        QWidget.__init__(self, parent)

        self.ui = loadUi('camera/roiwidget.ui', self)
        self.name = f'ROI {index}'
        self.db_key = f'roi{index}'
        self.ui.label.setText(self.name)
        frame = self.frame_roiul
        frame.setFrameShape(QFrame.Panel)
        frame.setLineWidth(2)
        frame.setMidLineWidth(3)

        self.setColor(color)

        self.max_values = deque(maxlen = deque_length)

    def setColor(self, color):
        self.color = color
        pal = self.label.palette()
        pal.setColor(QPalette.WindowText, color)
        self.label.setPalette(pal)
    
    def setValues(self, brightnessResults: BrightnessResults):
        self.ui.lineEdit_roi1_min.setText(f'{brightnessResults.min:.2f}')
        self.ui.lineEdit_roi1_max.setText(f'{brightnessResults.max:.2f}')
        self.ui.lineEdit_roi1_avg.setText(f'{brightnessResults.avg:.2f}')
    
    def isChecked(self):
        return self.ui.checkBox_ROI1.isChecked()
    
    def setConfig(self, config: Roi):
        self.config = config
    
    def createRoi(self):
        self.roi = pg.RectROI([self.config.x, self.config.y], [self.config.w, self.config.h], pen = self.color)
        return self.roi

    def updateRoi_from_config(self):
        self.roi.setPos([self.config.x, self.config.y])
        self.roi.setSize([self.config.w, self.config.h])
    
    def clear_max_values(self):
        self.max_values.clear()
    
    def add_max_value(self, value):
        self.max_values.appendleft(value)