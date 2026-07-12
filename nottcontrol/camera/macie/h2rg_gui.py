from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlparse

import numpy
from PyQt5.QtCore import QEvent, QPointF, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PyQt5.uic import loadUi

from nottcontrol import config
from nottcontrol.camera.macie.fits_science import (
    load_science_image,
    save_science_fits,
    science_fits_path,
)

MACIE_CONFIG_FILE = config.get(
    "MACIE", "config_file", fallback="basic_warm_slow.cfg"
)
MACIE_ZMQ_ADDRESS = config.get(
    "MACIE", "zmq_address", fallback="tcp://localhost:65534"
)
MACIE_OFFLINE_MODE = config.getboolean("MACIE", "offline_mode", fallback=False)
MACIE_IMAGE_SCALE = config.getint("MACIE", "image_display_scale", fallback=2)
FITS_DIR_CHECK_TIMEOUT_S = config.getfloat(
    "MACIE", "fits_directory_check_timeout_s", fallback=1.0
)
FITS_LINUX_PATH_PREFIX = config.get(
    "MACIE", "fits_linux_path_prefix", fallback=""
).strip()
FITS_WINDOWS_UNC_ROOT = config.get(
    "MACIE", "fits_windows_unc_root", fallback=""
).strip()
MACIE_INTEGRATION_NGROUPS_MAX = config.getint(
    "MACIE", "integration_ngroups_max", fallback=2
)
MACIE_SAVE_SCIENCE_FITS = config.getboolean(
    "MACIE", "save_science_fits", fallback=True
)

PANEL_BUTTON_STYLE = """
    QPushButton {
        font: 10pt "Segoe UI";
        color: white;
        background: rgb(50, 129, 140);
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        min-height: 28px;
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

WINDOW_STYLE = """
    QMainWindow, QWidget#h2rg_root {
        background: rgb(245, 248, 249);
    }
"""

IMAGE_FRAME_STYLE = """
    QFrame#frame_camera {
        background: rgb(26, 26, 46);
        border: 1px solid rgb(50, 129, 140);
        border-radius: 6px;
    }
