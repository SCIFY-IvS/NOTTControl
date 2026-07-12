# This Python file uses the following encoding: utf-8
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)
from PyQt5.uic import loadUi

import sys
import time
import threading
import os
from datetime import datetime, timedelta, timezone
import ctypes,_ctypes
import pyqtgraph as pg
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPointF
from PyQt5.QtGui import QColorConstants
from nottcontrol.camera.infratec.infratec_interface import InfratecInterface, Image

import numpy
from nottcontrol.camera.infratec.frame_writer import FrameWriter
from nottcontrol.camera.infratec.brightness_calculator import BrightnessCalculator
from nottcontrol.camera.infratec.detector_options import (
    DEFAULT_FRAMERATE_HZ,
    ensure_default_framerate_option,
    fallback_framerate_options_hz,
    fallback_integration_times_us,
    format_exposure_ms,
    format_framerate_hz,
    get_framerate_options_hz,
    get_integration_time_options_us,
    integration_time_options_for_framerate,
)
from nottcontrol.camera.infratec.parametersdialog import ParametersDialog
from nottcontrol.redisclient import RedisClient
from nottcontrol.app_icon import install_nott_logo_header
from nottcontrol import config
from collections import deque
from enum import Enum
from nottcontrol.camera.infratec.roi import Roi
from nottcontrol.camera.infratec.roiwidget import (
    GRID_H_SPACING,
    HEADER_HEIGHT,
    NAME_WIDTH,
    PANEL_CHROME_HEIGHT,
    PLOT_WIDTH,
    RoiWidget,
    VALUE_WIDTH,
    header_style,
    roi_panel_height,
    roi_panel_width,
)
from nottcontrol.ui_scale import scaled, scaled_font_pt
import queue
from pathlib import Path
import zmq
from platform import system

# Location of frames on the machine
if system() == "Windows":
    frame_directory = str(config['DEFAULT']['frame_directory'])
else:
    frame_directory = str(config['DEFAULT']['linux_frame_directory'])


def count_frames_saved_for_utc_day(utc_day: str) -> int:
    directory = Path(frame_directory) / utc_day
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.iterdir() if path.suffix.lower() == ".png")


def camera_status_snapshot(camera_window=None) -> dict[str, object]:
    """Return dashboard camera status from an open window or disk fallback."""
    if camera_window is not None:
        return camera_window.get_dashboard_status()
    utc_day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return {
        "connected": False,
        "recording": False,
        "files_today": count_frames_saved_for_utc_day(utc_day),
        "utc_day": utc_day,
        "frame_size": "—",
    }


t=time.perf_counter()
tLive=t

img_timestamp_ref = None

use_camera_time = (config['CAMERA']['use_camera_time'] == "True")
record_rois = (config['CAMERA']['record_rois'] == "True")
CAMERA_VERBOSE = config['CAMERA'].get('verbose', 'False') == 'True'
FRAME_QUEUE_SIZE = config.getint("CAMERA", "frame_queue_size", fallback=64)
SAVE_QUEUE_SIZE = config.getint("CAMERA", "save_queue_size", fallback=256)
PNG_COMPRESSION = config.getint("CAMERA", "png_compression", fallback=1)
IMAGE_DISPLAY_SCALE = config.getint("CAMERA", "image_display_scale", fallback=4)
IMAGE_BORDER = 0
GRAPH_HEIGHT = config.getint("CAMERA", "graph_height", fallback=190)
ROI_GRAPHS_MIN_HEIGHT = 260
IMAGE_DISPLAY_REFRESH_HZ = config.getfloat(
    "CAMERA", "image_display_refresh_hz", fallback=2.0
)
ROI_VALUES_REFRESH_HZ = config.getfloat("CAMERA", "roi_values_refresh_hz", fallback=2.0)
ROI_PLOT_REFRESH_HZ = config.getfloat("CAMERA", "roi_plot_refresh_hz", fallback=1.0)


def _refresh_interval_ms(hz: float) -> int:
    return max(1, round(1000 / hz))


IMAGE_DISPLAY_REFRESH_INTERVAL_MS = _refresh_interval_ms(IMAGE_DISPLAY_REFRESH_HZ)
ROI_VALUES_REFRESH_INTERVAL_MS = _refresh_interval_ms(ROI_VALUES_REFRESH_HZ)
ROI_PLOT_REFRESH_INTERVAL_MS = _refresh_interval_ms(ROI_PLOT_REFRESH_HZ)
ROI_IDLE_PROCESS_STRIDE = config.getint("CAMERA", "roi_idle_process_stride", fallback=24)
ROI_TIME_PLOT_WINDOW_SECONDS = config.getint(
    "CAMERA", "roi_time_plot_window_seconds", fallback=60
)
ROI_TIME_PLOT_DEQUE_LENGTH = ROI_TIME_PLOT_WINDOW_SECONDS * config.getint(
    "CAMERA", "roi_time_plot_max_framerate", fallback=240
)
FRAME_READOUT_OVERHEAD_US = config.getint(
    "CAMERA", "frame_readout_overhead_us", fallback=5000
)
WINDOW_BOTTOM_BUFFER = 6
LEFT_COLUMN_X = 10
LEFT_COLUMN_GAP = 10
LEFT_PANEL_GAP = 8
ACQUISITION_PANEL_HEIGHT = 148
RIGHT_PANEL_WIDTH = 228
BRIGHTNESS_PANEL_HEIGHT = 152
CAM_PARAM_FRAMERATE_HZ = 240
CAM_PARAM_INTEGRATION_TIME = 262
DETECTOR_PANEL_HEIGHT = 256
CURSOR_READOUT_HEIGHT = 22
CURSOR_READOUT_INTERVAL_MS = 50

PANEL_BUTTON_STYLE = """
    QPushButton {
        font: 10pt "Segoe UI";
        color: white;
        background: rgb(50, 129, 140);
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
    }
    QPushButton:hover {
        background: rgb(42, 110, 120);
    }
    QPushButton:disabled {
        background: rgb(180, 190, 192);
        color: rgb(240, 240, 240);
    }
"""

PANEL_FIELD_STYLE = (
    'font: 9pt "Segoe UI";'
    "QComboBox, QSpinBox, QLineEdit { padding: 1px 4px; min-height: 22px; }"
)
PANEL_LABEL_STYLE = 'font: 9pt "Segoe UI"; color: rgb(50, 50, 50);'

