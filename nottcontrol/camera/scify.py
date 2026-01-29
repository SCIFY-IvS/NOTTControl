# This Python file uses the following encoding: utf-8
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIntValidator
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
from nottcontrol.camera.infratec_interface import InfratecInterface, Image

import numpy
import cv2
from nottcontrol.camera.brightness_calculator import BrightnessCalculator
from nottcontrol.camera.parametersdialog import ParametersDialog
from nottcontrol.redisclient import RedisClient
from nottcontrol import config
from collections import deque
from enum import Enum
from nottcontrol.camera.roi import Roi
from nottcontrol.camera.roiwidget import RoiWidget
import queue
from pathlib import Path

t=time.perf_counter()
tLive=t

img_timestamp_ref = None

use_camera_time_ = (config['CAMERA']['use_camera_time'] == "True")

def callback(context,*args):#, aHandle, aStreamIndex):
    recording_timestamp = datetime.now(timezone.utc)
    
    global img_timestamp_ref
    
    context.load_image(recording_timestamp,use_camera_time_)

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

        url =  config['DEFAULT']['databaseurl']
        self.redisclient = RedisClient(url)
        
        self.load_roi_config(config)

        self.ui.actionLoad_from_config.triggered.connect(self.load_roi_positions_from_config)
        self.ui.actionSave_to_config.triggered.connect(self.save_roi_positions_to_config)

        self.ui.cb_coadd.stateChanged.connect(self.enable_coadd)
        self.ui.lineEdit_coadd_frames.setPlaceholderText("Please enter a valid number up to 999")
        self.ui.lineEdit_coadd_frames.setValidator(QIntValidator(1, 999, self))

        #This should translate to roughly 30s, assuming 200 Hz
        deque_length = 6000

        self.timestamps = deque(maxlen = deque_length)
        self.coadd_frames_buffer = []
        self.roi_queue = queue.Queue()
    
    def enable_coadd(self):
        self.ui.lineEdit_coadd_frames.setEnabled(self.is_coadd_enabled())

        if self.is_coadd_enabled:
            self.coadd_frames_buffer.clear()
    
    def is_coadd_enabled(self):
        return self.ui.cb_coadd.isChecked()
    
    def nb_coadd_frames(self):
        s = self.ui.lineEdit_coadd_frames.text()
        return int(s)

    def process_frame(self):
        tLastUpdate = time.perf_counter()
        base_path = config["DEFAULT"]["frame_directory"]
        print(f"base directory: {base_path}")
        while True:
            item = self.roi_queue.get()
            img = item[0]

            timestamp = item[1]
            #base_path = r"Y:\Documents\Scify\Frames\frame_"
            directory = Path(base_path).joinpath(timestamp.strftime("%Y%m%d"))
            directory.mkdir(parents=True, exist_ok=True)
            timestamp_str = timestamp.strftime("%H%M%S%f")
            timestamp_str_round = str(round((int(timestamp_str)/1000)))
            filename = timestamp_str_round + ".png"
            filepath = str(Path.joinpath(directory, filename))

            recording = self.recording
            
            if recording:
                print(f"Saving {filepath} ...")
                thread = threading.Thread(target = cv2.imwrite, args =(filepath, img))
                thread.start()

            if recording or not self.is_coadd_enabled(): #always process individual frames if recording; always process all frames if not coadding
                self.process_roi(img, timestamp, coadded_frame=False)

            #If coadding, check to see if we have the required amount of frames
            coadd_in_process = False
            if self.is_coadd_enabled():
                self.coadd_frames_buffer.append(img)
                if len(self.coadd_frames_buffer) >= self.nb_coadd_frames():
                    #Create 3D array containing all values
                    arr = numpy.array(self.coadd_frames_buffer)
                    #maintain dtype, otherwise the background substraction will throw an error
                    img = numpy.average(arr, axis=0).astype(numpy.uint16)
                    self.process_roi(img, timestamp, coadded_frame=True)
                    self.coadd_frames_buffer.clear()
                else:
                    coadd_in_process = True
            
            t = time.perf_counter()
            if (t-tLastUpdate) > 0.4 and not coadd_in_process:
                tLastUpdate = t
                self.request_image_update.emit(img)
            
            if recording:
                thread.join()
    
    def load_roi_config(self, config):
        self.roi_config = []
        i = 1
        for roi_widget in self.roi_widgets:
            try:
                roi_config = self.load_roi_from_config(config, roi_widget.name)
            except:
                print(f'Failed to load roi configuration for {roi_widget.name}, using default')
                roi_config = Roi(i*100, 600, 50,50)
            roi_widget.setConfig(roi_config)
            i = i + 1
            
    def load_roi_from_config(self, config, adr):
        roi_string = config['CAMERA'][adr]
        roi_dimensions = roi_string.split(',')
        if len(roi_dimensions) != 4:
            raise Exception('Invalid Roi config')
        return Roi(roi_dimensions[0], roi_dimensions[1], roi_dimensions[2], roi_dimensions[3])
    
    def load_roi_positions_from_config(self):
        self.load_roi_config(config)
        if self.imageInit:
            for roi_widget in self.roi_widgets:
                roi_widget.updateRoi_from_config()

    def updateRoi_from_config(self, roi, roi_config):
        roi.setPos([roi_config.x, roi_config.y])
        roi.setSize([roi_config.w, roi_config.h])


    def save_roi_positions_to_config(self):
        if not config.config_parser.has_section('CAMERA'):
            config.config_parser.add_section('CAMERA')

        for roi_widget in self.roi_widgets:
            self.save_roi_position_to_config(roi_widget.roi, roi_widget.name)

        config.write()

    def save_roi_position_to_config(self, roi, key):
        roi_pos = roi.pos()
        roi_size = roi.size()
        config.config_parser.set('CAMERA', key, f'{roi_pos[0]},{roi_pos[1]},{roi_size[0]},{roi_size[1]}')

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
        if not config['CAMERA'].getboolean('windowing'):
            return
        
        # Fetching current window dimensions
        #w_cur = self.interface.getparam_int32(294)
        #h_cur = self.interface.getparam_int32(295)
        # Fetching config window dimensions
        #w_con = config['CAMERA'].getint('window_w')
        #h_con = config['CAMERA'].getint('window_h')
        
        # Large frame to small frame
        #if w_cur*h_cur > w_con*h_con:
        self.interface.setparam_int32(294, config['CAMERA'].getint('window_w'))
        self.interface.setparam_int32(295, config['CAMERA'].getint('window_h'))
        self.interface.setparam_int32(292, config['CAMERA'].getint('window_x'))
        self.interface.setparam_int32(293, config['CAMERA'].getint('window_y'))
        #else:
        # Small frame to large frame
        #    self.interface.setparam_int32(292, config['CAMERA'].getint('window_x'))
        #    self.interface.setparam_int32(293, config['CAMERA'].getint('window_y'))
        #    self.interface.setparam_int32(294, config['CAMERA'].getint('window_w'))
        #    self.interface.setparam_int32(295, config['CAMERA'].getint('window_h'))
            
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
            self.time_reference_frames = 0
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
    
    def load_image(self, recording_timestamp, use_camera_time):  
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
            if not self.imageInit:
                self.request_image_update.emit(img)
            timestamp_offset = image.get_timestamp() #not used ATM, but can we use this as a failsafe somehow?
                
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
        
        if use_camera_time:
            timestamp = timedelta(milliseconds=timestamp_offset)
        else:
            timestamp = img_timestamp_ref + timedelta(milliseconds=timestamp_offset)
        #print(f"Delay: {recording_timestamp - timestamp}")
        
        if(self.roi_queue.qsize() > 5):
            print('Dropping frame!')
        else:
            self.roi_queue.put((img, timestamp))

    
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

        #Now safe to start processing the frames
        threading.Thread(target=self.process_frame, daemon=True).start()



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
            self.set_brightness_auto()
        else:
            if self.ui.checkBox_subtractbackground.isChecked():
                img = cv2.subtract(img, self.background_img)
            self.image.getImageItem().setImage(img, autoLevels = False)

        self.pw_roi.clear()

        for roi_widget in self.roi_widgets:
            if roi_widget.isChecked():
                self.pw_roi.plot(list(self.timestamps), list(roi_widget.max_values), name= roi_widget.name, pen= roi_widget.color)
                
    def process_roi(self, img, timestamp, coadded_frame):
        calculator = self.run_roi_calculator(img)
        if not coadded_frame and self.recording:
            self.store_roi_to_db(timestamp, calculator)
            self.roi_tracking_frames += 1
        
        if coadded_frame or not self.is_coadd_enabled():
            self.update_gui_with_newroi(timestamp, calculator)
            
    def update_gui_with_newroi(self, timestamp, calculator):
        self.timestamps.appendleft(datetime.timestamp(timestamp))
        for i in range(len(self.roi_widgets)):
            self.roi_widgets[i].add_max_value(calculator.results[i].max)
                
        self.roi_calculation_finished.emit(calculator)

    def run_roi_calculator(self, img):
        calculator = BrightnessCalculator([roi_widget.roi.getArrayRegion(img, self.image.getImageItem()) for roi_widget in self.roi_widgets])
        calculator.run()
        return calculator

    def store_roi_to_db(self, timestamp, calculator):
        roi_values = dict()
        for i in range(len(self.roi_widgets)):
            key = self.roi_widgets[i].db_key
            value = calculator.results[i]
            roi_values[key] = value
        
        self.redisclient.add_roi_values(timestamp, roi_values)
    
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
