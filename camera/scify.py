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
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtGui import QColorConstants
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
from camera.roiwidget import RoiWidget

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

        self.roiwidgets = [RoiWidget(self, 1, QColorConstants.Green), RoiWidget(self, 2, QColorConstants.Cyan), RoiWidget(self, 3, QColorConstants.Red), 
                           RoiWidget(self, 4, QColorConstants.Blue), RoiWidget(self, 5, QColorConstants.Magenta), RoiWidget(self, 6, QColorConstants.DarkGreen),
                           RoiWidget(self, 7, QColorConstants.DarkBlue), RoiWidget(self, 8, QColorConstants.DarkRed), RoiWidget(self, 9, QColorConstants.DarkCyan),
                           RoiWidget(self, 10, QColorConstants.DarkYellow)]
        
        self.ui.scrollAreaWidgetContents.setLayout(QVBoxLayout())
        self.ui.scrollArea.setWidgetResizable(True)
        for roiwidget in self.roiwidgets:
            self.ui.scrollAreaWidgetContents.layout().addWidget(roiwidget)

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
        self.roi_config = []
        for i in range(1, len(self.roiwidgets) + 1):
            try:
                roi_config = self.load_roi_from_config(config, f'ROI{i}')
            except:
                print(f'Failed to load roi configuration for ROI{i}, using default')
                roi_config = Roi(i*100, 600, 50,50)
            self.roi_config.append(roi_config)
    
    def load_roi_from_config(self, config, adr):
        roi_string = config['CAMERA'][adr]
        roi_dimensions = roi_string.split(',')
        if len(roi_dimensions) != 4:
            raise Exception('Invalid Roi config')
        return Roi(roi_dimensions[0], roi_dimensions[1], roi_dimensions[2], roi_dimensions[3])
    
    def load_roi_positions_from_config(self):
        self.load_roi_config(self.config)
        if self.imageInit:
            self.updateRoi_from_config(self.roi1, self.roi_config[0])
            self.updateRoi_from_config(self.roi2, self.roi_config[1])
            self.updateRoi_from_config(self.roi3, self.roi_config[2])
            self.updateRoi_from_config(self.roi4, self.roi_config[3])
            self.updateRoi_from_config(self.roi5, self.roi_config[4])
            self.updateRoi_from_config(self.roi6, self.roi_config[5])
            self.updateRoi_from_config(self.roi7, self.roi_config[6])
            self.updateRoi_from_config(self.roi8, self.roi_config[7])
            self.updateRoi_from_config(self.roi9, self.roi_config[8])
            self.updateRoi_from_config(self.roi10, self.roi_config[9])

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
        self.save_roi_position_to_config(self.roi5, 'ROI5')
        self.save_roi_position_to_config(self.roi6, 'ROI6')
        self.save_roi_position_to_config(self.roi7, 'ROI7')
        self.save_roi_position_to_config(self.roi8, 'ROI8')
        self.save_roi_position_to_config(self.roi9, 'ROI9')
        self.save_roi_position_to_config(self.roi10, 'ROI10')

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
        self.roi5_max_values.clear()
        self.roi6_max_values.clear()
        self.roi7_max_values.clear()
        self.roi8_max_values.clear()
        self.roi9_max_values.clear()
        self.roi10_max_values.clear()

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
        self.roi5_max_values = deque(maxlen = deque_length)
        self.roi6_max_values = deque(maxlen = deque_length)
        self.roi7_max_values = deque(maxlen = deque_length)
        self.roi8_max_values = deque(maxlen = deque_length)
        self.roi9_max_values = deque(maxlen = deque_length)
        self.roi10_max_values = deque(maxlen = deque_length)

    def initialize_roi(self, img):
        self.roi1 = self.get_roi_from_config(self.roi_config[0], pen =self.roiwidgets[0].color)
        self.roi2 = self.get_roi_from_config(self.roi_config[1], pen =self.roiwidgets[1].color)
        self.roi3 = self.get_roi_from_config(self.roi_config[2], pen =self.roiwidgets[2].color)
        self.roi4 = self.get_roi_from_config(self.roi_config[3], pen =self.roiwidgets[3].color)
        self.roi5 = self.get_roi_from_config(self.roi_config[4], pen =self.roiwidgets[4].color)
        self.roi6 = self.get_roi_from_config(self.roi_config[5], pen =self.roiwidgets[5].color)
        self.roi7 = self.get_roi_from_config(self.roi_config[6], pen =self.roiwidgets[6].color)
        self.roi8 = self.get_roi_from_config(self.roi_config[7], pen =self.roiwidgets[7].color)
        self.roi9 = self.get_roi_from_config(self.roi_config[8], pen =self.roiwidgets[8].color)
        self.roi10 = self.get_roi_from_config(self.roi_config[9], pen =self.roiwidgets[9].color)

        
        self.image.getView().addItem(self.roi1)
        self.image.getView().addItem(self.roi3)
        self.image.getView().addItem(self.roi4)
        self.image.getView().addItem(self.roi2)
        self.image.getView().addItem(self.roi5)
        self.image.getView().addItem(self.roi6)
        self.image.getView().addItem(self.roi7)
        self.image.getView().addItem(self.roi8)
        self.image.getView().addItem(self.roi9)
        self.image.getView().addItem(self.roi10)
    
    def get_roi_from_config(self, roi_config:Roi, pen):
        return pg.RectROI([roi_config.x, roi_config.y], [roi_config.w, roi_config.h], pen = pen)
        
    def update_image(self, img):
        if not self.imageInit:
            self.initialize_image_display(img)
        else:
            if self.ui.checkBox_subtractbackground.isChecked():
                img = cv2.subtract(img, self.background_img)
            self.image.getImageItem().setImage(img, autoLevels = False)

        self.pw_roi.clear()

        if self.roiwidgets[0].isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi1_max_values), name='ROI1', pen= self.roiwidgets[0].color)
        if self.roiwidgets[1].isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi2_max_values), name='ROI2', pen= self.roiwidgets[1].color)
        if self.roiwidgets[2].isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi3_max_values), name='ROI3', pen= self.roiwidgets[2].color)
        if self.roiwidgets[3].isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi4_max_values), name='ROI4', pen= self.roiwidgets[3].color)
        if self.roiwidgets[4].isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi5_max_values), name='ROI5', pen= self.roiwidgets[4].color)
        if self.roiwidgets[5].isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi6_max_values), name='ROI6', pen= self.roiwidgets[5].color)
        if self.roiwidgets[6].isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi7_max_values), name='ROI7', pen= self.roiwidgets[6].color)
        if self.roiwidgets[7].isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi8_max_values), name='ROI8', pen= self.roiwidgets[7].color)
        if self.roiwidgets[8].isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi9_max_values), name='ROI9', pen= self.roiwidgets[8].color)
        if self.roiwidgets[9].isChecked():
            self.pw_roi.plot(list(self.timestamps), list(self.roi10_max_values), name='ROI10', pen= self.roiwidgets[9].color)

                
    def calculate_roi(self, img, timestamp):
        #Loop over all ROI: calculate values
        # Push to redis
        # Update corresponding GUI components

        calculator = BrightnessCalculator([self.roi1.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi2.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi3.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi4.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi5.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi6.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi7.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi8.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi9.getArrayRegion(img, self.image.getImageItem()),
                                      self.roi10.getArrayRegion(img, self.image.getImageItem())])
        
        calculator.run()

        roi_values = {'roi1': calculator.results[0], 
                      'roi2': calculator.results[1], 
                      'roi3': calculator.results[2], 
                      'roi4': calculator.results[3], 
                      'roi5': calculator.results[4], 
                      'roi6': calculator.results[5], 
                      'roi7': calculator.results[6], 
                      'roi8': calculator.results[7],
                      'roi9': calculator.results[8],
                      'roi10': calculator.results[9]}
        
        self.redisclient.add_roi_values(timestamp, roi_values)
        
        self.timestamps.appendleft(datetime.timestamp(timestamp))
        self.roi1_max_values.appendleft(calculator.results[0].max)
        self.roi2_max_values.appendleft(calculator.results[1].max)
        self.roi3_max_values.appendleft(calculator.results[2].max)
        self.roi4_max_values.appendleft(calculator.results[3].max)
        self.roi5_max_values.appendleft(calculator.results[4].max)
        self.roi6_max_values.appendleft(calculator.results[5].max)
        self.roi7_max_values.appendleft(calculator.results[6].max)
        self.roi8_max_values.appendleft(calculator.results[7].max)
        self.roi9_max_values.appendleft(calculator.results[8].max)
        self.roi10_max_values.appendleft(calculator.results[9].max)
                
        self.roi_calculation_finished.emit(calculator)
        
        self.roi_tracking_frames += 1
    
    def on_roi_calculations_finished(self, calculator):
        self.roiwidgets[0].setValues(calculator.results[0])
        self.roiwidgets[1].setValues(calculator.results[1])
        self.roiwidgets[2].setValues(calculator.results[2])
        self.roiwidgets[3].setValues(calculator.results[3])
        self.roiwidgets[4].setValues(calculator.results[4])
        self.roiwidgets[5].setValues(calculator.results[5])
        self.roiwidgets[6].setValues(calculator.results[6])
        self.roiwidgets[7].setValues(calculator.results[7])
        self.roiwidgets[8].setValues(calculator.results[8])
        self.roiwidgets[9].setValues(calculator.results[9])

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
