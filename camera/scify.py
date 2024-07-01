# This Python file uses the following encoding: utf-8
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QApplication
from PyQt5.uic import loadUi

import sys
import time
import threading
import os
from datetime import datetime, timedelta, timezone
import ctypes,_ctypes
import pyqtgraph as pg
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtWidgets import (QPushButton,QGridLayout,QCheckBox,
                             QWidget,
                             QComboBox,QLabel,QLineEdit,QFrame,
                             )
from PyQt5.QtWidgets import QFileDialog
from camera.infratec_interface import InfratecInterface, Image

import numpy
import cv2
from camera.brightness_calculator import BrightnessCalculator
from camera.parametersdialog import ParametersDialog
from redisclient import RedisClient

from configparser import ConfigParser
from collections import deque
from enum import Enum
from camera.roi import Roi

t=time.perf_counter()
tLive=t

img_timestamp_ref = None

def callback(context,*args):#, aHandle, aStreamIndex):
    recording_timestamp = datetime.utcnow()
    
    global img_timestamp_ref
    
    context.load_image(recording_timestamp)

class MainWindow(QMainWindow):
    #Without this call, the GUI is resized and tiny
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    request_image_update = pyqtSignal(numpy.ndarray)
    roi_calculation_finished = pyqtSignal(BrightnessCalculator)
    closing = pyqtSignal()
    
    def __init__(self):
        super(MainWindow, self).__init__()
        self.interface = InfratecInterface()

        pg.setConfigOptions(imageAxisOrder='row-major')
        ## Switch to using white background and black foreground
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
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
        
        self.image.getView().setMouseEnabled(x = True, y = True)
        self.image.getView().disableAutoRange()
        
        self.request_image_update.connect(self.update_image)
        self.roi_calculation_finished.connect(self.on_roi_calculations_finished)
        
        self.recording_lock = threading.Lock()

        self.nbCameraImages = 0
        self.roi_tracking_frames = 0
        self.calculating_roi = False

        self.config = ConfigParser()
        self.config.read('config.ini')
        url =  self.config['DEFAULT']['databaseurl']
        self.redisclient = RedisClient(url)
        
        self.load_roi_config(self.config)

        self.ui.actionLoad_from_config.triggered.connect(self.load_roi_positions_from_config)
        self.ui.actionSave_to_config.triggered.connect(self.save_roi_positions_to_config)

    def load_roi_config(self, config):
        try:
            self.roi1_config = self.load_roi_from_config(config, 'ROI1')
            self.roi2_config = self.load_roi_from_config(config, 'ROI2')
            self.roi3_config = self.load_roi_from_config(config, 'ROI3')
            self.roi4_config = self.load_roi_from_config(config, 'ROI4')
        except:
            print('Failed to load roi configuration')
            self.roi1_config = None
            self.roi2_config = None
            self.roi3_config = None
            self.roi4_config = None
    
    def load_roi_from_config(self, config, adr):
        roi_string = config['CAMERA'][adr]
        roi_dimensions = roi_string.split(',')
        if len(roi_dimensions) != 4:
            raise Exception('Invalid Roi config')
        return Roi(roi_dimensions[0], roi_dimensions[1], roi_dimensions[2], roi_dimensions[3])
    
    def load_roi_positions_from_config(self):
        self.load_roi_config(self.config)
        if self.imageInit:
            self.updateRoi_from_config(self.roi1, self.roi1_config)
            self.updateRoi_from_config(self.roi2, self.roi2_config)
            self.updateRoi_from_config(self.roi3, self.roi3_config)
            self.updateRoi_from_config(self.roi4, self.roi4_config)

    def updateRoi_from_config(self, roi, roi_config):
        roi.setPos([roi_config.x, roi_config.y])
        roi.setSize([roi_config.w, roi_config.h])


    def save_roi_positions_to_config(self):
        if not self.config.has_section('CAMERA'):
            self.config.add_section('CAMERA')

        self.save_roi_position_to_config(self.roi1, 'ROI1')
        self.save_roi_position_to_config(self.roi2, 'ROI2')
        self.save_roi_position_to_config(self.roi3, 'ROI3')
        self.save_roi_position_to_config(self.roi4, 'ROI4')

        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)

    def save_roi_position_to_config(self, roi, key):
        roi_pos = roi.pos()
        roi_size = roi.size()
        self.config.set('CAMERA', key, f'{roi_pos[0]},{roi_pos[1]},{roi_size[0]},{roi_size[1]}')

    def connectSignalSlots(self):
        self.ui.button_connect.clicked.connect(self.connect_clicked)
        self.ui.button_record.clicked.connect(self.record_clicked)
        self.ui.button_trigger.clicked.connect(self.trigger_clicked)

        self.ui.button_parameters.clicked.connect(self.configure_parameters)

        self.ui.button_takebackground.clicked.connect(self.take_background)

        self.ui.button_autobrightness.clicked.connect(self.set_brightness_auto)
        self.ui.button_manualbrightness.clicked.connect(self.set_brightness_manual)

    def set_brightness_auto(self):
        min, max = self.image.imageItem.quickMinMax()
        self.image.setLevels(min, max)

        self.ui.lineEdit_minBrightness.setText(str(min))
        self.ui.lineEdit_maxBrightness.setText(str(max))
    
    def set_brightness_manual(self):
        min = float(self.ui.lineEdit_minBrightness.text())
        max = float(self.ui.lineEdit_maxBrightness.text())

        self.image.setLevels(min, max)
    
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
            self.time_reference_frames = 0
            self.connect_camera()
        else:
            self.disconnect_camera()
    
    def connect_camera(self):
        if self.connected:
            return
        
        global img_timestamp_ref
        img_timestamp_ref = None
        if(self.interface.connect(callback, self)):
            self.connected = True
            self.ui.button_connect.setText('Disconnect')
            self.ui.label_connection.setText('Connected to camera')
            #self.max_values = []
            self.ui.button_record.setEnabled(True)
            self.ui.button_takebackground.setEnabled(True)
            self.nbCameraImages = 0
            
            
    def disconnect_camera(self):
        if not self.connected:
            return

        if(self.interface.disconnect()):
            self.connected = False
            self.ui.button_connect.setText('Connect')
            self.ui.label_connection.setText('Not connected to camera')
            self.ui.button_record.setEnabled(False)
            self.ui.button_takebackground.setEnabled(False)
            self.ui.checkBox_subtractbackground.setEnabled(False)

    def record_clicked(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()
            
    def start_recording(self):
        if self.recording:
            return
        
        self.timestamps.clear()
        self.roi1_max_values.clear()
        self.roi2_max_values.clear()
        self.roi3_max_values.clear()
        self.roi4_max_values.clear()

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
    
    def take_background(self):
        self.background_img = self.image.getImageItem().image
        self.ui.checkBox_subtractbackground.setEnabled(True)
    
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
        
        if self.time_reference_frames < 100:
            new_timestamp_ref = recording_timestamp - timedelta(milliseconds=timestamp_offset)
            print(f"Timestamp reference: {new_timestamp_ref}")
            if img_timestamp_ref is None:
                img_timestamp_ref = new_timestamp_ref
            #Take the earliest time because there is always a delay, and the estimated timestamp can never be earlier thatn the actual timestamp
            img_timestamp_ref = min(img_timestamp_ref, new_timestamp_ref)

            self.time_reference_frames = self.time_reference_frames + 1

            if self.time_reference_frames == 100:
                print(f"Final timestamp reference: {img_timestamp_ref}")

            #Use the first 100 frames purely to establish time
            return
        
        timestamp = img_timestamp_ref + timedelta(milliseconds=timestamp_offset)

        #print(f"Delay: {recording_timestamp - timestamp}")
        
        if self.recording:
            self.calculate_roi(img, timestamp)
        

        if (t-tLive) > 0.4:
            tLive=t
            self.request_image_update.emit(img)
    
    def initialize_image_display(self, img):
        self.image.setImage(img, autoRange=False)
        
        self.initialize_roi(img)
        
        self.image.autoRange()
        self.imageInit = True

        axis = pg.DateAxisItem(orientation='bottom')
        self.pw_roi = pg.PlotWidget(parent = self.ui.frame_roi_graph,axisItems={'bottom': axis})
        self.pw_roi.setMinimumWidth(self.ui.frame_roi_graph.width())
        self.pw_roi.setMinimumHeight(self.ui.frame_roi_graph.height())
        self.pw_roi.addLegend()
        self.pw_roi.getPlotItem().setLabel(axis='left', text='ROI brightness')

        
        self.pw_roi.show()
        self.plot_data_item_roi = self.pw_roi.plot()
        self.pw_roi.getPlotItem().setLabel(axis='bottom', text='Time')

        #This should translate to roughly 30s, assuming 200 Hz
        deque_length = 6000

        self.timestamps = deque(maxlen = deque_length)
        self.roi1_max_values = deque(maxlen = deque_length)
        self.roi2_max_values = deque(maxlen = deque_length)
        self.roi3_max_values = deque(maxlen = deque_length)
        self.roi4_max_values = deque(maxlen = deque_length)

    def initialize_roi(self, img):
        y = len(img)
        x = len(img[0])
        
        h = 50
        w = 50

        if self.roi1_config is None:
            self.roi1_config = Roi(x/4 - w/2 , y/4 - h /2, w,h)
        if self.roi2_config is None:
            self.roi2_config = Roi((3/4)*x - w/2, y/4 - h/2, w,h) 
        if self.roi3_config is None:
            self.roi3_config = Roi(x/4 - w/2, (3/4)*y - h/2, w,h)
        if self.roi4_config is None:
            self.roi4_config = Roi((3/4)*x - w/2, (3/4)*y - h/2, w,h)
        
        self.roi1 = pg.RectROI([self.roi1_config.x, self.roi1_config.y], [self.roi1_config.w, self.roi1_config.h], pen ='g')
        self.roi2 = pg.RectROI([self.roi2_config.x, self.roi2_config.y], [self.roi2_config.w, self.roi2_config.h], pen ='c')
        self.roi3 = pg.RectROI([self.roi3_config.x, self.roi3_config.y], [self.roi3_config.w, self.roi3_config.h], pen ='r')
        self.roi4 = pg.RectROI([self.roi4_config.x, self.roi4_config.y], [self.roi4_config.w, self.roi4_config.h], pen ='b')
        
        self.image.getView().addItem(self.roi1)
        self.image.getView().addItem(self.roi3)
        self.image.getView().addItem(self.roi4)
        self.image.getView().addItem(self.roi2)
        
    def update_image(self, img):
        if not self.imageInit:
            self.initialize_image_display(img)
        else:
            if self.ui.checkBox_subtractbackground.isChecked():
                img = cv2.subtract(img, self.background_img)
            self.image.getImageItem().setImage(img, autoLevels = False)

        self.pw_roi.clear()

        if self.ui.checkBox_ROI1.isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi1_max_values), name='ROI1', pen='g')
        if self.ui.checkBox_ROI2.isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi2_max_values), name='ROI2', pen='c')
        if self.ui.checkBox_ROI3.isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi3_max_values), name='ROI3', pen='r')
        if self.ui.checkBox_ROI4.isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi4_max_values), name='ROI4', pen='b')
                
    def calculate_roi(self, img, timestamp):
        self.t_startroi = time.perf_counter()
        
        calculator = BrightnessCalculator(img, self.roi1.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi3.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi4.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi2.getArrayRegion(img, self.image.getImageItem()))
        
        calculator.run()
        
        self.redisclient.add_roi_values(timestamp, 
                                             calculator.max_ul, calculator.avg_ul, calculator.sum_ul,
                                             calculator.max_ur, calculator.avg_ur, calculator.sum_ur,
                                             calculator.max_ll, calculator.avg_ll, calculator.sum_ll,
                                             calculator.max_lr, calculator.avg_lr, calculator.sum_lr)
        
        self.timestamps.appendleft(datetime.timestamp(timestamp))
        self.roi1_max_values.appendleft(calculator.max_ul)
        self.roi2_max_values.appendleft(calculator.max_ur)
        self.roi3_max_values.appendleft(calculator.max_ll)
        self.roi4_max_values.appendleft(calculator.max_lr)
        
        self.t_endroi = time.perf_counter()
        
        self.roi_calculation_finished.emit(calculator)
        
        self.roi_tracking_frames += 1
    
    def on_roi_calculations_finished(self, calculator):
        min = calculator.min_ul
        self.ui.lineEdit_roi1_min.setText(f'{min:.2f}')
        max_ul = calculator.max_ul
        self.ui.lineEdit_roi1_max.setText(f'{max_ul:.2f}')
        avg = calculator.avg_ul
        self.ui.lineEdit_roi1_avg.setText(f'{avg:.2f}')
        
        min = calculator.min_ll
        self.ui.lineEdit_roi3_min.setText(f'{min:.2f}')
        max_ll = calculator.max_ll
        self.ui.lineEdit_roi3_max.setText(f'{max_ll:.2f}')
        avg = calculator.avg_ll
        self.ui.lineEdit_roi3_avg.setText(f'{avg:.2f}')
        
        min = calculator.min_lr
        self.ui.lineEdit_roi4_min.setText(f'{min:.2f}')
        max_lr = calculator.max_lr
        self.ui.lineEdit_roi4_max.setText(f'{max_lr:.2f}')
        avg = calculator.avg_lr
        self.ui.lineEdit_roi4_avg.setText(f'{avg:.2f}')
        
        min = calculator.min_ur
        self.ui.lineEdit_roi2_min.setText(f'{min:.2f}')
        max_ur = calculator.max_ur
        self.ui.lineEdit_roi2_max.setText(f'{max_ur:.2f}')
        avg = calculator.avg_ur
        self.ui.lineEdit_roi2_avg.setText(f'{avg:.2f}')
        

    def closeEvent(self, *args):
        #stopgrab
        if self.connected:
            self.stop_recording()
        self.interface.free_device()
        self.interface.free_dll()
        self.closing.emit()
        super().closeEvent(*args)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
