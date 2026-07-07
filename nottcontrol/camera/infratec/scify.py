# This Python file uses the following encoding: utf-8
from PyQt5.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QWidget,
)
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
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtGui import QColorConstants
from nottcontrol.camera.infratec.infratec_interface import InfratecInterface, Image

import numpy
import cv2
from nottcontrol.camera.infratec.frame_writer import FrameWriter
from nottcontrol.camera.infratec.brightness_calculator import BrightnessCalculator
from nottcontrol.camera.infratec.parametersdialog import ParametersDialog
from nottcontrol.redisclient import RedisClient
from nottcontrol import config
from collections import deque
from enum import Enum
from nottcontrol.camera.infratec.roi import Roi
from nottcontrol.camera.infratec.roiwidget import (
    GRID_H_SPACING,
    HEADER_HEIGHT,
    HEADER_STYLE,
    NAME_WIDTH,
    PLOT_WIDTH,
    RoiWidget,
    VALUE_WIDTH,
    roi_panel_height,
    roi_panel_width,
)
import queue
from pathlib import Path
import zmq
from platform import system

# Location of frames on the machine
if system() == "Windows":
    frame_directory = str(config['DEFAULT']['frame_directory'])
else:
    frame_directory = str(config['DEFAULT']['linux_frame_directory'])


t=time.perf_counter()
tLive=t

img_timestamp_ref = None

use_camera_time = (config['CAMERA']['use_camera_time'] == "True")
record_rois = (config['CAMERA']['record_rois'] == "True")
FRAME_QUEUE_SIZE = config.getint("CAMERA", "frame_queue_size", fallback=64)
SAVE_QUEUE_SIZE = config.getint("CAMERA", "save_queue_size", fallback=256)
PNG_COMPRESSION = config.getint("CAMERA", "png_compression", fallback=1)
IMAGE_DISPLAY_SCALE = config.getint("CAMERA", "image_display_scale", fallback=4)
IMAGE_BORDER = 16
GRAPH_HEIGHT = 110
WINDOW_BOTTOM_BUFFER = 6
LEFT_COLUMN_X = 10
LEFT_COLUMN_GAP = 10
FRAMES_TODAY_LABEL_Y = 132
ROI_PANEL_Y = 156

def callback(context,*args):#, aHandle, aStreamIndex):
    # Creating timezone-aware datetime object, in utc
    recording_timestamp = datetime.now(timezone.utc)
    # Dropping the timezone info
    recording_timestamp = recording_timestamp.replace(tzinfo=None)
    
    
    global img_timestamp_ref
    
    context.load_image(recording_timestamp,use_camera_time)

