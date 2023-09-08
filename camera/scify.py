# This Python file uses the following encoding: utf-8
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QApplication
from PyQt5.uic import loadUi

import sys
import time
import threading
import os
from datetime import datetime, timedelta
import ctypes,_ctypes
import pyqtgraph as pg
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtWidgets import (QPushButton,QGridLayout,QCheckBox,
                             QWidget,
                             QComboBox,QLabel,QLineEdit,QFrame,
                             )
from PyQt5.QtWidgets import QFileDialog
from .infratec_interface import InfratecInterface, Image

import numpy
from .brightness_calculator import BrightnessCalculator
from .roi_filewriter import ROIFileWriter
from .parametersdialog import ParametersDialog
from redisclient import RedisClient

from configparser import ConfigParser

t=time.perf_counter()
tLive=t

img_timestamp_ref = None

def callback(context,*args):#, aHandle, aStreamIndex):
    global img_timestamp_ref
    if img_timestamp_ref is None:
        recording_timestamp = datetime.utcnow()
    else:
        recording_timestamp = None
    
    context.load_image(recording_timestamp)

class MainWindow(QMainWindow):
    #Without this call, the GUI is resized and tiny
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    request_image_update = pyqtSignal(numpy.ndarray)
    roi_calculation_finished = pyqtSignal(BrightnessCalculator)
    
    def __init__(self):
        super(MainWindow, self).__init__()
        self.interface = InfratecInterface()
        pg.setConfigOptions(imageAxisOrder='row-major')
        
        self.ui = loadUi('camera/mainwindow.ui', self)
        self.connectSignalSlots()
        
        self.connected = False
        self.recording = False
        self.triggerEnabled = False
        
        self.image=pg.ImageView(self.ui.frame_camera)
        self.image.ui.histogram.hide()
        self.image.ui.roiBtn.hide()
        self.image.ui.menuBtn.hide()
        self.image.show()
        self.imageInit = False
        
        self.image.getView().setMouseEnabled(x = False, y = False)
        self.image.getView().disableAutoRange()
        
        self.request_image_update.connect(self.update_image)
        self.roi_calculation_finished.connect(self.on_roi_calculations_finished)
        
        self.recording_lock = threading.Lock()
        
        self.frame_rate_timer = QTimer()
        self.frame_rate_timer.timeout.connect(self.calculate_frame_rates)
        
        self.nbCameraImages = 0
        self.roi_tracking_frames = 0
        self.calculating_roi = False

        config = ConfigParser()
        config.read('config.ini')
        url =  config['DEFAULT']['databaseurl']
        self.redisclient = RedisClient(url)

    def connectSignalSlots(self):
        self.ui.button_connect.clicked.connect(self.connect_clicked)
        self.ui.button_record.clicked.connect(self.record_clicked)
        self.ui.button_trigger.clicked.connect(self.trigger_clicked)

        self.ui.button_parameters.clicked.connect(self.configure_parameters)
    
    def configure_parameters(self):
        dialog = ParametersDialog(self.interface)
        dialog.exec()
    
    def calculate_frame_rates(self):
        camera_frame_rate = self.nbCameraImages / 5
        roi_frame_rate = self.roi_tracking_frames / 5
        print(f'Camera frame rate: {camera_frame_rate:.2f}')
        print(f'ROI tracking frame rate: {roi_frame_rate:.2f}')
        
        #TODO technically, need to lock
        self.nbCameraImages = 0
        self.roi_tracking_frames = 0

    def connect_clicked(self):
        if not self.connected:
            self.connect_camera()
        else:
            self.disconnect_camera()
    
    def connect_camera(self):
        if self.connected:
            return

        if(self.interface.connect(callback, self)):
            self.connected = True
            self.ui.button_connect.setText('Disconnect')
            self.ui.label_connection.setText('Connected to camera')
            #self.max_values = []
            self.ui.button_record.setEnabled(True)
            self.nbCameraImages = 0
            self.frame_rate_timer.start(5000)
            
            
    def disconnect_camera(self):
        if not self.connected:
            return

        if(self.interface.disconnect()):
            self.connected = False
            self.ui.button_connect.setText('Connect')
            self.ui.label_connection.setText('Not connected to camera')
            self.ui.button_record.setEnabled(False)
            self.frame_rate_timer.stop()

    def record_clicked(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()
            
    def start_recording(self):
        if self.recording:
            return

        self.tmax_graph = time.perf_counter()
        self.ui.button_record.setText('Stop')
        self.ui.label_recording.setText('Recording')
        self.recording = True
    
    def stop_recording(self):
        if not self.recording:
            return
        
        self.ui.button_record.setText('Start')
        self.ui.label_recording.setText('Not recording')
        self.recording = False

    def trigger_clicked(self):
        print('trigger')
        
    def load_image(self, recording_timestamp):  
        global t
        global tLive
        global img_timestamp_ref
        now=time.perf_counter()
        # print(now-t)
        t = now
        
        #Always setup ROI calculations, but only update UI intermittently
        
        self.nbCameraImages += 1
        
        with self.interface.get_image() as image:
            img = image.get_image_data()
            timestamp_offset = image.get_timestamp()
        
        if img_timestamp_ref is None:
            img_timestamp_ref = recording_timestamp - timedelta(milliseconds=timestamp_offset)
        
        timestamp = img_timestamp_ref + timedelta(milliseconds=timestamp_offset)
        
        if self.recording:
            self.calculate_roi(img, timestamp)
        
        if (t-tLive) > 0.4:
            tLive=t
            self.request_image_update.emit(img)
    
    def initialize_image_display(self, img):
        self.image.setImage(img, autoRange=False)
        
        y = len(img)
        x = len(img[0])
        
        h = 50
        w = 50
        
        self.roi_ul = pg.RectROI([x/4 - w/2 , y/4 - h /2], [w,h], centered = True, pen ='g')
        
        self.roi_ll = pg.RectROI([x/4 - w/2, (3/4)*y - h/2], [w,h], centered = True, pen ='r')
        
        self.roi_lr = pg.RectROI([(3/4)*x - w/2, (3/4)*y - h/2], [w,h], centered = True, pen ='b')
        
        self.roi_ur = pg.RectROI([(3/4)*x - w/2, y/4 - h/2], [w,h], centered = True, pen ='c')
        
        self.image.getView().addItem(self.roi_ul)
        self.image.getView().addItem(self.roi_ll)
        self.image.getView().addItem(self.roi_lr)
        self.image.getView().addItem(self.roi_ur)
        
        self.image.autoRange()
        self.imageInit = True
        
    def update_image(self, img):
        if not self.imageInit:
            self.initialize_image_display(img)
        else:
            self.image.getImageItem().updateImage(img)
    
    def calculate_roi(self, img, timestamp):
        self.t_startroi = time.perf_counter()
        
        calculator = BrightnessCalculator(img, self.roi_ul.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi_ll.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi_lr.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi_ur.getArrayRegion(img, self.image.getImageItem()))
        
        calculator.run()
        
        self.redisclient.add_roi_max_values(timestamp, calculator.max_ul, calculator.max_ur, calculator.max_ll, calculator.max_lr)
        
        self.t_endroi = time.perf_counter()
        
        self.roi_calculation_finished.emit(calculator)
        
        self.roi_tracking_frames += 1
    
    def on_roi_calculations_finished(self, calculator):
        min = calculator.min_ul
        self.ui.lineEdit_roi_ul_min.setText(f'{min:.2f}')
        max_ul = calculator.max_ul
        self.ui.lineEdit_roi_ul_max.setText(f'{max_ul:.2f}')
        mean = calculator.mean_ul
        self.ui.lineEdit_roi_ul_avg.setText(f'{mean:.2f}')
        
        min = calculator.min_ll
        self.ui.lineEdit_roi_ll_min.setText(f'{min:.2f}')
        max_ll = calculator.max_ll
        self.ui.lineEdit_roi_ll_max.setText(f'{max_ll:.2f}')
        mean = calculator.mean_ll
        self.ui.lineEdit_roi_ll_avg.setText(f'{mean:.2f}')
        
        min = calculator.min_lr
        self.ui.lineEdit_roi_lr_min.setText(f'{min:.2f}')
        max_lr = calculator.max_lr
        self.ui.lineEdit_roi_lr_max.setText(f'{max_lr:.2f}')
        mean = calculator.mean_lr
        self.ui.lineEdit_roi_lr_avg.setText(f'{mean:.2f}')
        
        min = calculator.min_ur
        self.ui.lineEdit_roi_ur_min.setText(f'{min:.2f}')
        max_ur = calculator.max_ur
        self.ui.lineEdit_roi_ur_max.setText(f'{max_ur:.2f}')
        mean = calculator.mean_ur
        self.ui.lineEdit_roi_ur_avg.setText(f'{mean:.2f}')
        

    def closeEvent(self, *args):
        #stopgrab
        if self.connected:
            self.stop_recording()
        self.interface.free_device()
        self.interface.free_dll()
        super().closeEvent(*args)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
