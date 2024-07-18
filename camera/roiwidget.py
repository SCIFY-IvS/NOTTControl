from PyQt5.QtWidgets import QWidget
from PyQt5.uic import loadUi
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QFrame
from camera.utils.utils import BrightnessResults

class RoiWidget(QWidget):
    def __init__(self, parent, index: int, color : QColor):
        QWidget.__init__(self, parent)

        self.ui = loadUi('camera/roiwidget.ui', self)
        self.ui.label.setText(f'ROI {index}')
        frame = self.frame_roiul
        frame.setFrameShape(QFrame.Panel)
        frame.setLineWidth(2)
        frame.setMidLineWidth(3)

        self.setColor(color)

    def setColor(self, color):
        pal = self.label.palette()
        pal.setColor(QPalette.WindowText, color)
        self.label.setPalette(pal)
    
    def setValues(self, brightnessResults: BrightnessResults):
        self.ui.lineEdit_roi1_min.setText(f'{brightnessResults.min:.2f}')
        self.ui.lineEdit_roi1_max.setText(f'{brightnessResults.max:.2f}')
        self.ui.lineEdit_roi1_avg.setText(f'{brightnessResults.avg:.2f}')
    
    def isChecked(self):
        return self.ui.checkBox_ROI1.isChecked()