class MainWindow(QMainWindow):
    #Without this call, the GUI is resized and tiny
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    request_image_update = pyqtSignal(numpy.ndarray)
    roi_calculation_finished = pyqtSignal(BrightnessCalculator)
    frames_saved_today_updated = pyqtSignal(int, str)
    closing = pyqtSignal()
    
    def __init__(self):
        super(MainWindow, self).__init__()
        self.interface = InfratecInterface()

        pg.setConfigOptions(imageAxisOrder='row-major')
        ## Switch to using white background and black foreground
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.ui = loadUi('camera/infratec/mainwindow.ui', self)
        self.frame_directory = frame_directory

        self._setup_roi_values_panel()
        self._setup_frames_today_label()
        self._layout_window()

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
        self.frames_saved_today_updated.connect(self._update_frames_today_label)
        
        self.recording_lock = threading.Lock()
        self._frames_count_lock = threading.Lock()
        self._frames_saved_utc_day: str | None = None
        self._frames_saved_today = 0

        self.frame_rate_timer = QTimer()
        self.frame_rate_timer.timeout.connect(self.calculate_frame_rates)

        self.nbCameraImages = 0
        self.roi_tracking_frames = 0
        self.calculating_roi = False

        url =  config['DEFAULT']['databaseurl']
        self.redisclient = RedisClient(url)
        self.frame_writer = FrameWriter(
            self.redisclient,
            queue_size=SAVE_QUEUE_SIZE,
            png_compression=PNG_COMPRESSION,
            on_frame_saved=self._on_frame_saved_to_disk,
        )
        
        self.load_roi_config(config)
        self._refresh_frames_saved_today()

        self.ui.actionLoad_from_config.triggered.connect(self.load_roi_positions_from_config)
        self.ui.actionSave_to_config.triggered.connect(self.save_roi_positions_to_config)

        self.ui.cb_coadd.stateChanged.connect(self.enable_coadd)
        self.ui.lineEdit_coadd_frames.setPlaceholderText("Please enter a valid number up to 999")
        self.ui.lineEdit_coadd_frames.setValidator(QIntValidator(1, 999, self))

        #This should translate to roughly 30s, assuming 200 Hz
        deque_length = 6000

        self.timestamps = deque(maxlen = deque_length)
        self.coadd_frames_buffer = []
        self.roi_queue = queue.Queue(maxsize=FRAME_QUEUE_SIZE)
        self.dropped_frames = 0
        
        self.running = True
        threading.Thread(target=self.socket_server, daemon=True).start()

    def _setup_roi_values_panel(self) -> None:
        self.ui.scrollArea.hide()

        panel_width = roi_panel_width()
        panel_height = roi_panel_height()

        self.roi_panel = QGroupBox("ROI values", self.ui.centralwidget)
        self.roi_panel.setGeometry(10, ROI_PANEL_Y, panel_width, panel_height)
        self.roi_panel.setFixedSize(panel_width, panel_height)
        self.roi_panel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.roi_panel.setStyleSheet(
            """
            QGroupBox {
                font: 700 10pt "Segoe UI";
                color: rgb(50, 129, 140);
                border: 1px solid rgb(50, 129, 140);
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 6px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            """
        )

        grid_host = QWidget(self.roi_panel)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(6, 2, 6, 4)
        grid.setHorizontalSpacing(GRID_H_SPACING)
        grid.setVerticalSpacing(0)

        for column, (text, width, alignment) in enumerate(
            (
                ("", NAME_WIDTH, Qt.AlignLeft),
                ("Plot", PLOT_WIDTH, Qt.AlignCenter),
                ("Min", VALUE_WIDTH, Qt.AlignRight),
                ("Max", VALUE_WIDTH, Qt.AlignRight),
                ("Avg", VALUE_WIDTH, Qt.AlignRight),
            )
        ):
            header = QLabel(text, grid_host)
            header.setFixedWidth(width)
            header.setFixedHeight(HEADER_HEIGHT)
            header.setStyleSheet(HEADER_STYLE)
            header.setAlignment(alignment | Qt.AlignVCenter)
            grid.addWidget(header, 0, column)

        self.roi_widgets = []
        colors = [
            QColorConstants.Green,
            QColorConstants.Cyan,
            QColorConstants.Red,
            QColorConstants.Blue,
            QColorConstants.Magenta,
            QColorConstants.DarkGreen,
            QColorConstants.DarkBlue,
            QColorConstants.DarkRed,
            QColorConstants.DarkCyan,
            QColorConstants.DarkYellow,
        ]
        for index, color in enumerate(colors, start=1):
            roi_widget = RoiWidget(grid_host, grid, index, index, color)
            self.roi_widgets.append(roi_widget)

        outer = QGridLayout(self.roi_panel)
        outer.setContentsMargins(6, 10, 6, 4)
        outer.addWidget(grid_host, 0, 0)

    def _setup_frames_today_label(self) -> None:
        self.label_frames_today = QLabel(self.ui.centralwidget)
        self.label_frames_today.setGeometry(
            LEFT_COLUMN_X, FRAMES_TODAY_LABEL_Y, roi_panel_width(), 20
        )
        self.label_frames_today.setStyleSheet(
            'font: 10pt "Segoe UI"; color: rgb(50, 129, 140);'
        )
        self._update_frames_today_label(0, datetime.now(timezone.utc).strftime("%Y%m%d"))

    def _utc_day_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d")

    def _count_frames_for_utc_day(self, utc_day: str) -> int:
        directory = Path(self.frame_directory) / utc_day
        if not directory.is_dir():
            return 0
        return sum(1 for path in directory.iterdir() if path.suffix.lower() == ".png")

    def _refresh_frames_saved_today(self) -> None:
        utc_day = self._utc_day_key()
        count = self._count_frames_for_utc_day(utc_day)
        with self._frames_count_lock:
            self._frames_saved_utc_day = utc_day
            self._frames_saved_today = count
        self.frames_saved_today_updated.emit(count, utc_day)

    def _on_frame_saved_to_disk(self, filepath: str) -> None:
        today = self._utc_day_key()
        saved_day = Path(filepath).parent.name
        with self._frames_count_lock:
            if self._frames_saved_utc_day != today:
                self._frames_saved_utc_day = today
                self._frames_saved_today = self._count_frames_for_utc_day(today)
            elif saved_day == today:
                self._frames_saved_today += 1
            count = self._frames_saved_today
            day = self._frames_saved_utc_day
        self.frames_saved_today_updated.emit(count, day)

    def _update_frames_today_label(self, count: int, utc_day: str) -> None:
        self.label_frames_today.setText(
            f"Frames saved today ({utc_day} UTC): {count:,}"
        )

    def _layout_window(self, img_shape=None) -> None:
        if img_shape is not None:
            img_h, img_w = int(img_shape[0]), int(img_shape[1])
        else:
            img_h = config.getint("CAMERA", "window_h")
            img_w = config.getint("CAMERA", "window_w")

        camera_w = img_w * IMAGE_DISPLAY_SCALE + IMAGE_BORDER
        camera_h = img_h * IMAGE_DISPLAY_SCALE + IMAGE_BORDER
        top_y = 50
        graph_gap = 8
        panel_width = roi_panel_width()
        panel_height = roi_panel_height()
        camera_x = LEFT_COLUMN_X + panel_width + LEFT_COLUMN_GAP

        self.roi_panel.setGeometry(LEFT_COLUMN_X, ROI_PANEL_Y, panel_width, panel_height)
        self.roi_panel.setFixedSize(panel_width, panel_height)
        self.label_frames_today.setFixedWidth(panel_width)

        self.ui.frame_camera.setGeometry(camera_x, top_y, camera_w, camera_h)
        self.ui.frame_camera.setFixedSize(camera_w, camera_h)

        background_bar = self.ui.button_takebackground.parentWidget()
        if background_bar is not None:
            background_bar.setGeometry(camera_x, 20, min(camera_w, 320), 32)

        graph_y = top_y + camera_h + graph_gap
        self.ui.frame_roi_graph.setGeometry(camera_x, graph_y, camera_w, GRAPH_HEIGHT)
        self.ui.frame_roi_graph.setFixedSize(camera_w, GRAPH_HEIGHT)
        if hasattr(self, "pw_roi"):
            self.pw_roi.setMinimumSize(camera_w, GRAPH_HEIGHT)

        right_x = camera_x + camera_w + 12
        self.ui.button_parameters.setGeometry(right_x, 20, 161, 32)
        self.ui.groupBox.setGeometry(right_x, 80, 181, 151)
        self.ui.groupBox_2.setGeometry(right_x, 250, 181, 91)

        content_h = graph_y + GRAPH_HEIGHT + WINDOW_BOTTOM_BUFFER
        window_w = max(right_x + 200, camera_x + camera_w + 40)
        self.ui.centralwidget.setFixedSize(window_w, content_h)
        window_h = content_h + self.menuBar().height()
        if self.statusBar() is not None:
            window_h += self.statusBar().height()
        self.setMinimumSize(window_w, window_h)
        self.resize(window_w, window_h)
    
    def socket_server(self):
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind("tcp://*:65535")

        poller = zmq.Poller()
        poller.register(socket, zmq.POLLIN)

        while self.running:
            try:
                events = dict(poller.poll(timeout=500))
                if socket in events:
                    message = socket.recv_string()
                    print(f"Message received: {message}")
                    if message == "Start record":
                        if self.start_recording():
                            reply = "Ok"
                        else:
                            reply = "Not connected"
                    elif message == "Stop record":
                        self.stop_recording()
                        reply = "Ok"
                    else:
                        reply = "Unknown command"
                    
                    socket.send_string(reply)
            except Exception as e:
                print(f"Unexpected error while handling message: {e}")
            
        print("Stopping zmq thread")

    
    def enable_coadd(self):
        self.ui.lineEdit_coadd_frames.setEnabled(self.is_coadd_enabled())

        if self.is_coadd_enabled:
            self.coadd_frames_buffer.clear()
    
    def is_coadd_enabled(self):
        return self.ui.cb_coadd.isChecked()
    
    def nb_coadd_frames(self):
        s = self.ui.lineEdit_coadd_frames.text()
        return int(s)

    def save_frame_write_redis(self, filepath, img, timestamp):
        if not self.frame_writer.enqueue(filepath, img, timestamp, self.integtime):
            print(f"Save queue full; dropped frame write ({self.frame_writer.dropped} total)")

    def process_frame(self):
        tLastUpdate = time.perf_counter()
        base_path = self.frame_directory
        print(f"base directory: {base_path}")
        while True:
            item = self.roi_queue.get()
            img = item[0]
            # Timestamp is a datetime.utc object
            timestamp = item[1]
            # Getting remaining amount of microseconds in the millisecond
            remaining_us = timestamp.microsecond % 1000
            # Rounding
            if remaining_us >= 500:
                timestamp = timestamp + timedelta(microseconds=(1000-remaining_us))
            else:
                timestamp = timestamp - timedelta(microseconds=remaining_us)
            directory = Path(base_path).joinpath(timestamp.strftime("%Y%m%d"))
            # Already rounded to the nearest ms earlier, just drop the "000" at the end.
            timestamp_str = timestamp.strftime("%H%M%S%f")[:-3]
            filename = timestamp_str + ".png"
            filepath = str(Path.joinpath(directory, filename))

            with self.recording_lock:
                recording = self.recording

            save_frame = recording and self.ui.checkBox_saveframes.isChecked()
            
            if save_frame:
                self.save_frame_write_redis(filepath, img, timestamp)

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
        return Roi(int(roi_dimensions[0])-config['CAMERA'].getint('window_x'), int(roi_dimensions[1])-config['CAMERA'].getint('window_y'), roi_dimensions[2], roi_dimensions[3])
    
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
        if self.dropped_frames or self.frame_writer.dropped:
            print(
                f'Dropped frames: process={self.dropped_frames}, '
                f'save={self.frame_writer.dropped}, '
                f'save queue={self.frame_writer.pending()}'
            )
        self._refresh_frames_saved_today()
        
        self.nbCameraImages = 0
        self.roi_tracking_frames = 0

    def connect_clicked(self):
        if not self.connected:
            self.time_reference_frames = 0
            self.connect_camera()
            self.integtime = self.interface.getparam_idx_int32(262,0)
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
            self._refresh_frames_saved_today()
    

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
        with self.recording_lock:
            if self.recording:
                return True
        if not self.connected:
            return False
        
        # Store current camera integration time
        self.integtime = self.interface.getparam_idx_int32(262,0)
        
        self.timestamps.clear()
        for roi_widget in self.roi_widgets:
            roi_widget.clear_max_values()

        self.ui.button_record.setText('Stop')
        self.ui.label_recording.setText('Recording')
        with self.recording_lock:
            self.recording = True
        self._refresh_frames_saved_today()
        return True
    
    def stop_recording(self):
        with self.recording_lock:
            if not self.recording:
                return
            self.recording = False
        
        self.ui.button_record.setText('Start')
        self.ui.label_recording.setText('Not recording')
        self.frame_writer.drain(timeout=30.0)
        self._refresh_frames_saved_today()
    
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
        
        if(self.roi_queue.full()):
            self.dropped_frames += 1
            if self.dropped_frames == 1 or self.dropped_frames % 100 == 0:
                print(
                    f'Dropping frame ({self.dropped_frames} total), '
                    f'process queue full, save queue={self.frame_writer.pending()}'
                )
        else:
            self.roi_queue.put((img, timestamp))

    
    def initialize_image_display(self, img):
        self._layout_window(img.shape)
        self.image.setImage(img, autoRange=False)
        
        self.initialize_roi(img)
        
        self.image.autoRange()
        self.imageInit = True

        axis = pg.DateAxisItem(orientation='bottom')
        self.pw_roi = pg.PlotWidget(parent = self.ui.frame_roi_graph,axisItems={'bottom': axis})
        self.pw_roi.setMinimumWidth(self.ui.frame_roi_graph.width())
        self.pw_roi.setMinimumHeight(self.ui.frame_roi_graph.height())
        self.pw_roi.addLegend()
        self.pw_roi.getPlotItem().setLabel(axis='left', text='ROI brightness [ADU]')
        
        self.pw_roi.show()
        self.plot_data_item_roi = self.pw_roi.plot()
        self.pw_roi.getPlotItem().setLabel(axis='bottom', text='Time [UTC]')

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
            if record_rois:
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
        regions = self._extract_roi_regions(img)
        calculator = BrightnessCalculator(regions)
        calculator.run()
        return calculator

    def _extract_roi_regions(self, img):
        if not self.imageInit:
            return [
                roi_widget.roi.getArrayRegion(img, self.image.getImageItem())
                for roi_widget in self.roi_widgets
            ]

        regions = []
        for roi_widget in self.roi_widgets:
            pos = roi_widget.roi.pos()
            size = roi_widget.roi.size()
            x, y = int(pos[0]), int(pos[1])
            w, h = int(size[0]), int(size[1])
            regions.append(img[y : y + h, x : x + w])
        return regions

    def store_roi_to_db(self, timestamp, calculator):
        roi_values = dict()
        for i in range(len(self.roi_widgets)):
            key = self.roi_widgets[i].db_key
            value = calculator.results[i]
            roi_values[key] = value
        
        self.redisclient.add_roi_values(timestamp, roi_values)
        
    def store_framerate_to_db(self, timestamp, framerate):
        self.redisclient.add_cam_framerate(timestamp,framerate)
        
    def store_integtime_to_db(self, timestamp, integtime):
        self.redisclient.add_cam_integtime(timestamp,integtime)
        
    def on_roi_calculations_finished(self, calculator):
        for i in range(len(self.roi_widgets)):
            self.roi_widgets[i].setValues(calculator.results[i])

    def closeEvent(self, *args):
        #stopgrab
        if self.connected:
            self.stop_recording()
        self.frame_writer.stop(timeout=30.0)
        self.interface.free_device()
        self.interface.free_dll()
        self.closing.emit()
        super().closeEvent(*args)

        self.running = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())