"""

CHECKBOX_STYLE = 'font: 9pt "Segoe UI"; color: rgb(50, 50, 50); spacing: 6px;'

_MACIE_UI = Path(__file__).resolve().parent / "ui" / "MacieControl.ui"
RIGHT_PANEL_WIDTH = 360
CURSOR_READOUT_HEIGHT = 22
CURSOR_READOUT_INTERVAL_MS = 50
H2RG_ARRAY_SIZE = 2048


@dataclass(frozen=True)
class WindowMode:
    label: str
    x_window: bool
    y_window: bool
    x1: int
    x2: int
    y1: int
    y2: int


def _window_region(x0: int, y0: int, size: int) -> tuple[int, int, int, int]:
    return x0, x0 + size - 1, y0, y0 + size - 1


def _centered_window(size: int, array_size: int = H2RG_ARRAY_SIZE) -> tuple[int, int, int, int]:
    origin = (array_size - size) // 2
    return _window_region(origin, origin, size)


def _build_window_modes(array_size: int = H2RG_ARRAY_SIZE) -> tuple[WindowMode, ...]:
    full_span = array_size - 1
    half = array_size // 2
    return (
        WindowMode("Full frame", False, False, 0, full_span, 0, full_span),
        WindowMode("Lower left 1024x1024", True, True, *_window_region(0, 0, 1024)),
        WindowMode("Lower right 1024x1024", True, True, *_window_region(half, 0, 1024)),
        WindowMode("Upper left 1024x1024", True, True, *_window_region(0, half, 1024)),
        WindowMode("Upper right 1024x1024", True, True, *_window_region(half, half, 1024)),
        WindowMode("Central 1024x1024", True, True, *_centered_window(1024, array_size)),
        WindowMode("Central 512x512", True, True, *_centered_window(512, array_size)),
    )


WINDOW_MODES = _build_window_modes()


def _normalize_scene_pos(pos) -> QPointF:
    """Accept QPointF or nested tuples from pyqtgraph signal/proxy variants."""
    while isinstance(pos, (tuple, list)) and len(pos) == 1:
        pos = pos[0]
    if isinstance(pos, (tuple, list)) and len(pos) >= 2:
        return QPointF(float(pos[0]), float(pos[1]))
    return pos


def _format_stat_value(value: float) -> str:
    """Format detector ADU statistics without scientific notation."""
    if not numpy.isfinite(value):
        return "—"
    rounded = float(numpy.round(value))
    if abs(rounded - value) < 1e-9:
        return f"{int(rounded)}"
    return f"{value:.2f}"


def window_mode_index(
    x_window: bool,
    y_window: bool,
    x1: int,
    x2: int,
    y1: int,
    y2: int,
) -> int:
    for index, mode in enumerate(WINDOW_MODES):
        if (mode.x_window, mode.y_window) != (x_window, y_window):
            continue
        if not mode.x_window and not mode.y_window:
            return index
        if (mode.x1, mode.x2, mode.y1, mode.y2) == (x1, x2, y1, y2):
            return index
    return -1


def macie_config_path(config_name: str) -> Path:
    base = Path(__file__).resolve().parent / "macie_exe" / "config_files"
    return base / config_name


def parse_macie_save_dir(config_path: Path) -> Path:
    save_dir: str | None = None
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("saveDir"):
            parts = stripped.split(maxsplit=1)
            if len(parts) == 2:
                save_dir = parts[1].strip()
            break
    if save_dir is None:
        return Path.home() / "test_data"
    return Path(os.path.expanduser(save_dir))


def resolve_fits_save_dir(config_path: Path) -> Path:
    configured = config.get("MACIE", "fits_directory", fallback="").strip()
    if configured:
        return Path(os.path.expanduser(configured))
    return parse_macie_save_dir(config_path)


def zmq_server_hostname(zmq_address: str) -> str | None:
    normalized = zmq_address if "://" in zmq_address else f"tcp://{zmq_address}"
    return urlparse(normalized).hostname


def map_server_fits_path(server_path: str, zmq_address: str = MACIE_ZMQ_ADDRESS) -> Path:
    normalized = server_path.replace("\\", "/")
    if FITS_LINUX_PATH_PREFIX and FITS_WINDOWS_UNC_ROOT:
        prefix = FITS_LINUX_PATH_PREFIX.replace("\\", "/").rstrip("/")
        if normalized.startswith(prefix):
            suffix = normalized[len(prefix) :].lstrip("/")
            unc_root = FITS_WINDOWS_UNC_ROOT.rstrip("\\/")
            if sys.platform == "win32":
                return Path(unc_root) / PureWindowsPath(suffix.replace("/", "\\"))
            return Path(unc_root) / Path(*PurePosixPath(suffix).parts)

    if sys.platform == "win32" and normalized.startswith("/"):
        host = zmq_server_hostname(zmq_address)
        if host:
            relative = normalized.lstrip("/")
            windows_relative = relative.replace("/", "\\")
            return Path(f"\\\\{host}\\{windows_relative}")

    return Path(server_path)


def load_fits_image(filepath: Path) -> numpy.ndarray:
    return load_science_image(filepath)


def load_fits_image_from_bytes(payload: bytes) -> numpy.ndarray:
    return load_science_image(payload)


def path_is_directory(path: Path, timeout_s: float = FITS_DIR_CHECK_TIMEOUT_S) -> bool:
    result: list[bool | None] = [None]

    def probe() -> None:
        try:
            result[0] = path.is_dir()
        except OSError:
            result[0] = False

    thread = threading.Thread(target=probe, daemon=True)
    thread.start()
    thread.join(timeout=timeout_s)
    if result[0] is None:
        return False
    return result[0]


def newest_fits_file(directory: Path, *, dir_ok: bool | None = None) -> Path | None:
    if dir_ok is False:
        return None
    if dir_ok is None:
        try:
            if not directory.is_dir():
                return None
        except OSError:
            return None
    candidates = [
        *directory.glob("*.fits"),
        *directory.glob("*.FITS"),
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


class H2rgMainWindow(QMainWindow):
    closing = pyqtSignal()
    frame_ready = pyqtSignal(object)
    operation_failed = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    controls_enabled = pyqtSignal(bool)
    readouts_updated = pyqtSignal(object)
    init_button_state = pyqtSignal(str)
    exposure_timing_updated = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("H2RG / MACIE")
        self.setMinimumSize(880, 650)
        self.ui = None
        self._init_runtime_state()

        self.frame_ready.connect(self._display_frame, Qt.QueuedConnection)
        self.operation_failed.connect(self._on_operation_failed, Qt.QueuedConnection)
        self.status_updated.connect(self._set_status, Qt.QueuedConnection)
        self.controls_enabled.connect(self._set_controls_enabled, Qt.QueuedConnection)
        self.readouts_updated.connect(self._apply_readouts, Qt.QueuedConnection)
        self.init_button_state.connect(self._apply_init_button_state, Qt.QueuedConnection)
        self.exposure_timing_updated.connect(
            self._apply_exposure_timing, Qt.QueuedConnection
        )

        loading = QLabel("Loading H2RG controls…", self)
        loading.setAlignment(Qt.AlignCenter)
        loading.setStyleSheet(
            'font: 13pt "Segoe UI"; color: rgb(100, 100, 100); background: rgb(245, 248, 249);'
        )
        self.setCentralWidget(loading)
        self.show()
        QApplication.processEvents()
        QTimer.singleShot(0, self._stage_load_ui)

    def _init_runtime_state(self) -> None:
        self._config_path = macie_config_path(MACIE_CONFIG_FILE)
        self._save_dir = resolve_fits_save_dir(self._config_path)
        self._fits_dir_ok: bool | None = None
        self._macie = None
        self._live_active = False
        self._background: numpy.ndarray | None = None
        self._current_frame: numpy.ndarray | None = None
        self._last_fits_mtime = 0.0
        self._last_fits_path: Path | None = None
        self._auto_levels_next = True
        self._operation_lock = threading.Lock()
        self._zmq_server = None
        self._last_tint_ms: float | None = None
        self._initialized = False
        self._last_zmq_fits_poll = 0.0
        self.image = None
        self._image_placeholder: QLabel | None = None
        self._cursor_readout: QLabel | None = None
        self._cursor_readout_pending = None
        self._cursor_readout_timer = QTimer()
        self._cursor_readout_timer.setSingleShot(True)
        self._cursor_readout_timer.timeout.connect(self._flush_cursor_readout)
        self._stat_mean: QLineEdit | None = None
        self._stat_min: QLineEdit | None = None
        self._stat_max: QLineEdit | None = None
        self._stat_std: QLineEdit | None = None

    def _stage_load_ui(self) -> None:
        QApplication.processEvents()
        self.ui = loadUi(str(_MACIE_UI))
        self.setCentralWidget(self.ui)
        QTimer.singleShot(0, self._stage_connect_ui)

    def _stage_connect_ui(self) -> None:
        QApplication.processEvents()
        self._connect_signals()
        self._set_status("Loading…")
        self._set_controls_enabled(False)
        self.ui.checkBox_substract_background.setEnabled(False)
        QTimer.singleShot(0, self._finish_setup)

    def _finish_setup(self) -> None:
        QApplication.processEvents()
        self._relayout_control_panels()
        self._rebuild_layout()
        QApplication.processEvents()
        self._apply_styles()
        self._setup_image_placeholder()
        self._create_cursor_readout_label()
        self.ui.frame_camera.installEventFilter(self)
        self._layout_image_frame()
        self._populate_comboboxes()
        self._set_status("Not connected")
        threading.Thread(target=self._background_startup, daemon=True).start()

    def _setup_image_placeholder(self) -> None:
        self._image_placeholder = QLabel("No image yet", self.ui.frame_camera)
        self._image_placeholder.setAlignment(Qt.AlignCenter)
        self._image_placeholder.setStyleSheet(
            'color: rgb(180, 180, 200); font: 11pt "Segoe UI";'
        )

    def _clear_frame_camera_layout(self) -> None:
        layout = self.ui.frame_camera.layout()
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self.ui.frame_camera)
        QWidget().setLayout(layout)

    def _create_cursor_readout_label(self) -> None:
        if self._cursor_readout is not None:
            return
        self._cursor_readout = QLabel("Pixel: —", self.ui.frame_camera)
        self._cursor_readout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._cursor_readout.setStyleSheet(
            'font: 9pt "Consolas", monospace;'
            " color: rgb(50, 50, 50);"
            " background-color: rgba(255, 255, 255, 215);"
            " padding-left: 6px;"
        )
        self._cursor_readout.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def _setup_image_statistics_panel(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Image statistics")
        group.setStyleSheet(PANEL_GROUP_STYLE)
        grid = QGridLayout(group)
        grid.setContentsMargins(8, 12, 8, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)

        field_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        stat_field_style = (
            PANEL_FIELD_STYLE + " QLineEdit { background: rgb(250, 252, 252); }"
        )

        def _add_row(row: int, text: str, field: QLineEdit) -> None:
            label = QLabel(text, group)
            label.setStyleSheet(PANEL_LABEL_STYLE)
            field.setReadOnly(True)
            field.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            field.setSizePolicy(field_policy)
            field.setStyleSheet(stat_field_style)
            grid.addWidget(label, row, 0, Qt.AlignLeft | Qt.AlignVCenter)
            grid.addWidget(field, row, 1, Qt.AlignRight | Qt.AlignVCenter)

        self._stat_mean = QLineEdit("—", group)
        self._stat_min = QLineEdit("—", group)
        self._stat_max = QLineEdit("—", group)
        self._stat_std = QLineEdit("—", group)
        _add_row(0, "Mean:", self._stat_mean)
        _add_row(1, "Min:", self._stat_min)
        _add_row(2, "Max:", self._stat_max)
        _add_row(3, "Std:", self._stat_std)
        parent_layout.addWidget(group)

    def _setup_cursor_readout(self) -> None:
        if self.image is None or self._cursor_readout is None:
            return
        scene = self.image.getView().scene()
        scene.sigMouseMoved.connect(self._update_cursor_readout)

    def _layout_image_frame(self) -> None:
        width = max(1, self.ui.frame_camera.width())
        height = max(1, self.ui.frame_camera.height())
        readout_h = CURSOR_READOUT_HEIGHT
        image_h = max(1, height - readout_h)

        if self.image is not None:
            self.image.setGeometry(4, 4, max(1, width - 8), max(1, image_h - 8))
        elif self._image_placeholder is not None:
            self._image_placeholder.setGeometry(4, 4, max(1, width - 8), max(1, image_h - 8))

        if self._cursor_readout is not None:
            self._cursor_readout.setGeometry(0, height - readout_h, width, readout_h)
            self._cursor_readout.raise_()

    def _update_cursor_readout(self, pos) -> None:
        self._cursor_readout_pending = pos
        if not self._cursor_readout_timer.isActive():
            self._cursor_readout_timer.start(CURSOR_READOUT_INTERVAL_MS)

    def _flush_cursor_readout(self) -> None:
        if self._cursor_readout is None:
            return
        pos = self._cursor_readout_pending
        if pos is None:
            return
        if self.image is None:
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
        self._cursor_readout.setText(f"Pixel: x={x}, y={y}  ADU={adu:.1f}")

    def _update_image_statistics(self, frame: numpy.ndarray) -> None:
        if self._stat_mean is None:
            return
        data = numpy.asarray(frame, dtype=numpy.float64)
        if data.size == 0:
            for field in (
                self._stat_mean,
                self._stat_min,
                self._stat_max,
                self._stat_std,
            ):
                field.setText("—")
            return
        self._stat_mean.setText(_format_stat_value(float(numpy.mean(data))))
        self._stat_min.setText(_format_stat_value(float(numpy.min(data))))
        self._stat_max.setText(_format_stat_value(float(numpy.max(data))))
        self._stat_std.setText(_format_stat_value(float(numpy.std(data))))

    def eventFilter(self, obj, event) -> bool:
        if (
            self.ui is not None
            and obj is self.ui.frame_camera
            and event.type() == QEvent.Resize
        ):
            self._layout_image_frame()
        return super().eventFilter(obj, event)

    def _ensure_image_view(self) -> None:
        if self.image is not None:
            return

        import pyqtgraph as pg

        pg.setConfigOptions(imageAxisOrder="row-major")
        pg.setConfigOption("background", "#1a1a2e")
        pg.setConfigOption("foreground", "w")

        self._clear_frame_camera_layout()

        if self._image_placeholder is not None:
            self._image_placeholder.hide()
            self._image_placeholder.deleteLater()
            self._image_placeholder = None

        self.image = pg.ImageView(self.ui.frame_camera)
        self.image.ui.histogram.hide()
        self.image.ui.roiBtn.hide()
        self.image.ui.menuBtn.hide()
        self.image.show()
        self.image.getView().setMouseEnabled(x=True, y=True)
        self.image.getView().setAspectLocked(True)
        self._setup_cursor_readout()
        self._layout_image_frame()

        if self._current_frame is not None:
            self._display_frame(self._current_frame)

    def _background_startup(self) -> None:
        from nottcontrol.camera.macie.zmq_server_manager import MacieZmqServerProcess

        if self._zmq_server is None:
            self._zmq_server = MacieZmqServerProcess(MACIE_ZMQ_ADDRESS)
        self._fits_dir_ok = path_is_directory(self._save_dir)
        if not self._fits_dir_ok and sys.platform == "win32":
            self.status_updated.emit(
                "Not connected — FITS preview uses ZMQ fetch or SMB path mapping"
            )

        try:
            self._zmq_server.ensure_running()
            if self._zmq_server.started_by_gui:
                self.status_updated.emit("ZMQ server started")
            elif self._fits_dir_ok is not False:
                self.status_updated.emit(
                    f"Connected to ZMQ server at {MACIE_ZMQ_ADDRESS}"
                )
        except Exception as exc:
            message = str(exc)
            if self._fits_dir_ok is False and sys.platform == "win32":
                message = (
                    f"{message} — also set [MACIE] fits_directory for FITS preview"
                )
            self.status_updated.emit(message)

    def _relayout_control_panels(self) -> None:
        self._layout_conf_panel()
        self._layout_acquisition_panel()
        self._layout_visualisation_panel()

    def _layout_conf_panel(self) -> None:
        box = self.ui.groupBox_conf
        outer = QHBoxLayout(box)
        outer.setContentsMargins(8, 12, 8, 8)
        outer.setSpacing(8)

        buttons = QVBoxLayout()
        buttons.setSpacing(6)
        for name in ("button_init", "button_powerOn", "button_powerOff"):
            buttons.addWidget(getattr(self.ui, name))
        outer.addLayout(buttons)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        form.addWidget(self.ui.label, 0, 0)
        form.addWidget(self.ui.comboBox_detector_mode, 0, 1)
        form.addWidget(self.ui.label_2, 1, 0)
        form.addWidget(self.ui.comboBox_window_mode, 1, 1)
        form.addWidget(self.ui.label_3, 2, 0)
        form.addWidget(self.ui.lineEdit_status, 2, 1)
        form.setColumnStretch(1, 1)
        outer.addLayout(form, stretch=1)

    def _layout_acquisition_panel(self) -> None:
        box = self.ui.groupBox_acquisition
        outer = QVBoxLayout(box)
        outer.setContentsMargins(8, 12, 8, 8)
        outer.setSpacing(8)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        editable_rows = (
            ("label_5", "lineEdit_integration_time"),
            ("label_6", "lineEdit_nb_coadd"),
            ("label_7", "lineEdit_nb_frames"),
        )
        self.ui.label_5.setText("Integration time (ms):")
        self.ui.label_4.setText("Total integration time (ms):")
        for row, (label_name, field_name) in enumerate(editable_rows):
            form.addWidget(getattr(self.ui, label_name), row, 0)
            form.addWidget(getattr(self.ui, field_name), row, 1)

        self._label_photon_time = QLabel("Photon time (s):")
        self._lineEdit_photon_time = QLineEdit("—")
        self._lineEdit_photon_time.setReadOnly(True)
        self._label_execution_time = QLabel("Execution time (s):")
        self._lineEdit_execution_time = QLineEdit("—")
        self._lineEdit_execution_time.setReadOnly(True)
        self._label_efficiency = QLabel("Efficiency (%):")
        self._lineEdit_efficiency = QLineEdit("—")
        self._lineEdit_efficiency.setReadOnly(True)
        timing_row = len(editable_rows)
        for offset, (label, field) in enumerate(
            (
                (self._label_photon_time, self._lineEdit_photon_time),
                (self._label_execution_time, self._lineEdit_execution_time),
                (self._label_efficiency, self._lineEdit_efficiency),
            )
        ):
            label.setStyleSheet(PANEL_LABEL_STYLE)
            field.setStyleSheet(
                PANEL_FIELD_STYLE + " QLineEdit { background: rgb(250, 252, 252); }"
            )
            form.addWidget(label, timing_row + offset, 0)
            form.addWidget(field, timing_row + offset, 1)

        footer_row = timing_row + 3
        for offset, (label_name, field_name) in enumerate(
            (
                ("label_4", "lineEdit_integration_time_total"),
                ("label_8", "lineEdit_frame_nb"),
            )
        ):
            form.addWidget(getattr(self.ui, label_name), footer_row + offset, 0)
            form.addWidget(getattr(self.ui, field_name), footer_row + offset, 1)
        form.setColumnStretch(1, 1)
        outer.addLayout(form)

        self.ui.button_take_background.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        outer.addWidget(self.ui.button_take_background)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        for name in ("button_live", "button_acquire", "button_halt"):
            button = getattr(self.ui, name)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            actions.addWidget(button)
        outer.addLayout(actions)

    def _layout_visualisation_panel(self) -> None:
        box = self.ui.groupBox_visualisation
        outer = QHBoxLayout(box)
        outer.setContentsMargins(8, 12, 8, 8)
        outer.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(4)
        for name in (
            "checkBox_substract_background",
            "checkBox_avg",
            "checkBox_max",
            "checkBox_min",
        ):
            left.addWidget(getattr(self.ui, name))
        left.addStretch()
        outer.addLayout(left, stretch=1)

        middle = QVBoxLayout()
        middle.setSpacing(4)
        for index in range(1, 6):
            middle.addWidget(getattr(self.ui, f"checkBox_ROI{index}"))
        middle.addStretch()
        outer.addLayout(middle, stretch=1)

        right = QVBoxLayout()
        right.setSpacing(4)
        for index in range(6, 11):
            right.addWidget(getattr(self.ui, f"checkBox_ROI{index}"))
        right.addStretch()
        outer.addLayout(right, stretch=1)

    def _rebuild_layout(self) -> None:
        form = self.ui
        form.setObjectName("h2rg_root")

        outer = QHBoxLayout(form)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(16)

        self.ui.frame_camera.setMinimumWidth(480)
        image_column = QWidget()
        image_column_layout = QVBoxLayout(image_column)
        image_column_layout.setContentsMargins(0, 0, 0, 0)
        image_column_layout.setSpacing(8)
        image_column_layout.addWidget(self.ui.frame_camera, stretch=1)
        self._setup_image_statistics_panel(image_column_layout)
        outer.addWidget(image_column, stretch=1)

        right_host = QWidget()
        right_host.setFixedWidth(RIGHT_PANEL_WIDTH)
        right = QVBoxLayout(right_host)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(12)

        panel_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        for box in (
            self.ui.groupBox_conf,
            self.ui.groupBox_acquisition,
            self.ui.groupBox_visualisation,
        ):
            box.setSizePolicy(panel_policy)
            right.addWidget(box)

        right.addStretch()
        outer.addWidget(right_host, stretch=0)

    def _apply_styles(self) -> None:
        self.setStyleSheet(WINDOW_STYLE)
        self.ui.frame_camera.setStyleSheet(IMAGE_FRAME_STYLE)

        for box in (
            self.ui.groupBox_conf,
            self.ui.groupBox_acquisition,
            self.ui.groupBox_visualisation,
        ):
            box.setStyleSheet(PANEL_GROUP_STYLE)

        for name in (
            "button_init",
            "button_powerOn",
            "button_powerOff",
            "button_take_background",
            "button_live",
            "button_acquire",
            "button_halt",
        ):
            getattr(self.ui, name).setStyleSheet(PANEL_BUTTON_STYLE)

        for name in (
            "label",
            "label_2",
            "label_3",
            "label_4",
            "label_5",
            "label_6",
            "label_7",
            "label_8",
        ):
            getattr(self.ui, name).setStyleSheet(PANEL_LABEL_STYLE)

        for name in (
            "lineEdit_status",
            "lineEdit_integration_time",
            "lineEdit_nb_coadd",
            "lineEdit_nb_frames",
            "lineEdit_integration_time_total",
            "lineEdit_frame_nb",
            "comboBox_detector_mode",
            "comboBox_window_mode",
        ):
            getattr(self.ui, name).setStyleSheet(PANEL_FIELD_STYLE)

        for name in (
            "checkBox_substract_background",
            "checkBox_avg",
            "checkBox_max",
            "checkBox_min",
        ):
            getattr(self.ui, name).setStyleSheet(CHECKBOX_STYLE)

        for index in range(1, 11):
            checkbox = getattr(self.ui, f"checkBox_ROI{index}", None)
            if checkbox is not None:
                checkbox.setStyleSheet(CHECKBOX_STYLE)

        self.ui.lineEdit_status.setStyleSheet(
            PANEL_FIELD_STYLE + " QLineEdit { background: rgb(250, 252, 252); }"
        )

    def _populate_comboboxes(self) -> None:
        self.ui.comboBox_detector_mode.clear()
        self.ui.comboBox_detector_mode.addItems(["Slow", "Fast"])
        self.ui.comboBox_window_mode.clear()
        self.ui.comboBox_window_mode.addItems([mode.label for mode in WINDOW_MODES])
        self.ui.comboBox_window_mode.setMinimumWidth(200)

    def _connect_signals(self) -> None:
        self.ui.button_init.clicked.connect(self.init_camera)
        self.ui.button_powerOn.clicked.connect(self.power_on)
        self.ui.button_powerOff.clicked.connect(self.power_off)
        self.ui.button_take_background.clicked.connect(self.take_background)
        self.ui.button_live.clicked.connect(self.live_clicked)
        self.ui.button_acquire.clicked.connect(self.acquire)
        self.ui.button_halt.clicked.connect(self.halt)
        self.ui.checkBox_substract_background.toggled.connect(self._refresh_display)

        for widget in (
            self.ui.lineEdit_integration_time,
            self.ui.lineEdit_nb_coadd,
            self.ui.lineEdit_nb_frames,
        ):
            widget.editingFinished.connect(self._on_exposure_fields_changed)

        self.ui.comboBox_window_mode.currentIndexChanged.connect(
            self._on_window_mode_changed
        )

    def _on_window_mode_changed(self, index: int) -> None:
        if not self._initialized:
            return
        self._schedule_window_mode_apply(index)

    def _schedule_window_mode_apply(self, index: int) -> None:
        if index < 0 or index >= len(WINDOW_MODES):
            return

        def operation() -> None:
            macie = self._ensure_macie()
            self._apply_window_mode_to_macie(macie, index)

        self._run_macie_operation("Window mode", operation)

    def _apply_window_mode_to_macie(self, macie, index: int) -> None:
        mode = WINDOW_MODES[index]
        macie.frame_settings(
            mode.x_window,
            mode.y_window,
            mode.x1,
            mode.x2,
            mode.y1,
            mode.y2,
        )
        if mode.x_window or mode.y_window:
            status = (
                f"{mode.label} — x=[{mode.x1},{mode.x2}] y=[{mode.y1},{mode.y2}]"
            )
        else:
            status = mode.label
        self.status_updated.emit(status)
        self._refresh_exposure_timing(macie)

    def _on_exposure_fields_changed(self) -> None:
        self._update_total_integration_label()
        self._schedule_exposure_timing_preview()

    def _set_status(self, message: str) -> None:
        if self.ui is None:
            return
        self.ui.lineEdit_status.setText(message)

    def _set_controls_enabled(self, enabled: bool) -> None:
        if self.ui is None:
            return
        for name in (
            "button_powerOn",
            "button_powerOff",
            "button_take_background",
            "button_live",
            "button_acquire",
            "button_halt",
        ):
            getattr(self.ui, name).setEnabled(enabled)

    def _apply_init_button_state(self, state: str) -> None:
        if self.ui is None:
            return
        button = self.ui.button_init
        if state == "busy":
            button.setEnabled(False)
            button.setText("Initializing…")
            return
        if state == "done":
            self._initialized = True
            button.setEnabled(True)
            button.setText("Re-init")
            return
        self._initialized = False
        button.setEnabled(True)
        button.setText("Init")

    def _apply_exposure_timing(self, timing: dict[str, float]) -> None:
        if self.ui is None:
            return
        self._lineEdit_photon_time.setText(f"{timing['inttime_s']:.4g}")
        self._lineEdit_execution_time.setText(f"{timing['execution_s']:.4g}")
        self._lineEdit_efficiency.setText(f"{timing['efficiency'] * 100:.1f}")

    def _refresh_exposure_timing(self, macie) -> None:
        try:
            timing = macie.read_exposure_timing()
        except Exception:
            return
        self.exposure_timing_updated.emit(timing)

    def _schedule_exposure_timing_preview(self) -> None:
        if not self._initialized or self._macie is None:
            return

        def operation() -> None:
            self._apply_exposure_settings(self._macie)
            self._refresh_exposure_timing(self._macie)

        self._run_macie_operation("Update timing", operation)

    def _on_operation_failed(self, message: str) -> None:
        self._set_status(message)
        QMessageBox.warning(self, "H2RG", message)

    def _ensure_macie(self):
        from nottcontrol.camera.macie.macie_interface import MacieInterface

        if self._macie is None:
            self._macie = MacieInterface(
                offline_mode=MACIE_OFFLINE_MODE,
                config_file=MACIE_CONFIG_FILE,
                zmq_address=MACIE_ZMQ_ADDRESS,
            )
        return self._macie

    def _run_macie_operation(self, label: str, operation) -> None:
        def worker() -> None:
            try:
                with self._operation_lock:
                    operation()
            except Exception as exc:
                self.operation_failed.emit(f"{label} failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def init_camera(self) -> None:
        self.init_button_state.emit("busy")
        self.status_updated.emit("Initializing…")
        window_index = self.ui.comboBox_window_mode.currentIndex()

        def operation() -> None:
            macie = self._ensure_macie()
            macie.init_camera()
            if 0 <= window_index < len(WINDOW_MODES):
                self._apply_window_mode_to_macie(macie, window_index)
            self._sync_save_dir_from_server(macie)
            self._refresh_readouts(macie)
            self._refresh_exposure_timing(macie)
            self.status_updated.emit("Initialized")
            self.controls_enabled.emit(True)
            self.init_button_state.emit("done")

        def worker() -> None:
            try:
                with self._operation_lock:
                    operation()
            except Exception as exc:
                self.init_button_state.emit("idle")
                self.operation_failed.emit(f"Init failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def power_on(self) -> None:
        self._run_macie_operation("Power on", lambda: self._ensure_macie().power_on())

    def power_off(self) -> None:
        self._run_macie_operation("Power off", lambda: self._ensure_macie().power_off())

    def _apply_exposure_settings(self, macie) -> None:
        try:
            tint_ms = float(self.ui.lineEdit_integration_time.text().strip())
            ncoadds = int(self.ui.lineEdit_nb_coadd.text().strip() or "1")
            nseq = int(self.ui.lineEdit_nb_frames.text().strip() or "1")
        except ValueError as exc:
            raise ValueError(f"Invalid exposure field: {exc}") from exc

        if tint_ms <= 0:
            raise ValueError("Integration time must be greater than zero")

        tint_s = tint_ms / 1000.0
        actual_ms, ngroups, ndrops, nreads = macie.set_integration_time(
            tint_s,
            ngmax=MACIE_INTEGRATION_NGROUPS_MAX,
            ncoadds=ncoadds,
            nseq=nseq,
            save=True,
        )
        self._last_tint_ms = actual_ms
        self._update_total_integration_label(actual_tint_ms=actual_ms)
        self._refresh_exposure_timing(macie)
        self.status_updated.emit(
            f"Exposure: {actual_ms:.3g} ms "
            f"(groups={ngroups}, drops={ndrops}, reads={nreads})"
        )

    def acquire(self) -> None:
        def operation() -> None:
            macie = self._ensure_macie()
            self._apply_exposure_settings(macie)
            self._fits_dir_ok = None
            before_mtime = self._latest_fits_mtime()
            macie.acquire()
            frame, path = self._wait_for_new_frame(before_mtime, macie)
            if frame is not None:
                science_path = self._save_science_fits(frame, path)
                self._last_fits_path = science_path or path
                self._auto_levels_next = True
                self.frame_ready.emit(frame)
                if science_path is not None:
                    self.status_updated.emit(
                        f"Acquire complete — science FITS: {science_path.name}"
                    )
                else:
                    self.status_updated.emit("Acquire complete")
            else:
                self.status_updated.emit(self._missing_fits_status())

        self._run_macie_operation("Acquire", operation)

    def _science_output_path(self, ramp_path: Path) -> Path:
        if ramp_path.is_absolute():
            return science_fits_path(ramp_path)
        return science_fits_path(self._save_dir / ramp_path.name)

    def _save_science_fits(
        self, frame: numpy.ndarray, ramp_path: Path | None
    ) -> Path | None:
        if not MACIE_SAVE_SCIENCE_FITS or ramp_path is None:
            return None
        try:
            output_path = self._science_output_path(ramp_path)
            save_science_fits(
                output_path,
                frame,
                tint_ms=self._last_tint_ms,
            )
            return output_path
        except OSError as exc:
            print(f"H2RG failed to save science FITS: {exc}")
            return None

    def _sync_save_dir_from_server(self, macie) -> None:
        try:
            server_dir = macie.get_save_dir()
        except Exception:
            return
        if not server_dir:
            return
        mapped = map_server_fits_path(server_dir.rstrip("/\\"))
        if mapped:
            self._save_dir = mapped

    def _local_fits_accessible(self, *, allow_probe: bool = False) -> bool:
        if self._fits_dir_ok is False and not allow_probe:
            return False
        try:
            accessible = self._save_dir.is_dir()
        except OSError:
            accessible = False
        self._fits_dir_ok = accessible
        return accessible

    def _try_load_path_if_new(
        self, path: Path | None, before_mtime: float
    ) -> tuple[numpy.ndarray, Path] | None:
        if path is None:
            return None
        try:
            if not path.is_file():
                return None
            mtime = path.stat().st_mtime
        except OSError:
            return None
        if mtime <= before_mtime:
            return None
        return self._load_fits_from_path(path), path

    def _resolve_server_fits_path(self, macie) -> Path | None:
        try:
            server_path = macie.get_newest_fits_path()
        except Exception:
            return None
        if not server_path:
            return None
        return map_server_fits_path(server_path)

    def _fetch_fits_from_server(self, macie) -> tuple[numpy.ndarray, Path] | None:
        try:
            fetched = macie.fetch_newest_fits()
        except Exception as exc:
            print(f"H2RG FITS fetch over ZMQ failed: {exc}")
            return None
        if fetched is None:
            return None
        filename, payload = fetched
        path = Path(filename)
        frame = load_fits_image_from_bytes(payload)
        self._last_fits_path = path
        return frame, path

    def _missing_fits_status(self) -> str:
        if sys.platform == "win32":
            return (
                "Acquire complete — no FITS preview (set fits_directory or "
                "fits_linux_path_prefix/fits_windows_unc_root, or update zmq_server)"
            )
        if self._fits_dir_ok is False:
            return f"Acquire complete — FITS directory not found: {self._save_dir}"
        return f"Acquire complete — no new FITS in {self._save_dir}"

    def _newest_fits_file(self, *, allow_probe: bool = False) -> Path | None:
        dir_ok = None if allow_probe else self._fits_dir_ok
        return newest_fits_file(self._save_dir, dir_ok=dir_ok)

    def live_clicked(self) -> None:
        if self._macie is None:
            self._on_operation_failed("Initialize the detector first")
            return
        if self._live_active:
            self._macie.stop_continuous_acquisition()
            self._live_active = False
            self.ui.button_live.setText("Live")
            self._set_status("Live stopped")
            return

        self._live_active = True
        self.ui.button_live.setText("Stop live")
        self._set_status("Live acquiring…")
        self._macie.start_continuous_acquisition()

        def poll_frames() -> None:
            import time

            while self._live_active and self._macie is not None:
                loaded = self._load_latest_frame(force=True, macie=self._macie)
                if loaded is not None:
                    frame, _path = loaded
                    self.frame_ready.emit(frame)
                time.sleep(0.5)

        threading.Thread(target=poll_frames, daemon=True).start()

    def halt(self) -> None:
        if self._live_active and self._macie is not None:
            self._macie.stop_continuous_acquisition()
            self._live_active = False
            self.ui.button_live.setText("Live")

        if self._macie is not None:
            self._run_macie_operation("Halt", self._macie.halt_acquisition)
        self._set_status("Halted")

    def take_background(self) -> None:
        if self._current_frame is None:
            loaded = self._load_latest_frame()
            if loaded is None:
                self._on_operation_failed("No FITS frame available for background")
                return
            frame, _path = loaded
        else:
            frame = self._current_frame
        self._background = frame.copy()
        self.ui.checkBox_substract_background.setEnabled(True)
        self._set_status("Background stored")

    def _refresh_readouts(self, macie) -> None:
        from nottcontrol.camera.macie.macie_interface import DetectorMode

        mode = macie.get_detector_mode()
        x_window, y_window, x1, x2, y1, y2 = macie.read_frame_settings()
        x1_i, x2_i, y1_i, y2_i = int(x1), int(x2), int(y1), int(y2)
        (
            _save,
            ncoadds,
            nseq,
            _ngroups,
            nreads,
            _ndrops,
            _nresets,
        ) = macie.read_exposure_settings()
        try:
            tint_s = macie.read_integration_time_s()
        except Exception:
            tint_s = None
        self.readouts_updated.emit(
            {
                "mode_index": 0 if mode == DetectorMode.SLOW else 1,
                "window_index": window_mode_index(
                    x_window, y_window, x1_i, x2_i, y1_i, y2_i
                ),
                "windowed": x_window or y_window,
                "window_status": f"Window x=[{x1_i},{x2_i}] y=[{y1_i},{y2_i}]",
                "ncoadds": str(ncoadds),
                "nseq": str(nseq),
                "nreads": str(nreads) if nreads else "",
                "tint_s": tint_s,
            }
        )

    def _apply_readouts(self, data: dict) -> None:
        self.ui.comboBox_detector_mode.setCurrentIndex(data["mode_index"])
        window_index = data.get("window_index", -1)
        if window_index >= 0:
            combo = self.ui.comboBox_window_mode
            combo.blockSignals(True)
            combo.setCurrentIndex(window_index)
            combo.blockSignals(False)
        elif data["windowed"]:
            self._set_status(data["window_status"])
        self.ui.lineEdit_nb_coadd.setText(data["ncoadds"])
        self.ui.lineEdit_nb_frames.setText(data["nseq"])
        if data.get("tint_s") is not None:
            self.ui.lineEdit_integration_time.setText(f"{data['tint_s'] * 1000:.6g}")
        elif data["nreads"]:
            self.ui.lineEdit_integration_time.setText(data["nreads"])
        self._update_total_integration_label()

    def _update_total_integration_label(self, actual_tint_ms: float | None = None) -> None:
        try:
            per_frame = actual_tint_ms
            if per_frame is None:
                per_frame = float(self.ui.lineEdit_integration_time.text() or 0)
            coadds = int(self.ui.lineEdit_nb_coadd.text() or 1)
            frames = int(self.ui.lineEdit_nb_frames.text() or 1)
            total = per_frame * coadds * frames
            self.ui.lineEdit_integration_time_total.setText(f"{total:g}")
        except ValueError:
            self.ui.lineEdit_integration_time_total.setText("—")

    def _latest_fits_mtime(self) -> float:
        path = self._newest_fits_file(allow_probe=True)
        if path is None:
            return 0.0
        return path.stat().st_mtime

    def _wait_for_new_frame(
        self,
        before_mtime: float,
        macie,
        timeout_s: float = 30.0,
    ) -> tuple[numpy.ndarray | None, Path | None]:
        import time

        if not self._local_fits_accessible(allow_probe=True):
            for delay in (0.0, 0.5, 1.0, 2.0):
                if delay:
                    time.sleep(delay)
                fetched = self._fetch_fits_from_server(macie)
                if fetched is not None:
                    return fetched
            return None, None

        deadline = time.monotonic() + timeout_s
        server_path: Path | None = None
        server_path_checked_at = 0.0

        while time.monotonic() < deadline:
            loaded = self._try_load_path_if_new(
                self._newest_fits_file(allow_probe=True), before_mtime
            )
            if loaded is not None:
                return loaded

            now = time.monotonic()
            if now - server_path_checked_at >= 2.0:
                server_path_checked_at = now
                server_path = self._resolve_server_fits_path(macie)
            loaded = self._try_load_path_if_new(server_path, before_mtime)
            if loaded is not None:
                return loaded
            time.sleep(0.2)

        fetched = self._fetch_fits_from_server(macie)
        if fetched is not None:
            return fetched
        return None, None

    def _load_fits_from_path(self, path: Path) -> numpy.ndarray:
        self._last_fits_path = path
        self._last_fits_mtime = path.stat().st_mtime
        self._fits_dir_ok = True
        return load_fits_image(path)

    def _load_latest_frame(
        self, force: bool = False, macie=None
    ) -> tuple[numpy.ndarray, Path] | None:
        if not self._local_fits_accessible(allow_probe=True):
            if macie is None:
                return None
            import time

            now = time.monotonic()
            if not force and (now - self._last_zmq_fits_poll) < 2.0:
                return None
            self._last_zmq_fits_poll = now
            return self._fetch_fits_from_server(macie)

        path = self._newest_fits_file(allow_probe=True)
        if path is None and macie is not None:
            path = self._resolve_server_fits_path(macie)
        if path is None:
            if force and macie is not None:
                return self._fetch_fits_from_server(macie)
            return None
        try:
            mtime = path.stat().st_mtime
        except OSError:
            if macie is not None:
                return self._fetch_fits_from_server(macie)
            return None
        if not force and mtime == self._last_fits_mtime:
            return None
        try:
            return self._load_fits_from_path(path), path
        except OSError:
            if macie is not None:
                return self._fetch_fits_from_server(macie)
            return None

    def _refresh_display(self) -> None:
        if self._current_frame is not None:
            self._display_frame(self._current_frame)

    def _display_frame(self, frame: numpy.ndarray) -> None:
        self._ensure_image_view()
        if self.image is None:
            return
        self._current_frame = frame
        display = frame
        if (
            self.ui.checkBox_substract_background.isChecked()
            and self._background is not None
            and self._background.shape == frame.shape
        ):
            display = frame - self._background

        auto_levels = self._auto_levels_next
        self.image.setImage(display, autoLevels=auto_levels)
        if auto_levels:
            self._auto_levels_next = False

        self._update_image_statistics(display)
        self._layout_image_frame()

        if self._last_fits_path is not None:
            self.ui.lineEdit_frame_nb.setText(self._last_fits_path.name)

    def get_dashboard_status(self) -> dict[str, object]:
        powered = None
        if self._macie is not None:
            try:
                powered = self._macie.get_power()
            except Exception:
                powered = None
        return {
            "connected": self._macie is not None,
            "live": self._live_active,
            "powered": powered,
            "save_dir": str(self._save_dir),
        }

    def closeEvent(self, event) -> None:
        if self._live_active and self._macie is not None:
            self._macie.stop_continuous_acquisition()
            self._live_active = False

        if self._macie is not None:
            if self._operation_lock.acquire(timeout=5.0):
                self._operation_lock.release()
            try:
                self._macie.close()
            except Exception:
                pass
            self._macie = None
        if self._zmq_server is not None:
            self._zmq_server.stop()
        self.closing.emit()
        super().closeEvent(event)
