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
import queue

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

        self.roi_widgets = [RoiWidget(self, 1, QColorConstants.Green), RoiWidget(self, 2, QColorConstants.Cyan), RoiWidget(self, 3, QColorConstants.Red), 
                           RoiWidget(self, 4, QColorConstants.Blue), RoiWidget(self, 5, QColorConstants.Magenta), RoiWidget(self, 6, QColorConstants.DarkGreen),
                           RoiWidget(self, 7, QColorConstants.DarkBlue), RoiWidget(self, 8, QColorConstants.DarkRed), RoiWidget(self, 9, QColorConstants.DarkCyan),
                           RoiWidget(self, 10, QColorConstants.DarkYellow)]
        
        self.ui.scrollAreaWidgetContents.setLayout(QVBoxLayout())
        self.ui.scrollArea.setWidgetResizable(True)
        for roiwidget in self.roi_widgets:
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

        self.frame_rate_timer = QTimer()
        self.frame_rate_timer.timeout.connect(self.calculate_frame_rates)

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

        self.roi_queue = queue.Queue()
        threading.Thread(target=self.load_roi_worker, daemon=True).start()
    
    def load_roi_worker(self):
        while True:
            item = self.roi_queue.get()
            img = item[0]
            timestamp = item[1]
            print(f"Calculating ROI for timestamp {timestamp}")
            self.calculate_roi(img, timestamp)


    def load_roi_config(self, config):
        self.roi_config = []
        for roi_widget in self.roi_widgets:
            try:
                roi_config = self.load_roi_from_config(config, roi_widget.name)
            except:
                print(f'Failed to load roi configuration for {roi_widget.name}, using default')
                roi_config = Roi(i*100, 600, 50,50)
            roi_widget.setConfig(roi_config)
            
    def load_roi_from_config(self, config, adr):
        roi_string = config['CAMERA'][adr]
        roi_dimensions = roi_string.split(',')
        if len(roi_dimensions) != 4:
            raise Exception('Invalid Roi config')
        return Roi(roi_dimensions[0], roi_dimensions[1], roi_dimensions[2], roi_dimensions[3])
    
    def load_roi_positions_from_config(self):
        self.load_roi_config(self.config)
        if self.imageInit:
            for roi_widget in self.roi_widgets:
                roi_widget.updateRoi_from_config()

    def updateRoi_from_config(self, roi, roi_config):
        roi.setPos([roi_config.x, roi_config.y])
        roi.setSize([roi_config.w, roi_config.h])


    def save_roi_positions_to_config(self):
        if not self.config.has_section('CAMERA'):
            self.config.add_section('CAMERA')

        for roi_widget in self.roi_widgets:
            self.save_roi_position_to_config(roi_widget.roi, roi_widget.name)

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
            self.frame_rate_timer.start(5000)
    

    def set_window(self):
        if not self.config['CAMERA'].getboolean('windowing'):
            return

        self.interface.setparam_int32(294, self.config['CAMERA'].getint('window_w'))
        self.interface.setparam_int32(295, self.config['CAMERA'].getint('window_h'))
        self.interface.setparam_int32(292, self.config['CAMERA'].getint('window_x'))
        self.interface.setparam_int32(293, self.config['CAMERA'].getint('window_y'))

        self.set_brightness_auto()
            
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
            self.frame_rate_timer.stop()

    def record_clicked(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()
            
    def start_recording(self):
        if self.recording:
            return
        
        self.timestamps.clear()
        for roi_widget in self.roi_widgets:
            roi_widget.clear_max_values()

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
            timestamp_offset = image.get_timestamp() #not used ATM, but can we use this as a failsafe somehow?
                
        timestamp = recording_timestamp #TODO: this needs changing after coordinating with the PLC

        #print(f"Delay: {recording_timestamp - timestamp}")
        
        if self.recording:
            if(self.roi_queue.qsize() > 5):
                print('Dropping frame!')
            else:
                self.roi_queue.put((img, timestamp))
            #self.calculate_roi(img, timestamp)

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

    def initialize_roi(self, img):
        for roi_widget in self.roi_widgets:
            roi = roi_widget.createRoi()
            self.image.getView().addItem(roi)
    
    def get_roi_from_config(self, roi_config:Roi, pen):
        return pg.RectROI([roi_config.x, roi_config.y], [roi_config.w, roi_config.h], pen = pen)
        
    def update_image(self, img):
        if not self.imageInit:
            self.set_window()
            self.initialize_image_display(img)
        else:
            if self.ui.checkBox_subtractbackground.isChecked():
                img = cv2.subtract(img, self.background_img)
            self.image.getImageItem().setImage(img, autoLevels = False)

        self.pw_roi.clear()

        for roi_widget in self.roi_widgets:
            if roi_widget.isChecked():
                self.pw_roi.plot(list(self.timestamps), list(roi_widget.max_values), name= roi_widget.name, pen= roi_widget.color)
                
    def calculate_roi(self, img, timestamp):
        #Loop over all ROI: calculate values
        # Push to redis
        # Update corresponding GUI components

        calculator = BrightnessCalculator([roi_widget.roi.getArrayRegion(img, self.image.getImageItem()) for roi_widget in self.roi_widgets])
        
        calculator.run()

        roi_values = dict()
        for i in range(len(self.roi_widgets)):
            key = self.roi_widgets[i].db_key
            value = calculator.results[i]
            roi_values[key] = value
        
        self.redisclient.add_roi_values(timestamp, roi_values)
        
        self.timestamps.appendleft(datetime.timestamp(timestamp))
        for i in range(len(self.roi_widgets)):
            self.roi_widgets[i].add_max_value(calculator.results[i].max)
                
        self.roi_calculation_finished.emit(calculator)
        
        self.roi_tracking_frames += 1
    
    def on_roi_calculations_finished(self, calculator):
        for i in range(len(self.roi_widgets)):
            self.roi_widgets[i].setValues(calculator.results[i])

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