PANEL_GROUP_STYLE = """
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


def _camera_log(*args, **kwargs) -> None:
    if CAMERA_VERBOSE:
        print(*args, **kwargs)


def callback(context,*args):#, aHandle, aStreamIndex):
    # Creating timezone-aware datetime object, in utc
    recording_timestamp = datetime.now(timezone.utc)
    # Dropping the timezone info
    recording_timestamp = recording_timestamp.replace(tzinfo=None)
    
    
    global img_timestamp_ref
    
    context.load_image(recording_timestamp,use_camera_time)

def _normalize_scene_pos(pos) -> QPointF:
    """Accept QPointF or nested tuples from pyqtgraph signal/proxy variants."""
    while isinstance(pos, (tuple, list)) and len(pos) == 1:
        pos = pos[0]
    if isinstance(pos, (tuple, list)) and len(pos) >= 2:
        return QPointF(float(pos[0]), float(pos[1]))
    return pos

def roi_profile_1d(region: numpy.ndarray) -> numpy.ndarray:
    """Collapse a 2D ROI array to a 1D profile (mean across the narrow axis)."""
    if region.ndim == 1:
        return region.astype(float, copy=False)
    if region.size == 0:
        return numpy.array([], dtype=float)
    height, width = region.shape[:2]
    data = region.astype(float, copy=False)
    if width <= height:
        return numpy.mean(data, axis=1)
    return numpy.mean(data, axis=0)


class MainWindow(QMainWindow):
    request_image_update = pyqtSignal(numpy.ndarray)
    image_display_update = pyqtSignal()
    roi_values_update = pyqtSignal()
    roi_plots_update = pyqtSignal()
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

        self.connected = False
        self.recording = False
        self.triggerEnabled = False
        self.integtime = 0
        self._last_camera_frame_rate: float | None = None
        self._recording_started_at: datetime | None = None
        self._coadd_frame_count = 1
        self._cached_exposure_options_us: list[int] | None = None
        self._cached_framerate_options_hz: list[float] | None = None
        self._applying_detector = False
        self._subtract_background_enabled = False
        self._background_img = None
        self._plot_flags_lock = threading.Lock()
        self._any_time_plot_enabled = False
        self._any_profile_plot_enabled = False

        self._setup_brightness_panel()
        self._setup_acquisition_panel()
        self._setup_roi_values_panel()
        self._setup_detector_panel()
        self._layout_window()
        install_nott_logo_header(self)

        self.connectSignalSlots()
        
        self.image=pg.ImageView(self.ui.frame_camera)
        self.image.ui.histogram.hide()
        self.image.ui.roiBtn.hide()
        self.image.ui.menuBtn.hide()
        self.image.show()
        self._layout_image_view()
        self.imageInit = False
        
        self.image.getView().setMouseEnabled(x = True, y = True)
        self.image.getView().setAspectLocked(True)
        self._setup_cursor_readout()
        
        self.request_image_update.connect(self.update_image, Qt.QueuedConnection)
        self.image_display_update.connect(
            self.on_image_display_update, Qt.QueuedConnection
        )
        self.roi_values_update.connect(
            self.on_roi_values_update, Qt.QueuedConnection
        )
        self.roi_plots_update.connect(
            self.on_roi_plots_update, Qt.QueuedConnection
        )
        self.frames_saved_today_updated.connect(
            self._update_frames_today_label, Qt.QueuedConnection
        )
        
        self.recording_lock = threading.Lock()
        self._coadd_lock = threading.Lock()
        self._frames_count_lock = threading.Lock()
        self._frames_saved_utc_day: str | None = None
        self._frames_saved_today = 0

        self.frame_rate_timer = QTimer()
        self.frame_rate_timer.timeout.connect(self.calculate_frame_rates)

        self._timing_refresh_timer = QTimer()
        self._timing_refresh_timer.timeout.connect(self._update_timing_labels)

        self._timing_labels_debounce = QTimer()
        self._timing_labels_debounce.setSingleShot(True)
        self._timing_labels_debounce.timeout.connect(self._update_timing_labels)

        self._cursor_readout_timer = QTimer()
        self._cursor_readout_timer.setSingleShot(True)
        self._cursor_readout_timer.timeout.connect(self._flush_cursor_readout)

        self.nbCameraImages = 0
        self.roi_tracking_frames = 0
        self.calculating_roi = False
        self.time_reference_frames = 0

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

        # Keep enough history for the rolling time-plot window.
        deque_length = ROI_TIME_PLOT_DEQUE_LENGTH

        self.timestamps = deque(maxlen = deque_length)
        self.coadd_frames_buffer = []
        self.roi_queue = queue.Queue(maxsize=FRAME_QUEUE_SIZE)
        self.dropped_frames = 0

        self._last_roi_profiles = None
        self._latest_brightness_results = None
        self._latest_frame_for_display = None
        self._latest_frame_lock = threading.Lock()
        self._display_emit_lock = threading.Lock()
        self._last_display_emit = 0.0
        self._roi_data_lock = threading.Lock()
        self._roi_emit_lock = threading.Lock()
        self._last_values_emit = 0.0
        self._last_plots_emit = 0.0
        self._idle_roi_frame_counter = 0
        self._profile_selection: tuple[str, ...] = ()
        self._profile_pens: dict[str, object] = {}
        self._cursor_readout_pending = None
        
        self.running = True
        threading.Thread(target=self.socket_server, daemon=True).start()
        self._update_timing_labels()

    def _setup_roi_values_panel(self) -> None:
        self.ui.scrollArea.hide()
        self.ui.scrollArea.setEnabled(False)
        self.ui.scrollArea.setFixedSize(0, 0)

        panel_width = roi_panel_width()
        panel_height = roi_panel_height()
        grid_height = panel_height - scaled(PANEL_CHROME_HEIGHT)

        self.roi_panel = QGroupBox("ROI values", self.ui.centralwidget)
        self.roi_panel.setGeometry(LEFT_COLUMN_X, 0, panel_width, panel_height)
        self.roi_panel.setFixedSize(panel_width, panel_height)
        self.roi_panel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.roi_panel.setStyleSheet(PANEL_GROUP_STYLE)

        grid_host = QWidget(self.roi_panel)
        grid_host.setMinimumSize(panel_width - scaled(12), grid_height)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(scaled(6), scaled(2), scaled(6), scaled(4))
        grid.setHorizontalSpacing(scaled(GRID_H_SPACING))
        grid.setVerticalSpacing(0)

        for column, (text, width, alignment) in enumerate(
            (
                ("", NAME_WIDTH, Qt.AlignLeft),
                ("Time", PLOT_WIDTH, Qt.AlignCenter),
                ("1D", PLOT_WIDTH, Qt.AlignCenter),
                ("Min", VALUE_WIDTH, Qt.AlignRight),
                ("Max", VALUE_WIDTH, Qt.AlignRight),
                ("Avg", VALUE_WIDTH, Qt.AlignRight),
            )
        ):
            header = QLabel(text, grid_host)
            header.setMinimumWidth(scaled(width))
            header.setFixedHeight(scaled(HEADER_HEIGHT))
            header.setStyleSheet(header_style())
            header.setAlignment(alignment | Qt.AlignVCenter)
            grid.addWidget(header, 0, column)
            if column >= 3:
                grid.setColumnStretch(column, 1)

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
            roi_widget = RoiWidget(
                grid_host,
                grid,
                index,
                index,
                color,
                deque_length=ROI_TIME_PLOT_DEQUE_LENGTH,
            )
            roi_widget.enable_profile_click(self._show_roi_profile)
            roi_widget.time_plot_checkbox.stateChanged.connect(
                self._on_roi_plot_selection_changed
            )
            roi_widget.profile_plot_checkbox.stateChanged.connect(
                self._on_roi_plot_selection_changed
            )
            self.roi_widgets.append(roi_widget)

        self._refresh_plot_enable_flags()
        outer = QGridLayout(self.roi_panel)
        outer.setContentsMargins(6, 10, 6, 4)
        outer.addWidget(grid_host, 0, 0)
        self.roi_panel.show()
        self.roi_panel.raise_()

    def _setup_brightness_panel(self) -> None:
        group = self.ui.groupBox
        group.setStyleSheet(PANEL_GROUP_STYLE)
        group.setTitle("Brightness levels")

        outer = QVBoxLayout(group)
        outer.setContentsMargins(8, 12, 8, 8)
        outer.setSpacing(6)

        self.ui.button_autobrightness.setStyleSheet(PANEL_BUTTON_STYLE)
        self.ui.button_autobrightness.setMinimumHeight(28)
        outer.addWidget(self.ui.button_autobrightness)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        field_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        def _add_row(row: int, text: str, widget: QLineEdit) -> None:
            label = QLabel(text, group)
            label.setStyleSheet(PANEL_LABEL_STYLE)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            grid.addWidget(label, row, 0, Qt.AlignLeft | Qt.AlignVCenter)
            widget.setSizePolicy(field_policy)
            widget.setStyleSheet(PANEL_FIELD_STYLE)
            grid.addWidget(widget, row, 1, Qt.AlignRight | Qt.AlignVCenter)

        _add_row(0, "Min:", self.ui.lineEdit_minBrightness)
        _add_row(1, "Max:", self.ui.lineEdit_maxBrightness)
        outer.addLayout(grid)

        self.ui.button_manualbrightness.setText("Apply")
        self.ui.button_manualbrightness.setStyleSheet(PANEL_BUTTON_STYLE)
        self.ui.button_manualbrightness.setMinimumHeight(28)
        outer.addWidget(self.ui.button_manualbrightness)

        self.ui.label.hide()
        self.ui.label_5.hide()

    def _setup_acquisition_panel(self) -> None:
        old_conn_host = self.ui.label_connection.parentWidget()
        old_bg_host = self.ui.button_takebackground.parentWidget()

        self.acquisition_panel = QGroupBox("Acquisition", self.ui.centralwidget)
        self.acquisition_panel.setStyleSheet(PANEL_GROUP_STYLE)

        outer = QVBoxLayout(self.acquisition_panel)
        outer.setContentsMargins(8, 12, 8, 8)
        outer.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        conn_grid = QGridLayout()
        conn_grid.setContentsMargins(0, 0, 0, 0)
        conn_grid.setHorizontalSpacing(8)
        conn_grid.setVerticalSpacing(8)

        checkbox_style = 'font: 9pt "Segoe UI"; color: rgb(50, 50, 50);'
        for widget in (
            self.ui.label_connection,
            self.ui.label_recording,
        ):
            widget.setStyleSheet(PANEL_LABEL_STYLE)
        for widget in (
            self.ui.checkBox_saveframes,
            self.ui.checkBox_subtractbackground,
        ):
            widget.setStyleSheet(checkbox_style)

        button_policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        for button in (
            self.ui.button_connect,
            self.ui.button_record,
            self.ui.button_takebackground,
            self.ui.button_parameters,
        ):
            button.setStyleSheet(PANEL_BUTTON_STYLE)
            button.setSizePolicy(button_policy)
            button.setFixedHeight(28)
            button.setMinimumWidth(scaled(88))

        conn_grid.addWidget(self.ui.label_connection, 0, 0, Qt.AlignLeft | Qt.AlignVCenter)
        conn_grid.addWidget(self.ui.button_connect, 0, 1, Qt.AlignLeft | Qt.AlignVCenter)
        conn_grid.addWidget(self.ui.label_recording, 1, 0, Qt.AlignLeft | Qt.AlignVCenter)
        conn_grid.addWidget(self.ui.button_record, 1, 1, Qt.AlignLeft | Qt.AlignVCenter)

        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(6)
        left_col.addLayout(conn_grid)
        left_col.addWidget(self.ui.checkBox_saveframes)

        bg_row = QHBoxLayout()
        bg_row.setContentsMargins(0, 0, 0, 0)
        bg_row.setSpacing(8)
        bg_row.addWidget(self.ui.button_takebackground)
        bg_row.addWidget(self.ui.checkBox_subtractbackground)

        top_row.addLayout(left_col)
        top_row.addStretch(1)
        top_row.addLayout(bg_row)
        top_row.addStretch(1)
        top_row.addWidget(self.ui.button_parameters, 0, Qt.AlignRight | Qt.AlignVCenter)
        outer.addLayout(top_row)

        self.label_frames_today = QLabel(self.acquisition_panel)
        self.label_frames_today.setStyleSheet(
            'font: 9pt "Segoe UI"; color: rgb(70, 70, 70);'
        )
        self._update_frames_today_label(0, datetime.now(timezone.utc).strftime("%Y%m%d"))
        outer.addWidget(self.label_frames_today)

        for host in (old_conn_host, old_bg_host):
            if host is not None and host is not self.acquisition_panel:
                host.hide()
                host.setFixedSize(0, 0)

    def _utc_day_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d")

    def _count_frames_for_utc_day(self, utc_day: str) -> int:
        directory = Path(self.frame_directory) / utc_day
        if not directory.is_dir():
            return 0
        return sum(1 for path in directory.iterdir() if path.suffix.lower() == ".png")

    def _refresh_frames_saved_today(self) -> None:
        utc_day = self._utc_day_key()
        disk_count = self._count_frames_for_utc_day(utc_day)
        with self._frames_count_lock:
            if self._frames_saved_utc_day != utc_day:
                self._frames_saved_utc_day = utc_day
                self._frames_saved_today = disk_count
            else:
                self._frames_saved_today = max(self._frames_saved_today, disk_count)
            count = self._frames_saved_today
            day = self._frames_saved_utc_day
        self.frames_saved_today_updated.emit(count, day)

    def _maybe_refresh_frames_saved_on_day_change(self) -> None:
        utc_day = self._utc_day_key()
        with self._frames_count_lock:
            if self._frames_saved_utc_day == utc_day:
                return
        self._refresh_frames_saved_today()

    def _on_frame_saved_to_disk(self, filepath: str) -> None:
        saved_day = Path(filepath).parent.name
        with self._frames_count_lock:
            if self._frames_saved_utc_day != saved_day:
                self._frames_saved_utc_day = saved_day
                self._frames_saved_today = self._count_frames_for_utc_day(saved_day)
            else:
                self._frames_saved_today += 1
            count = self._frames_saved_today
            day = self._frames_saved_utc_day
        self.frames_saved_today_updated.emit(count, day)

    def _update_frames_today_label(self, count: int, utc_day: str) -> None:
        self.label_frames_today.setText(
            f"Frames saved today ({utc_day} UTC): {count:,}"
        )

    def _setup_detector_panel(self) -> None:
        self.ui.groupBox_2.hide()

        self.detector_panel = QGroupBox("Detector setup", self.ui.centralwidget)
        self.detector_panel.setStyleSheet(PANEL_GROUP_STYLE)

        outer = QVBoxLayout(self.detector_panel)
        outer.setContentsMargins(8, 12, 8, 8)
        outer.setSpacing(6)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        field_style = PANEL_FIELD_STYLE
        label_style = PANEL_LABEL_STYLE
        field_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        def _form_label(text: str) -> QLabel:
            label = QLabel(text, self.detector_panel)
            label.setStyleSheet(label_style)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            return label

        def _add_field(row: int, text: str, widget: QWidget) -> None:
            grid.addWidget(_form_label(text), row, 0, Qt.AlignLeft | Qt.AlignVCenter)
            widget.setSizePolicy(field_policy)
            widget.setStyleSheet(field_style)
            grid.addWidget(widget, row, 1, Qt.AlignRight | Qt.AlignVCenter)

        self.combo_exposure = QComboBox(self.detector_panel)
        self.combo_exposure.setEditable(False)
        self.combo_exposure.setMinimumWidth(104)
        _add_field(0, "Exposure (ms):", self.combo_exposure)

        self.combo_framerate = QComboBox(self.detector_panel)
        self.combo_framerate.setEditable(False)
        self.combo_framerate.setMinimumWidth(104)
        _add_field(1, "Frame rate (Hz):", self.combo_framerate)

        self.spin_coadd = QSpinBox(self.detector_panel)
        self.spin_coadd.setRange(1, 999)
        self.spin_coadd.setValue(1)
        self.spin_coadd.setMinimumWidth(104)
        _add_field(2, "Coadd:", self.spin_coadd)

        outer.addLayout(grid)

        self.btn_apply_detector = QPushButton("Apply to camera", self.detector_panel)
        self.btn_apply_detector.setStyleSheet(PANEL_BUTTON_STYLE)
        self.btn_apply_detector.clicked.connect(self._apply_detector_settings)
        outer.addWidget(self.btn_apply_detector)

        divider = QFrame(self.detector_panel)
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: rgb(210, 220, 222);")
        outer.addWidget(divider)

        summary_style = 'font: 9pt "Segoe UI"; color: rgb(70, 70, 70);'
        self.label_total_integ = QLabel("Total integ.: —", self.detector_panel)
        self.label_acq_time = QLabel("Acq. time: —", self.detector_panel)
        self.label_acq_efficiency = QLabel("Acq. efficiency: —", self.detector_panel)
        self.label_measured_rate = QLabel("Measured: —", self.detector_panel)
        self.label_frame_size = QLabel("Frame size: —", self.detector_panel)
        self.label_recording_elapsed = QLabel("", self.detector_panel)

        for label in (
            self.label_total_integ,
            self.label_acq_time,
            self.label_acq_efficiency,
            self.label_measured_rate,
            self.label_frame_size,
        ):
            label.setStyleSheet(summary_style)
            label.setWordWrap(True)
            label.setMinimumHeight(14)
            outer.addWidget(label)

        self.label_recording_elapsed.setStyleSheet(
            'font: 9pt "Segoe UI"; color: rgb(50, 129, 140);'
        )
        outer.addWidget(self.label_recording_elapsed)

        self.spin_coadd.valueChanged.connect(self._on_coadd_changed)
        self.combo_exposure.currentIndexChanged.connect(
            self._schedule_timing_labels_update
        )
        self.combo_framerate.currentIndexChanged.connect(
            self._on_framerate_selection_changed
        )
        self._populate_detector_option_combos()
        self._set_detector_controls_enabled()

    def _selected_integration_us(self) -> int | None:
        if not hasattr(self, "combo_exposure"):
            return None
        value = self.combo_exposure.currentData()
        if value is None:
            return None
        return int(value)

    def _selected_framerate_hz(self) -> float | None:
        if not hasattr(self, "combo_framerate"):
            return None
        value = self.combo_framerate.currentData()
        if value is None:
            return None
        return float(value)

    def _select_combo_value(self, combo: QComboBox, value, *, tolerance: float = 0.05) -> None:
        for index in range(combo.count()):
            item_value = combo.itemData(index)
            if item_value is None:
                continue
            if isinstance(value, float):
                if abs(float(item_value) - float(value)) <= tolerance:
                    combo.setCurrentIndex(index)
                    return
            elif int(item_value) == int(value):
                combo.setCurrentIndex(index)
                return
        if combo.count() > 0:
            combo.setCurrentIndex(0)

    def _populate_detector_option_combos(self, *, refresh: bool = False) -> None:
        if not hasattr(self, "combo_exposure"):
            return

        if refresh or self._cached_exposure_options_us is None:
            if self.connected:
                self._cached_exposure_options_us = get_integration_time_options_us(
                    self.interface
                )
                self._cached_framerate_options_hz = get_framerate_options_hz(
                    self.interface
                )
            else:
                self._cached_exposure_options_us = fallback_integration_times_us()
                self._cached_framerate_options_hz = fallback_framerate_options_hz()

        exposure_options = self._cached_exposure_options_us
        framerate_options = ensure_default_framerate_option(
            self._cached_framerate_options_hz
        )

        self.combo_framerate.blockSignals(True)
        self.combo_framerate.clear()
        for framerate_hz in framerate_options:
            self.combo_framerate.addItem(
                format_framerate_hz(framerate_hz),
                framerate_hz,
            )
        self.combo_framerate.blockSignals(False)
        self._select_default_framerate()
        self._rebuild_exposure_combo()

    def _selected_framerate_for_exposure_limits(self) -> float | None:
        selected = self._selected_framerate_hz()
        if selected is not None:
            return selected
        return DEFAULT_FRAMERATE_HZ

    def _rebuild_exposure_combo(self, *, keep_selection: bool = True) -> None:
        if not hasattr(self, "combo_exposure"):
            return

        previous_us = self._selected_integration_us() if keep_selection else None
        exposure_options = integration_time_options_for_framerate(
            self._cached_exposure_options_us or fallback_integration_times_us(),
            self._selected_framerate_for_exposure_limits(),
        )

        self.combo_exposure.blockSignals(True)
        self.combo_exposure.clear()
        for integration_us in exposure_options:
            self.combo_exposure.addItem(
                format_exposure_ms(integration_us),
                integration_us,
            )
        if previous_us is not None:
            self._select_combo_value(self.combo_exposure, previous_us)
        elif self.combo_exposure.count() > 0:
            self.combo_exposure.setCurrentIndex(0)
        self.combo_exposure.blockSignals(False)

    def _on_framerate_selection_changed(self) -> None:
        self._rebuild_exposure_combo()
        self._schedule_timing_labels_update()

    def _select_default_framerate(self) -> None:
        if not hasattr(self, "combo_framerate") or self.combo_framerate.count() == 0:
            return
        self.combo_framerate.blockSignals(True)
        self._select_combo_value(self.combo_framerate, DEFAULT_FRAMERATE_HZ)
        self.combo_framerate.blockSignals(False)

    def _format_duration_us(self, us: float | None) -> str:
        if us is None:
            return "—"
        if us >= 1_000_000:
            return f"{us / 1_000_000:.2f} s"
        if us >= 1000:
            return f"{us / 1000:.2f} ms"
        return f"{us:.0f} µs"

    def _read_integtime_us(self) -> int | None:
        selected = self._selected_integration_us()
        if selected is not None:
            return selected
        if not self.connected:
            return getattr(self, "integtime", None) or None
        try:
            return int(self.interface.getparam_idx_int32(CAM_PARAM_INTEGRATION_TIME, 0))
        except Exception:
            return getattr(self, "integtime", None) or None

    def _configured_framerate_hz(self) -> float | None:
        selected = self._selected_framerate_hz()
        if selected is not None:
            return selected
        return None

    def _coadd_count(self) -> int:
        return max(1, getattr(self, "_coadd_frame_count", 1))

    def _schedule_timing_labels_update(self) -> None:
        if hasattr(self, "_timing_labels_debounce"):
            self._timing_labels_debounce.start(50)
        else:
            self._update_timing_labels()

    def _frame_period_us(self) -> tuple[float | None, bool]:
        configured_hz = self._configured_framerate_hz()
        if configured_hz and configured_hz > 0:
            return 1e6 / configured_hz, False
        if self._last_camera_frame_rate and self._last_camera_frame_rate > 0:
            return 1e6 / self._last_camera_frame_rate, True
        dit_us = self._read_integtime_us()
        if dit_us is not None:
            return dit_us + FRAME_READOUT_OVERHEAD_US, False
        return None, False

    def _timing_snapshot(self) -> dict:
        dit_us = self._read_integtime_us()
        coadd_n = self._coadd_count()
        frame_period_us, measured = self._frame_period_us()
        total_integ_us = dit_us * coadd_n if dit_us is not None else None
        if frame_period_us is not None:
            acq_per_output_us = frame_period_us * coadd_n
        else:
            acq_per_output_us = None
        frame_rate_hz = (
            self._last_camera_frame_rate
            if measured and self._last_camera_frame_rate
            else None
        )
        acq_efficiency_pct = None
        if (
            total_integ_us is not None
            and acq_per_output_us is not None
            and acq_per_output_us > 0
        ):
            acq_efficiency_pct = 100.0 * total_integ_us / acq_per_output_us
        return {
            "dit_us": dit_us,
            "coadd_n": coadd_n,
            "total_integ_us": total_integ_us,
            "frame_period_us": frame_period_us,
            "acq_per_output_us": acq_per_output_us,
            "frame_rate_hz": frame_rate_hz,
            "measured": measured,
            "acq_efficiency_pct": acq_efficiency_pct,
        }

    def _frame_size_text(self) -> str:
        if not self.imageInit:
            return "—"
        img = self.image.getImageItem().image
        if img is None or len(img.shape) < 2:
            return "—"
        return f"{int(img.shape[1])} × {int(img.shape[0])}"

    def _update_timing_labels(self) -> None:
        if not hasattr(self, "label_total_integ"):
            return

        snap = self._timing_snapshot()
        coadd_n = snap["coadd_n"]

        if coadd_n > 1:
            self.label_total_integ.setText(
                "Total integ.: "
                f"{self._format_duration_us(snap['total_integ_us'])} (×{coadd_n})"
            )
            self.label_acq_time.setText(
                "Acq. time/output: "
                f"{self._format_duration_us(snap['acq_per_output_us'])}"
            )
        else:
            self.label_total_integ.setText(
                "Total integ.: "
                f"{self._format_duration_us(snap['total_integ_us'])}"
            )
            self.label_acq_time.setText(
                "Acq. time/frame: "
                f"{self._format_duration_us(snap['acq_per_output_us'])}"
            )

        efficiency = snap.get("acq_efficiency_pct")
        if efficiency is not None:
            self.label_acq_efficiency.setText(f"Acq. efficiency: {efficiency:.1f}%")
        else:
            self.label_acq_efficiency.setText("Acq. efficiency: —")

        if snap["frame_rate_hz"]:
            self.label_measured_rate.setText(
                f"Measured: {snap['frame_rate_hz']:.1f} Hz"
            )
        elif snap["frame_period_us"] is not None and self._configured_framerate_hz():
            self.label_measured_rate.setText(
                f"Configured: {self._configured_framerate_hz():.2f} Hz"
            )
        else:
            self.label_measured_rate.setText("Measured: —")

        self.label_frame_size.setText(f"Frame size: {self._frame_size_text()}")

        if self.recording and self._recording_started_at is not None:
            elapsed = (
                datetime.now(timezone.utc).replace(tzinfo=None)
                - self._recording_started_at
            )
            elapsed_text = str(elapsed).split(".")[0]
            self.label_recording_elapsed.setText(f"Recording: {elapsed_text}")
        else:
            self.label_recording_elapsed.setText("")

    def _set_detector_controls_enabled(self) -> None:
        if not hasattr(self, "combo_exposure"):
            return
        camera_controls_enabled = (
            self.connected and not self.recording and not self._applying_detector
        )
        self.combo_exposure.setEnabled(camera_controls_enabled)
        self.combo_framerate.setEnabled(camera_controls_enabled)
        self.btn_apply_detector.setEnabled(camera_controls_enabled)

    def _load_detector_settings_from_camera(
        self, *, use_default_framerate: bool = False
    ) -> None:
        if not self.connected:
            return
        self._populate_detector_option_combos(refresh=True)
        try:
            integ_us = int(
                self.interface.getparam_idx_int32(CAM_PARAM_INTEGRATION_TIME, 0)
            )
            self.integtime = integ_us
            self.combo_exposure.blockSignals(True)
            self._select_combo_value(self.combo_exposure, integ_us)
            self.combo_exposure.blockSignals(False)

            if use_default_framerate:
                self._select_default_framerate()
            else:
                framerate_hz = float(
                    self.interface.getparam_single(CAM_PARAM_FRAMERATE_HZ)
                )
                self.combo_framerate.blockSignals(True)
                self._select_combo_value(self.combo_framerate, framerate_hz)
                self.combo_framerate.blockSignals(False)
        except Exception:
            pass
        self._update_timing_labels()
        if use_default_framerate:
            self._apply_detector_settings()

    def _apply_detector_settings(self) -> None:
        if (
            not self.connected
            or self.recording
            or self._applying_detector
        ):
            return
        integ_us = self._selected_integration_us()
        framerate_hz = self._selected_framerate_hz()
        if integ_us is None or framerate_hz is None:
            return

        self._applying_detector = True
        self.btn_apply_detector.setEnabled(False)
        self.combo_exposure.setEnabled(False)
        self.combo_framerate.setEnabled(False)

        def worker() -> None:
            error: Exception | None = None
            try:
                self.interface.setparam_idx_int32(
                    CAM_PARAM_INTEGRATION_TIME, 0, integ_us
                )
                self.interface.setparam_single(
                    CAM_PARAM_FRAMERATE_HZ, framerate_hz
                )
            except Exception as exc:
                error = exc

            def finish() -> None:
                self._applying_detector = False
                if error is None:
                    self.integtime = integ_us
                    _camera_log(
                        f"Detector settings applied: DIT={integ_us} us, "
                        f"frame rate={framerate_hz:.2f} Hz"
                    )
                else:
                    _camera_log(f"Failed to apply detector settings: {error}")
                self._set_detector_controls_enabled()
                self._update_timing_labels()

            QTimer.singleShot(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _on_coadd_changed(self, value: int) -> None:
        self._coadd_frame_count = max(1, value)
        if self._coadd_frame_count <= 1:
            with self._coadd_lock:
                self.coadd_frames_buffer.clear()
        self._schedule_timing_labels_update()

    def _fit_detector_image(self) -> None:
        if not hasattr(self, "image") or not getattr(self, "imageInit", False):
            return
        img = self.image.getImageItem().image
        if img is None:
            return
        img_h, img_w = img.shape[:2]
        if img_w <= 0 or img_h <= 0:
            return

        widget_w = max(1, self.image.width())
        widget_h = max(1, self.image.height())
        view = self.image.getView()
        view.setAspectLocked(True)

        # Scale to cover the view (zoom in, crop if needed) rather than letterbox.
        scale = max(widget_w / img_w, widget_h / img_h)
        visible_w = widget_w / scale
        visible_h = widget_h / scale
        x0 = (img_w - visible_w) / 2.0
        y0 = (img_h - visible_h) / 2.0
        view.setRange(
            xRange=(x0, x0 + visible_w),
            yRange=(y0, y0 + visible_h),
            padding=0,
        )

    def _layout_image_view(self) -> None:
        if not hasattr(self, "image"):
            return
        width = max(1, self.ui.frame_camera.width())
        height = max(1, self.ui.frame_camera.height())
        self.image.setGeometry(0, 0, width, height)
        if hasattr(self, "_cursor_readout"):
            readout_h = scaled(CURSOR_READOUT_HEIGHT)
            self._cursor_readout.setGeometry(0, height - readout_h, width, readout_h)
            self._cursor_readout.raise_()
        self._fit_detector_image()

    def _setup_cursor_readout(self) -> None:
        self._cursor_readout = QLabel(self.ui.frame_camera)
        self._cursor_readout.setText("Pixel: —")
        self._cursor_readout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._cursor_readout.setStyleSheet(
            'font: 9pt "Consolas", monospace;'
            " color: rgb(50, 50, 50);"
            " background-color: rgba(255, 255, 255, 215);"
            " padding-left: 6px;"
        )
        scene = self.image.getView().scene()
        scene.sigMouseMoved.connect(self._update_cursor_readout)

    def _roi_name_at(self, x: int, y: int) -> str | None:
        for roi_widget in self.roi_widgets:
            roi = roi_widget.roi
            if roi is None:
                continue
            rx, ry = roi.pos()
            rw, rh = roi.size()
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return roi_widget.name
        return None

    def _should_process_roi_frame(self, recording: bool) -> bool:
        if recording:
            return True
        self._idle_roi_frame_counter += 1
        return self._idle_roi_frame_counter % ROI_IDLE_PROCESS_STRIDE == 0

    def _profile_pen(self, roi_widget) -> object:
        pen = self._profile_pens.get(roi_widget.name)
        if pen is None:
            pen = pg.mkPen(
                color=(
                    roi_widget.color.red(),
                    roi_widget.color.green(),
                    roi_widget.color.blue(),
                ),
                width=2,
            )
            self._profile_pens[roi_widget.name] = pen
        return pen

    def _update_cursor_readout(self, pos) -> None:
        self._cursor_readout_pending = pos
        if not self._cursor_readout_timer.isActive():
            self._cursor_readout_timer.start(CURSOR_READOUT_INTERVAL_MS)

    def _flush_cursor_readout(self) -> None:
        pos = self._cursor_readout_pending
        if pos is None:
            return
        if not getattr(self, "imageInit", False):
            self._cursor_readout.setText("Pixel: —")
            return

        img = self.image.getImageItem().image
        if img is None:
            self._cursor_readout.setText("Pixel: —")
            return

        try:
            scene_pos = _normalize_scene_pos(pos)
            mouse = self.image.getView().mapSceneToView(scene_pos)
        except (TypeError, ValueError):
            return
        x = int(mouse.x())
        y = int(mouse.y())
        img_h, img_w = img.shape[:2]
        if x < 0 or y < 0 or x >= img_w or y >= img_h:
            self._cursor_readout.setText("Pixel: —")
            return

        adu = float(img[y, x])
        roi_name = self._roi_name_at(x, y)
        if roi_name:
            self._cursor_readout.setText(
                f"Pixel: x={x}, y={y}  ADU={adu:.1f}  [{roi_name}]"
            )
        else:
            self._cursor_readout.setText(f"Pixel: x={x}, y={y}  ADU={adu:.1f}")

    def _layout_window(self) -> None:
        img_h = config.getint("CAMERA", "window_h", fallback=150)
        img_w = config.getint("CAMERA", "window_w", fallback=160)

        camera_w = img_w * IMAGE_DISPLAY_SCALE + IMAGE_BORDER
        camera_h = img_h * IMAGE_DISPLAY_SCALE + IMAGE_BORDER
        graph_gap = 8
        panel_width = roi_panel_width()
        panel_height = roi_panel_height()
        acquisition_panel_h = scaled(ACQUISITION_PANEL_HEIGHT)
        detector_panel_h = scaled(DETECTOR_PANEL_HEIGHT)
        right_panel_w = scaled(RIGHT_PANEL_WIDTH)
        brightness_panel_h = scaled(BRIGHTNESS_PANEL_HEIGHT)
        left_panel_gap = scaled(LEFT_PANEL_GAP)
        left_column_gap = scaled(LEFT_COLUMN_GAP)
        acquisition_y = scaled(8)

        camera_x = LEFT_COLUMN_X + panel_width + left_column_gap
        right_x = camera_x + camera_w + scaled(12)
        content_right = right_x + right_panel_w
        acquisition_w = content_right - LEFT_COLUMN_X

        if hasattr(self, "acquisition_panel"):
            self.acquisition_panel.setFixedWidth(acquisition_w)
            self.acquisition_panel.adjustSize()
            acquisition_panel_h = max(
                scaled(ACQUISITION_PANEL_HEIGHT),
                self.acquisition_panel.sizeHint().height(),
            )
            self.acquisition_panel.setGeometry(
                LEFT_COLUMN_X, acquisition_y, acquisition_w, acquisition_panel_h
            )
            self.acquisition_panel.setFixedHeight(acquisition_panel_h)

        content_top = acquisition_y + acquisition_panel_h + left_panel_gap
        detector_y = content_top
        roi_y = detector_y + detector_panel_h + left_panel_gap

        if hasattr(self, "detector_panel"):
            self.detector_panel.setGeometry(
                LEFT_COLUMN_X, detector_y, panel_width, detector_panel_h
            )
            self.detector_panel.setFixedSize(panel_width, detector_panel_h)

        self.roi_panel.setGeometry(LEFT_COLUMN_X, roi_y, panel_width, panel_height)
        self.roi_panel.setFixedSize(panel_width, panel_height)

        self.ui.frame_camera.setMinimumSize(0, 0)
        self.ui.frame_camera.setGeometry(camera_x, content_top, camera_w, camera_h)
        self.ui.frame_camera.setFixedSize(camera_w, camera_h)

        graphs_height = scaled(max(GRAPH_HEIGHT, ROI_GRAPHS_MIN_HEIGHT))
        upper_bottom = max(content_top + camera_h, roi_y + panel_height)
        graph_y = upper_bottom + graph_gap
        graphs_w = content_right - LEFT_COLUMN_X
        self.ui.frame_roi_graph.setMinimumSize(0, 0)
        self.ui.frame_roi_graph.setGeometry(LEFT_COLUMN_X, graph_y, graphs_w, graphs_height)
        self.ui.frame_roi_graph.setFixedSize(graphs_w, graphs_height)
        self.ui.frame_roi_graph.show()
        self.ui.frame_roi_graph.raise_()
        self._fit_roi_plot()

        self.ui.groupBox.setGeometry(
            right_x, content_top, right_panel_w, brightness_panel_h
        )
        self.ui.groupBox.setFixedSize(right_panel_w, brightness_panel_h)
        self.ui.groupBox_2.hide()

        content_h = max(
            graph_y + graphs_height + WINDOW_BOTTOM_BUFFER,
            roi_y + panel_height + WINDOW_BOTTOM_BUFFER,
        )
        window_w = max(content_right + scaled(24), camera_x + camera_w + scaled(40))
        self.ui.centralwidget.setMinimumSize(0, 0)
        self.ui.centralwidget.setFixedSize(window_w, content_h)
        window_h = content_h + self.menuBar().height()
        if self.statusBar() is not None:
            window_h += self.statusBar().height()
        self.setMinimumSize(0, 0)
        self.setFixedSize(window_w, window_h)
        self._layout_image_view()
        self._raise_overlay_widgets()

    def _raise_overlay_widgets(self) -> None:
        self.ui.scrollArea.lower()
        if hasattr(self, "acquisition_panel"):
            self.acquisition_panel.show()
            self.acquisition_panel.raise_()
        if hasattr(self, "roi_panel"):
            self.roi_panel.show()
            self.roi_panel.raise_()
        if hasattr(self, "detector_panel"):
            self.detector_panel.raise_()
        self.ui.frame_roi_graph.raise_()
        if hasattr(self, "image"):
            self.image.show()
            self.image.raise_()
        if hasattr(self, "_cursor_readout"):
            self._cursor_readout.raise_()

    def _setup_roi_plot(self) -> None:
        if hasattr(self, "pw_roi"):
            return

        root = QVBoxLayout(self.ui.frame_roi_graph)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(2)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        self.btn_rescale_roi_y = QPushButton("Rescale Y", self.ui.frame_roi_graph)
        self.btn_rescale_roi_y.setStyleSheet(PANEL_BUTTON_STYLE)
        self.btn_rescale_roi_y.setToolTip(
            "Auto-scale the Y axis on both ROI plots"
        )
        self.btn_rescale_roi_y.clicked.connect(self._rescale_roi_plots_y)
        toolbar.addWidget(self.btn_rescale_roi_y)
        root.addLayout(toolbar)

        plots_host = QWidget(self.ui.frame_roi_graph)
        outer = QHBoxLayout(plots_host)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(scaled(8))

        time_host = QWidget(plots_host)
        time_layout = QVBoxLayout(time_host)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(2)

        time_title = QLabel("ROI brightness vs time", time_host)
        time_title.setStyleSheet(PANEL_LABEL_STYLE)
        time_layout.addWidget(time_title)

        axis = pg.DateAxisItem(orientation='bottom')
        self.pw_roi = pg.PlotWidget(axisItems={'bottom': axis})
        self.pw_roi.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.pw_roi.showGrid(x=True, y=True, alpha=0.25)

        plot_item = self.pw_roi.getPlotItem()
        plot_item.addLegend(offset=(8, 8))
        plot_item.setLabel(axis='left', text='ROI brightness [ADU]')
        plot_item.setLabel(axis='bottom', text='Time [UTC]')
        plot_item.getAxis('left').setWidth(58)
        plot_item.layout.setContentsMargins(8, 8, 8, 8)
        plot_item.enableAutoRange(axis='y', enable=True)
        plot_item.enableAutoRange(axis='x', enable=False)

        self._time_plot_curves = {}
        self._time_plot_y_autorange = True
        time_layout.addWidget(self.pw_roi)
        outer.addWidget(time_host, stretch=1, alignment=Qt.AlignTop)

        profile_host = QWidget(plots_host)
        profile_layout = QVBoxLayout(profile_host)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(2)

        self._profile_title = QLabel(
            "ROI profile — check 1D or click an ROI", profile_host
        )
        self._profile_title.setStyleSheet(PANEL_LABEL_STYLE)
        profile_layout.addWidget(self._profile_title)

        self.pw_roi_profile = pg.PlotWidget()
        self.pw_roi_profile.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.pw_roi_profile.showGrid(x=True, y=True, alpha=0.25)
        profile_plot_item = self.pw_roi_profile.getPlotItem()
        profile_plot_item.addLegend(offset=(8, 8))
        profile_plot_item.setLabel(axis='left', text='ADU')
        profile_plot_item.setLabel(axis='bottom', text='Pixel index')
        profile_plot_item.getAxis('left').setWidth(58)
        profile_plot_item.layout.setContentsMargins(8, 8, 8, 8)
        profile_plot_item.enableAutoRange(axis='y', enable=True)
        self._profile_plot_curves = {}
        self._profile_y_autorange = True
        profile_layout.addWidget(self.pw_roi_profile)
        outer.addWidget(profile_host, stretch=1, alignment=Qt.AlignTop)

        outer.setStretch(0, 1)
        outer.setStretch(1, 1)
        root.addWidget(plots_host, stretch=1)

    def _rescale_roi_plots_y(self) -> None:
        if hasattr(self, "pw_roi"):
            self._auto_range_plot(self.pw_roi)
        if hasattr(self, "pw_roi_profile"):
            self._auto_range_plot(self.pw_roi_profile)

    def _fit_roi_plot(self) -> None:
        if hasattr(self, "pw_roi"):
            self.pw_roi.updateGeometry()
        if hasattr(self, "pw_roi_profile"):
            self.pw_roi_profile.updateGeometry()
    
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
                    _camera_log(f"Message received: {message}")
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
            
        _camera_log("Stopping zmq thread")

    
    def is_coadd_enabled(self):
        return self._coadd_count() > 1

    def nb_coadd_frames(self):
        return self._coadd_count()

    def save_frame_write_redis(self, filepath, img, timestamp):
        if not self.frame_writer.enqueue(filepath, img, timestamp, self.integtime):
            _camera_log(
                f"Save queue full; dropped frame write "
                f"({self.frame_writer.dropped} total)"
            )

    def process_frame(self):
        base_path = self.frame_directory
        _camera_log(f"base directory: {base_path}")
        while self.running:
            try:
                item = self.roi_queue.get(timeout=0.2)
            except queue.Empty:
                continue
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

            if recording or not self.is_coadd_enabled():
                if self._should_process_roi_frame(recording):
                    self.process_roi(img, timestamp, coadded_frame=False)
                
            #If coadding, check to see if we have the required amount of frames
            coadd_in_process = False
            if self.is_coadd_enabled():
                with self._coadd_lock:
                    self.coadd_frames_buffer.append(img)
                    ready = (
                        len(self.coadd_frames_buffer)
                        >= self._coadd_frame_count
                    )
                    if ready:
                        arr = numpy.array(self.coadd_frames_buffer)
                        self.coadd_frames_buffer.clear()
                    else:
                        coadd_in_process = True
                if ready:
                    img = numpy.average(arr, axis=0).astype(numpy.uint16)
                    self.process_roi(img, timestamp, coadded_frame=True)
    
    def load_roi_config(self, config):
        self.roi_config = []
        i = 1
        for roi_widget in self.roi_widgets:
            try:
                roi_config = self.load_roi_from_config(config, roi_widget.name)
            except:
                _camera_log(f'Failed to load roi configuration for {roi_widget.name}, using default')
                roi_config = Roi(i*100, 600, 50,50)
            roi_widget.setConfig(roi_config)
            i = i + 1
            
    def load_roi_from_config(self, config, adr):
        roi_string = config['CAMERA'][adr]
        roi_dimensions = roi_string.split(',')
        if len(roi_dimensions) != 4:
            raise Exception('Invalid Roi config')
        return Roi(
            int(roi_dimensions[0]) - config.getint("CAMERA", "window_x", fallback=0),
            int(roi_dimensions[1]) - config.getint("CAMERA", "window_y", fallback=0),
            roi_dimensions[2],
            roi_dimensions[3],
        )
    
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
        self.ui.checkBox_subtractbackground.stateChanged.connect(
            self._on_subtract_background_changed
        )

        self.ui.button_autobrightness.clicked.connect(self.set_brightness_auto)
        self.ui.button_manualbrightness.clicked.connect(self.set_brightness_manual)

    def _on_subtract_background_changed(self, state: int) -> None:
        self._subtract_background_enabled = state == Qt.Checked

    def _image_for_analysis(self, img: numpy.ndarray) -> numpy.ndarray:
        if not self._subtract_background_enabled:
            return img
        background = self._background_img
        if background is None or background.shape != img.shape:
            return img
        diff = img.astype(numpy.int32) - background.astype(numpy.int32)
        return numpy.clip(
            diff,
            numpy.iinfo(numpy.int16).min,
            numpy.iinfo(numpy.int16).max,
        ).astype(numpy.int16)

    def _refresh_plot_enable_flags(self) -> None:
        any_time = any(w.is_time_plot_checked() for w in self.roi_widgets)
        any_profile = any(w.is_profile_plot_checked() for w in self.roi_widgets)
        with self._plot_flags_lock:
            self._any_time_plot_enabled = any_time
            self._any_profile_plot_enabled = any_profile

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
        self._load_detector_settings_from_camera()
    
    def calculate_frame_rates(self):
        camera_frame_rate = self.nbCameraImages / 5
        roi_frame_rate = self.roi_tracking_frames / 5
        if camera_frame_rate > 0:
            self._last_camera_frame_rate = camera_frame_rate
        _camera_log(f'Camera frame rate: {camera_frame_rate:.2f}')
        _camera_log(f'ROI tracking frame rate: {roi_frame_rate:.2f}')
        if self.dropped_frames or self.frame_writer.dropped:
            _camera_log(
                f'Dropped frames: process={self.dropped_frames}, '
                f'save={self.frame_writer.dropped}, '
                f'save queue={self.frame_writer.pending()}'
            )
        self._maybe_refresh_frames_saved_on_day_change()
        self._update_timing_labels()
        
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
            self._refresh_frames_saved_today()
            self._load_detector_settings_from_camera(use_default_framerate=True)
            self._set_detector_controls_enabled()
    

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
        self.interface.setparam_int32(294, config.getint("CAMERA", "window_w", fallback=160))
        self.interface.setparam_int32(295, config.getint("CAMERA", "window_h", fallback=150))
        self.interface.setparam_int32(292, config.getint("CAMERA", "window_x", fallback=0))
        self.interface.setparam_int32(293, config.getint("CAMERA", "window_y", fallback=0))
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
            self._last_camera_frame_rate = None
            self._set_detector_controls_enabled()
            self._update_timing_labels()

    def record_clicked(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()
            
    def start_recording(self):
        with self.recording_lock:
            if self.recording:
                return True
        if not self.connected:
            return False
        
        # Store current camera integration time
        self.integtime = self.interface.getparam_idx_int32(CAM_PARAM_INTEGRATION_TIME, 0)
        
        self.timestamps.clear()
        for roi_widget in self.roi_widgets:
            roi_widget.clear_max_values()

        self.ui.button_record.setText('Stop')
        self.ui.label_recording.setText('Recording')
        with self.recording_lock:
            self.recording = True
        self._recording_started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self._timing_refresh_timer.start(1000)
        self._set_detector_controls_enabled()
        self._update_timing_labels()
        return True
    
    def stop_recording(self):
        with self.recording_lock:
            if not self.recording:
                return
            self.recording = False
        
        self.ui.button_record.setText('Start')
        self.ui.label_recording.setText('Not recording')
        self._recording_started_at = None
        self._timing_refresh_timer.stop()
        self.frame_writer.drain(timeout=5.0)
        self._refresh_frames_saved_today()
        self._set_detector_controls_enabled()
        self._update_timing_labels()
    
    def take_background(self):
        frame = self.image.getImageItem().image
        if frame is not None:
            self._background_img = frame.copy()
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
            _camera_log(f"Timestamp reference: {new_timestamp_ref}")
            if img_timestamp_ref is None:
                img_timestamp_ref = new_timestamp_ref
            #Take the earliest time because there is always a delay, and the estimated timestamp can never be earlier thatn the actual timestamp
            img_timestamp_ref = min(img_timestamp_ref, new_timestamp_ref)

            self.time_reference_frames = self.time_reference_frames + 1

            if self.time_reference_frames == 100:
                _camera_log(f"Final timestamp reference: {img_timestamp_ref}")

            #Use the first 100 frames purely to establish time
            return
        
        if use_camera_time:
            timestamp = timedelta(milliseconds=timestamp_offset)
        else:
            timestamp = img_timestamp_ref + timedelta(milliseconds=timestamp_offset)
        #print(f"Delay: {recording_timestamp - timestamp}")

        self._publish_latest_frame_for_display(img)

        if(self.roi_queue.full()):
            self.dropped_frames += 1
            if self.dropped_frames == 1 or self.dropped_frames % 100 == 0:
                _camera_log(
                    f'Dropping frame ({self.dropped_frames} total), '
                    f'process queue full, save queue={self.frame_writer.pending()}'
                )
        else:
            self.roi_queue.put((img, timestamp))

    
    def initialize_image_display(self, img):
        self.image.setImage(img, autoRange=False)

        self.initialize_roi(img)

        self.imageInit = True
        with self._latest_frame_lock:
            self._latest_frame_for_display = numpy.asarray(img).copy()
        self._fit_detector_image()
        self._update_timing_labels()

        self._setup_roi_plot()
        self._layout_image_view()
        self._raise_overlay_widgets()

        #Now safe to start processing the frames
        threading.Thread(target=self.process_frame, daemon=True).start()



    def initialize_roi(self, img):
        for roi_widget in self.roi_widgets:
            if roi_widget.roi is not None:
                self.image.getView().removeItem(roi_widget.roi)
            roi = roi_widget.createRoi()
            self._bind_roi_image_profile_click(roi_widget)
            self.image.getView().addItem(roi)
        self.image.getView().update()

    def _bind_roi_image_profile_click(self, roi_widget) -> None:
        roi = roi_widget.roi

        def mouse_click_event(event):
            if event.button() == Qt.LeftButton:
                self._show_roi_profile(roi_widget)
            pg.ROI.mouseClickEvent(roi, event)

        roi.mouseClickEvent = mouse_click_event

    def _time_series_in_window(
        self, roi_widget
    ) -> tuple[numpy.ndarray, numpy.ndarray]:
        with self._roi_data_lock:
            timestamps = numpy.array(self.timestamps, dtype=numpy.float64)
            values = numpy.array(roi_widget.max_values, dtype=numpy.float64)
        if timestamps.size == 0:
            return timestamps, values

        # Deques are filled with appendleft (newest first); reverse for plotting.
        timestamps = timestamps[::-1]
        values = values[::-1]

        latest = timestamps[-1]
        cutoff = latest - ROI_TIME_PLOT_WINDOW_SECONDS
        mask = timestamps >= cutoff
        return timestamps[mask], values[mask]

    def _update_time_plot_x_range(self, latest_timestamp: float) -> None:
        plot_item = self.pw_roi.getPlotItem()
        x_max = latest_timestamp
        x_min = x_max - ROI_TIME_PLOT_WINDOW_SECONDS
        plot_item.setXRange(x_min, x_max, padding=0)

    def _remove_inactive_plot_curves(
        self, plot_item, curves_dict: dict, active_names: set[str]
    ) -> None:
        legend = plot_item.legend
        for name in list(curves_dict):
            if name not in active_names:
                curve = curves_dict.pop(name)
                plot_item.removeItem(curve)
                if legend is not None:
                    legend.removeItem(curve)

    def _clear_plot(self, plot_widget: pg.PlotWidget) -> None:
        plot_item = plot_widget.getPlotItem()
        plot_item.clear()
        legend = plot_item.legend
        if legend is not None:
            legend.clear()

    def _auto_range_plot(self, plot_widget: pg.PlotWidget) -> None:
        plot_item = plot_widget.getPlotItem()
        plot_item.enableAutoRange(axis="y", enable=True)
        plot_item.getViewBox().autoRange(padding=0.08)

    def _on_roi_plot_selection_changed(self, _state: int = 0) -> None:
        self._refresh_plot_enable_flags()
        self._time_plot_y_autorange = True
        self._profile_y_autorange = True
        self._update_profile_title()
        self._clear_plot(self.pw_roi)
        self._time_plot_curves.clear()
        self._clear_plot(self.pw_roi_profile)
        self._profile_plot_curves.clear()
        self._refresh_roi_time_plot()
        self._refresh_roi_profile()

    def _show_roi_profile(self, roi_widget) -> None:
        if not roi_widget.is_profile_plot_checked():
            roi_widget.profile_plot_checkbox.setChecked(True)
        else:
            self._profile_y_autorange = True
            self._update_profile_title()
            self._refresh_roi_profile()

    def _update_profile_title(self) -> None:
        selected = tuple(
            w.name for w in self.roi_widgets if w.is_profile_plot_checked()
        )
        if selected == self._profile_selection:
            return
        self._profile_selection = selected
        if not selected:
            self._profile_title.setText(
                "ROI profile — check 1D or click an ROI"
            )
        elif len(selected) == 1:
            self._profile_title.setText(f"{selected[0]} — 1D profile")
        elif len(selected) <= 3:
            self._profile_title.setText(
                f"ROI profiles — {', '.join(selected)}"
            )
        else:
            self._profile_title.setText(
                f"ROI profiles ({len(selected)} selected)"
            )

    def _refresh_roi_time_plot(self) -> None:
        if not hasattr(self, "pw_roi"):
            return
        plot_item = self.pw_roi.getPlotItem()
        active_names: set[str] = set()
        plotted = False
        window_latest = None
        for roi_widget in self.roi_widgets:
            if not roi_widget.is_time_plot_checked():
                continue
            active_names.add(roi_widget.name)
            timestamps, values = self._time_series_in_window(roi_widget)
            if timestamps.size == 0:
                continue
            window_latest = float(timestamps[-1])
            curve = self._time_plot_curves.get(roi_widget.name)
            if curve is None:
                curve = self.pw_roi.plot(
                    timestamps,
                    values,
                    name=roi_widget.name,
                    pen=roi_widget.color,
                )
                self._time_plot_curves[roi_widget.name] = curve
            else:
                curve.setData(timestamps, values)
            plotted = True
        self._remove_inactive_plot_curves(
            plot_item, self._time_plot_curves, active_names
        )
        if window_latest is not None:
            self._update_time_plot_x_range(window_latest)
        if plotted and self._time_plot_y_autorange:
            self._auto_range_plot(self.pw_roi)
            self._time_plot_y_autorange = False

    def _refresh_roi_profile(self) -> None:
        if not hasattr(self, "pw_roi_profile"):
            return
        profiles = self._last_roi_profiles
        if not profiles:
            plot_item = self.pw_roi_profile.getPlotItem()
            self._remove_inactive_plot_curves(
                plot_item, self._profile_plot_curves, set()
            )
            return

        plot_item = self.pw_roi_profile.getPlotItem()
        active_names: set[str] = set()
        plotted = False
        for index, roi_widget in enumerate(self.roi_widgets):
            if not roi_widget.is_profile_plot_checked():
                continue
            if index >= len(profiles):
                continue
            profile = profiles[index]
            if profile.size == 0:
                continue
            active_names.add(roi_widget.name)
            x = numpy.arange(profile.size, dtype=numpy.float64)
            curve = self._profile_plot_curves.get(roi_widget.name)
            if curve is None:
                curve = self.pw_roi_profile.plot(
                    x,
                    profile,
                    pen=self._profile_pen(roi_widget),
                    name=roi_widget.name,
                )
                self._profile_plot_curves[roi_widget.name] = curve
            else:
                curve.setData(x, profile)
            plotted = True

        self._remove_inactive_plot_curves(
            plot_item, self._profile_plot_curves, active_names
        )
        if plotted and self._profile_y_autorange:
            self._auto_range_plot(self.pw_roi_profile)
            self._profile_y_autorange = False
    
    def get_roi_from_config(self, roi_config:Roi, pen):
        return pg.RectROI([roi_config.x, roi_config.y], [roi_config.w, roi_config.h], pen = pen)
        
    def update_image(self, img):
        if not self.imageInit:
            self.set_window()
            self.initialize_image_display(img)
            self.set_brightness_auto()

    def _publish_latest_frame_for_display(self, img: numpy.ndarray) -> None:
        if not self.imageInit:
            return
        with self._latest_frame_lock:
            self._latest_frame_for_display = numpy.asarray(img).copy()
        now = time.monotonic()
        with self._display_emit_lock:
            elapsed = now - self._last_display_emit
            if elapsed >= IMAGE_DISPLAY_REFRESH_INTERVAL_MS / 1000.0:
                self._last_display_emit = now
                self.image_display_update.emit()
                
    def process_roi(self, img, timestamp, coadded_frame):
        analysis_img = self._image_for_analysis(img)
        calculator = self.run_roi_calculator(analysis_img)
        if not coadded_frame and self.recording:
            if record_rois:
                self.store_roi_to_db(timestamp, calculator)
            self.roi_tracking_frames += 1
        
        if coadded_frame or not self.is_coadd_enabled():
            self.update_gui_with_newroi(timestamp, calculator)
            
    def update_gui_with_newroi(self, timestamp, calculator):
        with self._roi_data_lock:
            self.timestamps.appendleft(datetime.timestamp(timestamp))
            for i in range(len(self.roi_widgets)):
                self.roi_widgets[i].add_max_value(calculator.results[i].max)

        calculator_results = calculator.results
        calculator_rois = calculator.rois
        with self._plot_flags_lock:
            any_time_plot = self._any_time_plot_enabled
            any_profile_plot = self._any_profile_plot_enabled
        plots_enabled = any_time_plot or any_profile_plot
        now = time.monotonic()
        with self._roi_emit_lock:
            elapsed_values = now - self._last_values_emit
            if elapsed_values >= ROI_VALUES_REFRESH_INTERVAL_MS / 1000.0:
                self._last_values_emit = now
                self._latest_brightness_results = calculator_results
                self.roi_values_update.emit()

            elapsed_plots = now - self._last_plots_emit
            if (
                plots_enabled
                and elapsed_plots >= ROI_PLOT_REFRESH_INTERVAL_MS / 1000.0
            ):
                self._last_plots_emit = now
                if any_profile_plot:
                    self._last_roi_profiles = tuple(
                        roi_profile_1d(region) for region in calculator_rois
                    )
                else:
                    self._last_roi_profiles = None
                self.roi_plots_update.emit()

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
        
    def on_image_display_update(self) -> None:
        if not self.imageInit:
            return
        with self._latest_frame_lock:
            frame = self._latest_frame_for_display
        if frame is None:
            return
        display_img = self._image_for_analysis(frame)
        self.image.getImageItem().setImage(display_img, autoLevels=False)

    def on_roi_values_update(self) -> None:
        results = self._latest_brightness_results
        if results is None:
            return
        for i in range(len(self.roi_widgets)):
            self.roi_widgets[i].setValues(results[i])

    def on_roi_plots_update(self) -> None:
        with self._plot_flags_lock:
            refresh_time = self._any_time_plot_enabled
            refresh_profile = self._any_profile_plot_enabled
        if refresh_time:
            self._refresh_roi_time_plot()
        if refresh_profile:
            self._refresh_roi_profile()

    def _count_frames_for_utc_day(self, utc_day: str) -> int:
        return count_frames_saved_for_utc_day(utc_day)

    def get_dashboard_status(self) -> dict[str, object]:
        utc_day = self._utc_day_key()
        with self._frames_count_lock:
            files_today = self._frames_saved_today
            if self._frames_saved_utc_day != utc_day:
                files_today = self._count_frames_for_utc_day(utc_day)
        with self.recording_lock:
            recording = self.recording

        frame_size = self._frame_size_text()

        return {
            "connected": self.connected,
            "recording": recording,
            "files_today": files_today,
            "utc_day": utc_day,
            "frame_size": frame_size,
        }

    def closeEvent(self, *args):
        self.running = False
        self.frame_rate_timer.stop()
        self._timing_refresh_timer.stop()

        if self.connected:
            with self.recording_lock:
                self.recording = False
            self.disconnect_camera()

        self.frame_writer.stop(timeout=2.0)
        self.interface.free_device()
        self.interface.free_dll()
        self.closing.emit()
        super().closeEvent(*args)

if __name__ == "__main__":
    from nottcontrol.app_icon import apply_app_icon, ensure_windows_app_identity
    from nottcontrol.ui_scale import configure_high_dpi, init_ui_scale

    configure_high_dpi()
    ensure_windows_app_identity()
    app = QApplication(sys.argv)
    init_ui_scale(app)
    apply_app_icon(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())