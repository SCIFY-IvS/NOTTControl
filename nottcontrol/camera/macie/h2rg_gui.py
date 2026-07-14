from __future__ import annotations

import os
import subprocess
import sys
import threading
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlparse

import numpy
from PyQt5.QtCore import QEvent, QPointF, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt5.uic import loadUi

from nottcontrol import config
from nottcontrol.app_icon import load_app_icon, make_nott_logo_title_header
from nottcontrol.camera.macie.fits_science import (
    load_fits_data,
    ramp_sample_axis,
    save_science_fits,
    science_fits_path,
    science_image_from_cube,
)
from nottcontrol.camera.macie.ramp_plan import RAMP_MODE_ITEMS, RAMP_MODES, fits_wait_timeout_s

MACIE_CONFIG_FILE = config.get(
    "MACIE", "config_file", fallback="teledyne_cold_slow.cfg"
)
MACIE_CONFIG_FILE_SLOW = config.get(
    "MACIE", "config_file_slow", fallback="teledyne_cold_slow.cfg"
)
MACIE_CONFIG_FILE_FAST = config.get(
    "MACIE", "config_file_fast", fallback="basic_fast_H2RG_cold.cfg"
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
MACIE_FOWLER_PAIRS_DEFAULT = config.getint(
    "MACIE", "fowler_pairs_default", fallback=2
)
MACIE_SAVE_SCIENCE_FITS = config.getboolean(
    "MACIE", "save_science_fits", fallback=True
)
MACIE_DS9_EXECUTABLE = config.get("MACIE", "ds9_executable", fallback="ds9").strip()
MACIE_FITS_WAIT_MARGIN_S = config.getfloat(
    "MACIE", "fits_wait_margin_s", fallback=30.0
)

from nottcontrol.theme import (
    CHECKBOX_STYLE,
    H2RG_WINDOW_STYLE,
    IMAGE_FRAME_STYLE,
    PANEL_BUTTON_STYLE,
    PANEL_FIELD_STYLE,
    PANEL_GROUP_STYLE,
    PANEL_LABEL_STYLE,
)

_MACIE_UI = Path(__file__).resolve().parent / "ui" / "MacieControl.ui"
RIGHT_PANEL_WIDTH = 360
IMAGE_STATS_MAX_WIDTH = 200
CURSOR_READOUT_HEIGHT = 28
CURSOR_READOUT_INTERVAL_MS = 50
H2RG_ARRAY_SIZE = 2048
H2RG_NUM_CHANNELS = 32


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


def _channel_width(array_size: int = H2RG_ARRAY_SIZE) -> int:
    return array_size // H2RG_NUM_CHANNELS


def _channel_window(
    channel: int, *, array_size: int = H2RG_ARRAY_SIZE
) -> tuple[int, int, int, int]:
    """Return x1, x2, y1, y2 for a 1-based H2RG readout channel (full height)."""
    width = _channel_width(array_size)
    if not 1 <= channel <= H2RG_NUM_CHANNELS:
        raise ValueError(
            f"channel must be between 1 and {H2RG_NUM_CHANNELS}, got {channel}"
        )
    x1 = (channel - 1) * width
    x2 = x1 + width - 1
    return x1, x2, 0, array_size - 1


def _centered_vertical_stripe(
    height: int, array_size: int = H2RG_ARRAY_SIZE
) -> tuple[int, int, int, int]:
    """Full-width vertical burst stripe (horizontal window off, parallel outputs)."""
    y0 = (array_size - height) // 2
    return 0, array_size - 1, y0, y0 + height - 1


def _build_window_modes(array_size: int = H2RG_ARRAY_SIZE) -> tuple[WindowMode, ...]:
    full_span = array_size - 1
    half = array_size // 2
    return (
        WindowMode("Full frame", False, False, 0, full_span, 0, full_span),
        WindowMode(
            "SC 128",
            False,
            True,
            *_centered_vertical_stripe(128, array_size=array_size),
        ),
        WindowMode(
            "SC 256",
            False,
            True,
            *_centered_vertical_stripe(256, array_size=array_size),
        ),
        WindowMode(
            "SC 512",
            False,
            True,
            *_centered_vertical_stripe(512, array_size=array_size),
        ),
        WindowMode(
            "SC 1024",
            False,
            True,
            *_centered_vertical_stripe(1024, array_size=array_size),
        ),
        WindowMode("Channel 16", True, False, *_channel_window(16, array_size=array_size)),
        WindowMode("LL 1024x1024", True, True, *_window_region(0, 0, 1024)),
        WindowMode("LR 1024x1024", True, True, *_window_region(half, 0, 1024)),
        WindowMode("UL 1024x1024", True, True, *_window_region(0, half, 1024)),
        WindowMode("UR 1024x1024", True, True, *_window_region(half, half, 1024)),
        WindowMode("Center 1024x1024", True, True, *_centered_window(1024, array_size)),
        WindowMode("Center 512x512", True, True, *_centered_window(512, array_size)),
    )


WINDOW_MODES = _build_window_modes()
DETECTOR_MODES = ("Slow", "Fast")


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


def fits_header_text(
    header: dict | None, path: Path | None = None
) -> str | None:
    """Return a printable FITS header, preferring the on-disk file when available."""
    if path is not None:
        try:
            file_path = Path(path)
            if file_path.is_file():
                from astropy.io import fits

                with fits.open(file_path, memmap=False) as hdul:
                    return "\n".join(
                        card.image.rstrip() for card in hdul[0].header.cards
                    )
        except Exception:
            pass
    if not header:
        return None
    return "\n".join(f"{key:8} = {value}" for key, value in header.items())


class FitsHeaderDialog(QDialog):
    def __init__(self, parent: QWidget | None, *, title: str, text: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        editor = QTextEdit(self)
        editor.setReadOnly(True)
        editor.setFontFamily("Consolas")
        editor.setPlainText(text)
        layout.addWidget(editor)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def central_value_median(frame: numpy.ndarray) -> float | None:
    """Median ADU of the central region containing ~50% of image pixels."""
    data = numpy.asarray(frame)
    if data.size == 0:
        return None
    height, width = data.shape[:2]
    span = int(numpy.sqrt(0.5) * min(height, width))
    span = max(1, min(span, height, width))
    y0 = (height - span) // 2
    x0 = (width - span) // 2
    inner = data[y0 : y0 + span, x0 : x0 + span]
    if inner.size == 0:
        return None
    return float(numpy.median(inner))


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
        if mode.x_window == x_window and mode.y_window == y_window and (
            mode.x1,
            mode.x2,
            mode.y1,
            mode.y2,
        ) == (x1, x2, y1, y2):
            return index
    return -1


def detector_config_file(mode_index: int) -> str:
    if mode_index == 1:
        return MACIE_CONFIG_FILE_FAST
    return MACIE_CONFIG_FILE_SLOW


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


def map_server_fits_path(server_path: str, zmq_address: str = MACIE_ZMQ_ADDRESS) -> Path | None:
    """Map a Linux server FITS path to a local path when configured.

    Returns None on Windows when no explicit Linux-to-UNC mapping is configured,
    so callers fall back to ZMQ fetch instead of inventing invalid UNC paths.
    """
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
        return None

    return Path(server_path)


def load_fits_image(filepath: Path, *, reduction: str = "CDS", fowler_pairs: int = 2) -> numpy.ndarray:
    data, header = load_fits_data(filepath)
    return science_image_from_cube(
        data, header, reduction=reduction, fowler_pairs=fowler_pairs  # type: ignore[arg-type]
    )


def load_fits_image_from_bytes(
    payload: bytes, *, reduction: str = "CDS", fowler_pairs: int = 2
) -> numpy.ndarray:
    data, header = load_fits_data(payload)
    return science_image_from_cube(
        data, header, reduction=reduction, fowler_pairs=fowler_pairs  # type: ignore[arg-type]
    )


def is_science_fits_name(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith("_science.fits")


def ramp_fits_path_for_viewer(path: Path) -> Path:
    """Prefer the raw ramp FITS over the derived science file."""
    if is_science_fits_name(path.name):
        return path.with_name(path.name.replace("_science.fits", ".fits"))
    return path


def local_fits_file_for_viewer(path: Path | None) -> Path | None:
    if path is None:
        return None
    candidates = (ramp_fits_path_for_viewer(path), path)
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def launch_ds9(path: Path, executable: str = MACIE_DS9_EXECUTABLE) -> None:
    exe = shutil.which(executable) or executable
    launch_kwargs: dict[str, object] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        launch_kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        launch_kwargs["start_new_session"] = True
    subprocess.Popen([exe, str(path)], **launch_kwargs)


def open_directory_in_file_manager(path: Path) -> None:
    directory = path.expanduser().resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
        raise OSError(f"Failed to open {directory}")


def fits_basename(path: Path | str | None) -> str | None:
    if path is None:
        return None
    return Path(str(path)).name


def load_h2rg_rois_from_config() -> dict[int, tuple[int, int, int, int]]:
    rois: dict[int, tuple[int, int, int, int]] = {}
    for index in range(1, 11):
        key = f"ROI {index}"
        try:
            values = config.getarray("MACIE", key, dtype=int)
        except Exception:
            continue
        if len(values) == 4:
            rois[index] = (int(values[0]), int(values[1]), int(values[2]), int(values[3]))
    return rois


def is_new_ramp_fits(
    name: str | None,
    mtime: float,
    *,
    before_name: str | None,
    before_mtime: float,
) -> bool:
    if not name or is_science_fits_name(name):
        return False
    if before_name and name == before_name:
        return False
    if mtime > before_mtime:
        return True
    return bool(before_name and name != before_name)


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
    paths = list_ramp_fits_in_dir(directory, dir_ok=dir_ok)
    if not paths:
        return None
    return paths[-1]


def resolve_ramp_fits_path(
    ramp_path: Path,
    *,
    search_dirs: list[Path],
) -> Path | None:
    """Find a ramp FITS on disk when *ramp_path* is only a basename."""
    try:
        if ramp_path.is_file():
            return ramp_path
    except OSError:
        pass

    name = ramp_path.name
    for directory in search_dirs:
        try:
            if not directory.is_dir():
                continue
        except OSError:
            continue

        direct = directory / name
        try:
            if direct.is_file():
                return direct
        except OSError:
            pass

        try:
            for candidate in directory.rglob(name):
                if candidate.is_file() and not is_science_fits_name(candidate.name):
                    return candidate
        except OSError:
            continue

    return None


def list_ramp_fits_in_dir(directory: Path, *, dir_ok: bool | None = None) -> list[Path]:
    if dir_ok is False:
        return []
    if dir_ok is None:
        try:
            if not directory.is_dir():
                return []
        except OSError:
            return []
    candidates = []
    for pattern in ("*.fits", "*.FITS"):
        try:
            candidates.extend(directory.rglob(pattern))
        except OSError:
            continue
    candidates = [
        path
        for path in candidates
        if not is_science_fits_name(path.name)
    ]
    return sorted(
        candidates,
        key=lambda path: (
            path.stat().st_mtime if path.exists() else 0.0,
            path.name.lower(),
        ),
    )


def list_new_ramp_fits_in_dir(
    directory: Path,
    *,
    before_mtime: float,
    before_name: str | None,
    dir_ok: bool | None = None,
) -> list[Path]:
    new_paths: list[Path] = []
    for path in list_ramp_fits_in_dir(directory, dir_ok=dir_ok):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if is_new_ramp_fits(
            path.name,
            mtime,
            before_name=before_name,
            before_mtime=before_mtime,
        ):
            new_paths.append(path)
    return new_paths


class H2rgMainWindow(QMainWindow):
    closing = pyqtSignal()
    frame_ready = pyqtSignal(object)
    operation_failed = pyqtSignal(str)
    live_acquisition_failed = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    controls_enabled = pyqtSignal(bool)
    readouts_updated = pyqtSignal(object)
    init_button_state = pyqtSignal(str)
    exposure_timing_updated = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("H2RG / MACIE")
        app_icon = load_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        self.setMinimumSize(880, 650)
        self.ui = None
        self._init_runtime_state()

        self.frame_ready.connect(self._display_frame, Qt.QueuedConnection)
        self.operation_failed.connect(self._on_operation_failed, Qt.QueuedConnection)
        self.live_acquisition_failed.connect(
            self._on_live_acquisition_failed, Qt.QueuedConnection
        )
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
        self._central_value: float | None = None
        self._last_fits_mtime = 0.0
        self._last_fits_path: Path | None = None
        self._last_loaded_basename: str | None = None
        self._raw_fits_cube: numpy.ndarray | None = None
        self._raw_fits_header: dict | None = None
        self._h2rg_rois = load_h2rg_rois_from_config()
        self._roi_overlays: dict[int, object] = {}
        self._live_poll_stop = threading.Event()
        self._auto_levels_next = True
        self._operation_lock = threading.Lock()
        self._zmq_server = None
        self._zmq_address: str | None = None
        self._shutting_down = False
        self._last_tint_ms: float | None = None
        self._initialized = False
        self._last_zmq_fits_poll = 0.0
        self._fowler_pairs = MACIE_FOWLER_PAIRS_DEFAULT
        self.image = None
        self._image_placeholder: QLabel | None = None
        self._cursor_readout: QLabel | None = None
        self._cursor_readout_pending = None
        self._cursor_readout_proxy = None
        self._cursor_readout_timer = QTimer()
        self._cursor_readout_timer.setSingleShot(True)
        self._cursor_readout_timer.timeout.connect(self._flush_cursor_readout)
        self._stat_mean: QLineEdit | None = None
        self._stat_min: QLineEdit | None = None
        self._stat_max: QLineEdit | None = None
        self._stat_std: QLineEdit | None = None
        self._exposure_preview_timer = QTimer(self)
        self._exposure_preview_timer.setSingleShot(True)
        self._exposure_preview_timer.setInterval(450)
        self._exposure_preview_timer.timeout.connect(
            self._schedule_exposure_timing_preview
        )

    def _stage_load_ui(self) -> None:
        QApplication.processEvents()
        self.ui = loadUi(str(_MACIE_UI))
        self.setCentralWidget(self.ui)
        QTimer.singleShot(0, self._stage_connect_ui)

    def _stage_connect_ui(self) -> None:
        QApplication.processEvents()
        self._set_status("Loading…")
        self._set_controls_enabled(False)
        self.ui.checkBox_substract_background.setEnabled(False)
        QTimer.singleShot(0, self._finish_setup)

    def _finish_setup(self) -> None:
        QApplication.processEvents()
        try:
            self._relayout_control_panels()
            self._rebuild_layout()
            QApplication.processEvents()
            self._connect_signals()
            self._button_set_exposure.clicked.connect(self._on_set_exposure_clicked)
            self._button_autoscale.clicked.connect(self._autoscale_image)
            self._button_header.clicked.connect(self._show_fits_header)
            self._button_ds9.clicked.connect(self._open_fits_in_ds9)
            self._button_save_dir.clicked.connect(self._open_fits_save_dir)
            self._apply_styles()
            self._setup_image_placeholder()
            self.ui.frame_camera.installEventFilter(self)
            self._layout_image_frame()
            self._populate_comboboxes()
            self._sync_ramp_mode_fields()
            self._set_status("Not connected")
            threading.Thread(target=self._background_startup, daemon=True).start()
        except Exception as exc:
            print(f"H2RG GUI setup failed: {exc}")
            self._set_status(f"GUI setup failed: {exc}")

    def _setup_image_placeholder(self) -> None:
        self._image_placeholder = QLabel("No image yet", self.ui.frame_camera)
        self._image_placeholder.setAlignment(Qt.AlignCenter)
        self._image_placeholder.setStyleSheet(
            'color: rgb(180, 180, 200); font: 11pt "Segoe UI";'
        )

    def _clear_widget_layout(self, widget: QWidget) -> None:
        layout = widget.layout()
        if layout is None:
            return
        while layout.count():
            layout.takeAt(0)
        QWidget().setLayout(layout)

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

    def _setup_cursor_readout_row(self, parent_layout: QVBoxLayout) -> None:
        column = QVBoxLayout()
        column.setSpacing(6)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addStretch(1)
        self._button_autoscale = QPushButton("Autoscale")
        self._button_autoscale.setStyleSheet(PANEL_BUTTON_STYLE)
        self._button_autoscale.setMinimumHeight(CURSOR_READOUT_HEIGHT)
        self._button_autoscale.setFixedWidth(96)
        button_row.addWidget(self._button_autoscale)
        self._button_header = QPushButton("Header")
        self._button_header.setStyleSheet(PANEL_BUTTON_STYLE)
        self._button_header.setMinimumHeight(CURSOR_READOUT_HEIGHT)
        self._button_header.setFixedWidth(96)
        button_row.addWidget(self._button_header)
        self._button_ds9 = QPushButton("DS9")
        self._button_ds9.setStyleSheet(PANEL_BUTTON_STYLE)
        self._button_ds9.setMinimumHeight(CURSOR_READOUT_HEIGHT)
        self._button_ds9.setFixedWidth(96)
        button_row.addWidget(self._button_ds9)
        self._button_save_dir = QPushButton("Folder")
        self._button_save_dir.setStyleSheet(PANEL_BUTTON_STYLE)
        self._button_save_dir.setMinimumHeight(CURSOR_READOUT_HEIGHT)
        self._button_save_dir.setFixedWidth(96)
        self._button_save_dir.setToolTip("Open FITS save directory")
        button_row.addWidget(self._button_save_dir)
        button_row.addStretch(1)
        column.addLayout(button_row)

        if self._cursor_readout is None:
            self._cursor_readout = QLabel("Pixel: —  CV: —")
            self._cursor_readout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._cursor_readout.setFixedHeight(CURSOR_READOUT_HEIGHT)
            self._cursor_readout.setStyleSheet(
                'font: 10pt "Consolas", monospace;'
                " color: rgb(50, 50, 50);"
                " background-color: rgb(255, 255, 255);"
                " border: 1px solid rgb(50, 129, 140);"
                " border-radius: 4px;"
                " padding-left: 8px;"
            )
        column.addWidget(self._cursor_readout)
        parent_layout.addLayout(column)

    def _setup_nott_logo(self, parent_layout: QVBoxLayout) -> None:
        parent_layout.addWidget(make_nott_logo_title_header("H2RG / MACIE"))

    def _setup_image_statistics_panel(self) -> QGroupBox:
        group = QGroupBox("Image statistics")
        group.setStyleSheet(PANEL_GROUP_STYLE)
        group.setMaximumWidth(IMAGE_STATS_MAX_WIDTH)
        group.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        grid = QGridLayout(group)
        grid.setContentsMargins(8, 12, 8, 8)
        grid.setHorizontalSpacing(6)
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
        return group

    def _setup_cursor_readout(self) -> None:
        if self.image is None or self._cursor_readout is None:
            return
        if self._cursor_readout_proxy is not None:
            return

        import pyqtgraph as pg

        view = self.image.getView()
        graphics_view = getattr(getattr(self.image, "ui", None), "graphicsView", None)
        for widget in (graphics_view, self.image):
            if widget is not None and hasattr(widget, "setMouseTracking"):
                widget.setMouseTracking(True)
        view.installEventFilter(self)

        scene = view.scene()
        self._cursor_readout_proxy = pg.SignalProxy(
            scene.sigMouseMoved,
            rateLimit=30,
            slot=self._update_cursor_readout,
        )

    def _layout_image_frame(self) -> None:
        width = max(1, self.ui.frame_camera.width())
        height = max(1, self.ui.frame_camera.height())

        if self.image is not None:
            self.image.setGeometry(4, 4, max(1, width - 8), max(1, height - 8))
        elif self._image_placeholder is not None:
            self._image_placeholder.setGeometry(4, 4, max(1, width - 8), max(1, height - 8))

    def _scene_pos_to_image_xy(self, pos) -> tuple[int, int] | None:
        if self.image is None:
            return None
        image_item = self.image.getImageItem()
        if image_item is None or image_item.image is None:
            return None
        try:
            scene_pos = _normalize_scene_pos(pos)
            mouse = image_item.mapFromScene(scene_pos)
        except (TypeError, ValueError, AttributeError):
            return None

        x = int(mouse.x())
        y = int(mouse.y())
        img_h, img_w = image_item.image.shape[:2]
        if x < 0 or y < 0 or x >= img_w or y >= img_h:
            return None
        return x, y

    def _format_central_value_text(self) -> str:
        if self._central_value is None or not numpy.isfinite(self._central_value):
            return "CV: —"
        return f"CV: {_format_stat_value(self._central_value)}"

    def _format_cursor_readout_text(
        self, x: int | None, y: int | None, adu: float | None
    ) -> str:
        cv_text = self._format_central_value_text()
        if x is None or y is None or adu is None:
            return f"Pixel: —  {cv_text}"
        return f"Pixel: x={x}, y={y}  ADU={adu:.1f}  {cv_text}"

    def _update_central_value(self, frame: numpy.ndarray | None) -> None:
        if frame is None:
            self._central_value = None
            return
        self._central_value = central_value_median(frame)

    def _sync_cursor_readout_label(self) -> None:
        if self._cursor_readout is None:
            return
        if self._cursor_readout_pending is not None and self.image is not None:
            self._flush_cursor_readout()
            return
        self._cursor_readout.setText(self._format_cursor_readout_text(None, None, None))

    def _update_cursor_readout_from_view_pos(self, view_pos) -> None:
        self._cursor_readout_pending = view_pos
        if not self._cursor_readout_timer.isActive():
            self._cursor_readout_timer.start(CURSOR_READOUT_INTERVAL_MS)

    def _flush_cursor_readout(self) -> None:
        if self._cursor_readout is None:
            return
        pos = self._cursor_readout_pending
        if pos is None:
            return
        if self.image is None:
            self._cursor_readout.setText(self._format_cursor_readout_text(None, None, None))
            return

        img = self.image.getImageItem().image
        if img is None:
            self._cursor_readout.setText(self._format_cursor_readout_text(None, None, None))
            return

        pixel = self._scene_pos_to_image_xy(pos)
        if pixel is None:
            self._cursor_readout.setText(self._format_cursor_readout_text(None, None, None))
            return

        x, y = pixel
        adu = float(img[y, x])
        self._cursor_readout.setText(self._format_cursor_readout_text(x, y, adu))

    def _update_cursor_readout(self, pos) -> None:
        if isinstance(pos, (tuple, list)) and len(pos) == 1:
            pos = pos[0]
        self._update_cursor_readout_from_view_pos(pos)

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

        if self.image is not None:
            view = self.image.getView()
            if obj is view and event.type() == QEvent.MouseMove:
                self._update_cursor_readout_from_view_pos(view.mapToScene(event.pos()))
            elif obj is view and event.type() == QEvent.Leave:
                self._cursor_readout_pending = None
                if self._cursor_readout is not None:
                    self._cursor_readout.setText(
                        self._format_cursor_readout_text(None, None, None)
                    )

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
        try:
            self._setup_cursor_readout()
        except Exception as exc:
            print(f"H2RG cursor readout setup failed: {exc}")
        self._layout_image_frame()

        if self._current_frame is not None:
            self._display_frame(self._current_frame)

        self._setup_roi_overlays()

    def _resolved_zmq_address(self) -> str:
        if self._zmq_address is None:
            from nottcontrol.camera.macie.zmq_server_manager import (
                select_macie_zmq_address,
            )

            self._zmq_address = select_macie_zmq_address()
        return self._zmq_address

    def _background_startup(self) -> None:
        from nottcontrol.camera.macie.zmq_server_manager import (
            MacieZmqServerProcess,
            macie_zmq_addresses,
            select_macie_zmq_address,
        )

        self._zmq_address = select_macie_zmq_address()
        if self._zmq_server is None:
            self._zmq_server = MacieZmqServerProcess(self._zmq_address)
        self._fits_dir_ok = path_is_directory(self._save_dir)
        if not self._fits_dir_ok and sys.platform == "win32":
            self.status_updated.emit(
                "Not connected — FITS preview uses ZMQ fetch or SMB path mapping"
            )

        try:
            self._zmq_server.ensure_running()
            self._zmq_address = self._zmq_server.zmq_address
            if self._zmq_server.started_by_gui:
                self.status_updated.emit("ZMQ server started")
            elif self._fits_dir_ok is not False:
                addresses = macie_zmq_addresses()
                if addresses and self._zmq_address != addresses[0]:
                    self.status_updated.emit(
                        f"Connected to alternate ZMQ server at {self._zmq_address}"
                    )
                else:
                    self.status_updated.emit(
                        f"Connected to ZMQ server at {self._zmq_address}"
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
        self._clear_widget_layout(box)
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
        self.ui.lineEdit_status.setReadOnly(True)
        self.ui.lineEdit_status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.ui.lineEdit_status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.ui.lineEdit_status.setMinimumHeight(24)
        form.addWidget(self.ui.lineEdit_status, 2, 1)
        form.setColumnStretch(1, 1)
        combo_policy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        for combo in (self.ui.comboBox_detector_mode, self.ui.comboBox_window_mode):
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(12)
            combo.setMaximumWidth(132)
            combo.setSizePolicy(combo_policy)
        outer.addLayout(form, stretch=1)

    def _layout_acquisition_panel(self) -> None:
        box = self.ui.groupBox_acquisition
        self._clear_widget_layout(box)
        box.setMinimumHeight(380)
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
        self.ui.label_7.setText("Saved ramps:")
        self.ui.label_4.setText("Total integration time (ms):")
        for row, (label_name, field_name) in enumerate(editable_rows):
            label = getattr(self.ui, label_name)
            field = getattr(self.ui, field_name)
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            form.addWidget(label, row, 0)
            form.addWidget(field, row, 1)

        if not hasattr(self, "_button_set_exposure"):
            self._button_set_exposure = QPushButton("Set")
        self._button_set_exposure.setStyleSheet(PANEL_BUTTON_STYLE)
        self._button_set_exposure.setFixedSize(52, 28)
        self._button_set_exposure.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        mode_row = len(editable_rows)
        self._label_ramp_mode = QLabel("Ramp mode:")
        self._comboBox_ramp_mode = QComboBox()
        for label, mode in RAMP_MODE_ITEMS:
            self._comboBox_ramp_mode.addItem(label, mode)
        cds_index = next(
            (i for i, (_, mode) in enumerate(RAMP_MODE_ITEMS) if mode == "CDS"),
            0,
        )
        self._comboBox_ramp_mode.setCurrentIndex(cds_index)
        self._label_fowler_pairs = QLabel("Fowler pairs:")
        self._lineEdit_fowler_pairs = QLineEdit(str(self._fowler_pairs))
        self._lineEdit_fowler_pairs.setFixedWidth(48)
        for widget in (
            self._label_ramp_mode,
            self._comboBox_ramp_mode,
            self._label_fowler_pairs,
            self._lineEdit_fowler_pairs,
        ):
            widget.setStyleSheet(PANEL_LABEL_STYLE if isinstance(widget, QLabel) else PANEL_FIELD_STYLE)
        form.addWidget(self._label_ramp_mode, mode_row, 0)
        form.addWidget(self._comboBox_ramp_mode, mode_row, 1)
        form.addWidget(self._label_fowler_pairs, mode_row + 1, 0)
        form.addWidget(self._lineEdit_fowler_pairs, mode_row + 1, 1)
        form.addWidget(self._button_set_exposure, 0, 2, mode_row + 2, 1, Qt.AlignTop)

        separator_row = mode_row + 2
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setStyleSheet("color: rgb(50, 129, 140);")
        separator.setFixedHeight(2)
        form.addWidget(separator, separator_row, 0, 1, 3)

        timing_row = separator_row + 1
        self._label_frame_time = QLabel("Frame time (ms):")
        self._lineEdit_frame_time = QLineEdit("—")
        self._lineEdit_frame_time.setReadOnly(True)
        self._label_photon_time = QLabel("Photon time (s):")
        self._lineEdit_photon_time = QLineEdit("—")
        self._lineEdit_photon_time.setReadOnly(True)
        self._label_execution_time = QLabel("Execution time (s):")
        self._lineEdit_execution_time = QLineEdit("—")
        self._lineEdit_execution_time.setReadOnly(True)
        self._label_efficiency = QLabel("Efficiency (%):")
        self._lineEdit_efficiency = QLineEdit("—")
        self._lineEdit_efficiency.setReadOnly(True)
        for offset, (label, field) in enumerate(
            (
                (self._label_frame_time, self._lineEdit_frame_time),
                (self._label_photon_time, self._lineEdit_photon_time),
                (self._label_execution_time, self._lineEdit_execution_time),
                (self._label_efficiency, self._lineEdit_efficiency),
            )
        ):
            label.setStyleSheet(PANEL_LABEL_STYLE)
            field.setStyleSheet(
                PANEL_FIELD_STYLE + " QLineEdit { background: rgb(250, 252, 252); }"
            )
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            form.addWidget(label, timing_row + offset, 0)
            form.addWidget(field, timing_row + offset, 1)

        footer_row = timing_row + 4
        for offset, (label_name, field_name) in enumerate(
            (
                ("label_4", "lineEdit_integration_time_total"),
                ("label_8", "lineEdit_frame_nb"),
            )
        ):
            label = getattr(self.ui, label_name)
            field = getattr(self.ui, field_name)
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            form.addWidget(label, footer_row + offset, 0)
            form.addWidget(field, footer_row + offset, 1)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(2, 0)
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
        self._clear_widget_layout(box)
        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        outer = QHBoxLayout(box)
        outer.setContentsMargins(8, 12, 8, 8)
        outer.setSpacing(8)

        left = QVBoxLayout()
        left.setSpacing(2)
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
        middle.setSpacing(2)
        for index in range(1, 6):
            middle.addWidget(getattr(self.ui, f"checkBox_ROI{index}"))
        middle.addStretch()
        outer.addLayout(middle, stretch=1)

        right = QVBoxLayout()
        right.setSpacing(2)
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
        self._setup_cursor_readout_row(image_column_layout)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)
        bottom_row.addWidget(self._setup_image_statistics_panel(), stretch=0)
        panel_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.ui.groupBox_visualisation.setSizePolicy(panel_policy)
        bottom_row.addWidget(self.ui.groupBox_visualisation, stretch=1)
        image_column_layout.addLayout(bottom_row)

        outer.addWidget(image_column, stretch=1)

        right_host = QWidget()
        right_host.setFixedWidth(RIGHT_PANEL_WIDTH)
        right = QVBoxLayout(right_host)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(12)

        self._setup_nott_logo(right)

        for box in (
            self.ui.groupBox_conf,
            self.ui.groupBox_acquisition,
        ):
            box.setSizePolicy(panel_policy)
            right.addWidget(box)

        right.addStretch()
        outer.addWidget(right_host, stretch=0)

    def _apply_styles(self) -> None:
        self.setStyleSheet(H2RG_WINDOW_STYLE)
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

        for button in (
            getattr(self, "_button_set_exposure", None),
            getattr(self, "_button_autoscale", None),
            getattr(self, "_button_header", None),
            getattr(self, "_button_ds9", None),
            getattr(self, "_button_save_dir", None),
        ):
            if button is not None:
                button.setStyleSheet(PANEL_BUTTON_STYLE)

        for widget in (
            getattr(self, "_label_ramp_mode", None),
            getattr(self, "_label_fowler_pairs", None),
            getattr(self, "_label_frame_time", None),
            getattr(self, "_label_photon_time", None),
            getattr(self, "_label_execution_time", None),
            getattr(self, "_label_efficiency", None),
        ):
            if widget is not None:
                widget.setStyleSheet(PANEL_LABEL_STYLE)

        for widget in (
            getattr(self, "_comboBox_ramp_mode", None),
            getattr(self, "_lineEdit_fowler_pairs", None),
            getattr(self, "_lineEdit_frame_time", None),
            getattr(self, "_lineEdit_photon_time", None),
            getattr(self, "_lineEdit_execution_time", None),
            getattr(self, "_lineEdit_efficiency", None),
        ):
            if widget is None:
                continue
            if isinstance(widget, QLineEdit):
                widget.setStyleSheet(
                    PANEL_FIELD_STYLE
                    + " QLineEdit { background: rgb(250, 252, 252); }"
                )
            else:
                widget.setStyleSheet(PANEL_FIELD_STYLE)

        stats_panel = getattr(self, "_stat_mean", None)
        if stats_panel is not None and stats_panel.parent() is not None:
            stats_panel.parent().setStyleSheet(PANEL_GROUP_STYLE)

    def _populate_comboboxes(self) -> None:
        self.ui.comboBox_detector_mode.clear()
        self.ui.comboBox_detector_mode.addItems(list(DETECTOR_MODES))
        if MACIE_CONFIG_FILE == MACIE_CONFIG_FILE_FAST:
            self.ui.comboBox_detector_mode.setCurrentIndex(1)
        self.ui.comboBox_window_mode.clear()
        self.ui.comboBox_window_mode.addItems([mode.label for mode in WINDOW_MODES])

    def _connect_signals(self) -> None:
        self.ui.button_init.clicked.connect(self.init_camera)
        self.ui.button_powerOn.clicked.connect(self.power_on)
        self.ui.button_powerOff.clicked.connect(self.power_off)
        self.ui.button_take_background.clicked.connect(self.take_background)
        self.ui.button_live.clicked.connect(self.live_clicked)
        self.ui.button_acquire.clicked.connect(self.acquire)
        self.ui.button_halt.clicked.connect(self.halt)
        self.ui.checkBox_substract_background.toggled.connect(self._refresh_display)

        self.ui.checkBox_avg.toggled.connect(self._on_avg_toggled)
        self.ui.checkBox_max.toggled.connect(self._on_max_toggled)
        self.ui.checkBox_min.toggled.connect(self._on_min_toggled)
        for index in range(1, 11):
            checkbox = getattr(self.ui, f"checkBox_ROI{index}", None)
            if checkbox is not None:
                checkbox.toggled.connect(self._on_roi_toggled)

        for widget in (
            self.ui.lineEdit_integration_time,
            self.ui.lineEdit_nb_coadd,
            self.ui.lineEdit_nb_frames,
            getattr(self, "_lineEdit_fowler_pairs", None),
        ):
            if widget is not None:
                widget.editingFinished.connect(self._on_exposure_fields_changed)

        ramp_mode = getattr(self, "_comboBox_ramp_mode", None)
        if ramp_mode is not None:
            ramp_mode.currentIndexChanged.connect(self._on_ramp_mode_changed)

        self.ui.comboBox_window_mode.currentIndexChanged.connect(
            self._on_window_mode_changed
        )
        self.ui.comboBox_detector_mode.currentIndexChanged.connect(
            self._on_detector_mode_changed
        )

    def _on_avg_toggled(self, checked: bool) -> None:
        if checked:
            self.ui.checkBox_max.setChecked(False)
            self.ui.checkBox_min.setChecked(False)
        self._refresh_display()

    def _on_max_toggled(self, checked: bool) -> None:
        if checked:
            self.ui.checkBox_avg.setChecked(False)
            self.ui.checkBox_min.setChecked(False)
        self._refresh_display()

    def _on_min_toggled(self, checked: bool) -> None:
        if checked:
            self.ui.checkBox_avg.setChecked(False)
            self.ui.checkBox_max.setChecked(False)
        self._refresh_display()

    def _on_roi_toggled(self, _checked: bool) -> None:
        self._update_roi_overlays()
        self._refresh_display()

    def _selected_ramp_mode(self) -> str:
        if hasattr(self, "_comboBox_ramp_mode"):
            data = self._comboBox_ramp_mode.currentData()
            if data in RAMP_MODES:
                return str(data)
        return "CDS"

    def _fowler_pairs_value(self) -> int:
        try:
            if hasattr(self, "_lineEdit_fowler_pairs"):
                return max(1, min(int(self._lineEdit_fowler_pairs.text().strip()), 8))
        except ValueError:
            pass
        return self._fowler_pairs

    def _sync_ramp_mode_fields(self) -> None:
        if not hasattr(self, "_comboBox_ramp_mode"):
            return
        fowler = self._selected_ramp_mode() == "Fowler"
        single_frame = self._selected_ramp_mode() == "SingleFrame"
        if hasattr(self, "_lineEdit_fowler_pairs"):
            self._lineEdit_fowler_pairs.setEnabled(fowler)
        if hasattr(self, "_label_fowler_pairs"):
            self._label_fowler_pairs.setEnabled(fowler)
        if hasattr(self, "ui") and self.ui is not None:
            self.ui.lineEdit_integration_time.setEnabled(not fowler and not single_frame)
            if fowler:
                label = "Integration time (ms):"
                tooltip = (
                    "Fowler timing is controlled by Fowler pairs and ASIC registers. "
                    "Photon time is shown below after Set."
                )
            elif single_frame:
                label = "Integration time (ms):"
                tooltip = (
                    "Single Frame uses one clocked frame (no drops). "
                    "Photon time equals the frame time shown below after Set."
                )
            elif self._selected_ramp_mode() == "Ramp":
                label = "Integration time (ms):"
                tooltip = (
                    "Target DIT for up-the-ramp readout. Ramp mode saves one raw sample "
                    "per ramp; use Saved ramps for multiple frames."
                )
            else:
                label = "Integration time (ms):"
                tooltip = "Target photon-collection time for CDS ramps."
            self.ui.label_5.setText(label)
            self.ui.lineEdit_integration_time.setToolTip(tooltip)
            self.ui.label_5.setToolTip(tooltip)

    def _sync_fowler_pairs_enabled(self) -> None:
        self._sync_ramp_mode_fields()

    def _windowed_cds_layout(self) -> bool:
        if self.ui is None:
            return False
        index = self.ui.comboBox_window_mode.currentIndex()
        if not 0 <= index < len(WINDOW_MODES):
            return False
        mode = WINDOW_MODES[index]
        return mode.x_window or mode.y_window

    def _on_ramp_mode_changed(self, _index: int) -> None:
        self._sync_ramp_mode_fields()
        if not self._initialized:
            return
        self._on_exposure_fields_changed()

    def _display_mode(self) -> str:
        if self.ui.checkBox_avg.isChecked():
            return "avg"
        if self.ui.checkBox_max.isChecked():
            return "max"
        if self.ui.checkBox_min.isChecked():
            return "min"
        return "cds"

    def _frame_from_display_mode(self) -> numpy.ndarray | None:
        if self._raw_fits_cube is not None:
            data = numpy.asarray(self._raw_fits_cube, dtype=numpy.float32)
            header = self._raw_fits_header or {}
            mode = self._display_mode()
            if data.ndim <= 2:
                return data
            axis = ramp_sample_axis(header, data.shape)
            if mode == "avg":
                return numpy.mean(data, axis=axis).astype(numpy.float32)
            if mode == "max":
                return numpy.max(data, axis=axis).astype(numpy.float32)
            if mode == "min":
                return numpy.min(data, axis=axis).astype(numpy.float32)
            return science_image_from_cube(
                data,
                header,
                reduction=self._selected_ramp_mode(),  # type: ignore[arg-type]
                fowler_pairs=self._fowler_pairs_value(),
            )
        return self._current_frame

    def _selected_roi_indices(self) -> list[int]:
        selected = []
        for index in range(1, 11):
            checkbox = getattr(self.ui, f"checkBox_ROI{index}", None)
            if checkbox is not None and checkbox.isChecked():
                selected.append(index)
        return selected

    def _stats_array(self, frame: numpy.ndarray) -> numpy.ndarray:
        selected = self._selected_roi_indices()
        if not selected:
            return numpy.asarray(frame, dtype=numpy.float64)
        parts = []
        height, width = frame.shape[:2]
        for index in selected:
            roi = self._h2rg_rois.get(index)
            if roi is None:
                continue
            x, y, w, h = roi
            x_end = min(width, x + w)
            y_end = min(height, y + h)
            if x >= width or y >= height or x_end <= x or y_end <= y:
                continue
            parts.append(frame[y:y_end, x:x_end].ravel())
        if not parts:
            return numpy.asarray(frame, dtype=numpy.float64)
        return numpy.concatenate(parts)

    def _build_display_frame(self) -> numpy.ndarray | None:
        frame = self._frame_from_display_mode()
        if frame is None:
            return None
        display = frame
        if (
            self.ui.checkBox_substract_background.isChecked()
            and self._background is not None
            and self._background.shape == frame.shape
        ):
            display = frame - self._background
        return display

    def _setup_roi_overlays(self) -> None:
        if self.image is None or not self._h2rg_rois:
            return

        import pyqtgraph as pg

        view = self.image.getView()
        colors = (
            "#ff6b6b",
            "#ffd166",
            "#06d6a0",
            "#118ab2",
            "#8338ec",
            "#fb5607",
            "#3a86ff",
            "#ff006e",
            "#8ac926",
            "#1982c4",
        )
        for index, (x, y, w, h) in self._h2rg_rois.items():
            if index in self._roi_overlays:
                continue
            color = colors[(index - 1) % len(colors)]
            roi = pg.RectROI(
                [x, y],
                [w, h],
                pen=pg.mkPen(color, width=2),
                movable=False,
                removable=False,
            )
            roi.setZValue(20)
            view.addItem(roi)
            self._roi_overlays[index] = roi
        self._update_roi_overlays()

    def _update_roi_overlays(self) -> None:
        selected = set(self._selected_roi_indices())
        for index, roi in self._roi_overlays.items():
            roi.setVisible(index in selected)

    def _set_live_dependent_controls(self, live: bool) -> None:
        if self.ui is None or not self._initialized:
            return
        enabled = not live
        self.ui.button_acquire.setEnabled(enabled)
        if hasattr(self, "_button_set_exposure"):
            self._button_set_exposure.setEnabled(enabled)
        self.ui.button_take_background.setEnabled(enabled)
        self.ui.comboBox_detector_mode.setEnabled(enabled)
        self.ui.comboBox_window_mode.setEnabled(enabled)
        self.ui.button_init.setEnabled(enabled)
        self.ui.button_powerOn.setEnabled(enabled)
        self.ui.button_powerOff.setEnabled(enabled)

    def _stop_live_ui(self) -> None:
        self._live_active = False
        self._live_poll_stop.set()
        if self.ui is not None:
            self.ui.button_live.setText("Live")
        self._set_live_dependent_controls(False)

    def _activate_live_ui(self) -> None:
        self._live_active = True
        self._live_poll_stop.clear()
        if self.ui is not None:
            self.ui.button_live.setText("Stop live")
        self._set_live_dependent_controls(True)

        def poll_frames() -> None:
            import time

            while (
                self._live_active
                and self._macie is not None
                and not self._live_poll_stop.is_set()
            ):
                loaded = self._load_latest_frame(force=False, macie=self._macie)
                if loaded is not None:
                    frame, _path = loaded
                    self.frame_ready.emit(frame)
                time.sleep(0.5)

        threading.Thread(target=poll_frames, daemon=True).start()

    def _fits_snapshot_before_acquire(self, macie) -> tuple[float, str | None]:
        before_mtime = self._latest_fits_mtime()
        before_name = fits_basename(self._newest_fits_file(allow_probe=True))
        if not self._local_fits_accessible(allow_probe=True):
            try:
                server_path = macie.get_newest_fits_path()
            except Exception:
                server_path = None
            if server_path:
                server_name = fits_basename(server_path)
                if server_name and not is_science_fits_name(server_name):
                    before_name = server_name
        return before_mtime, before_name

    def _on_detector_mode_changed(self, index: int) -> None:
        if not self._initialized:
            return
        self._schedule_detector_mode_apply(index)

    def _schedule_detector_mode_apply(self, index: int) -> None:
        if index < 0 or index >= len(DETECTOR_MODES):
            return
        window_index = self.ui.comboBox_window_mode.currentIndex()

        def operation() -> None:
            macie = self._ensure_macie()
            self._apply_detector_mode_to_macie(macie, index, window_index)

        self._run_macie_operation("Detector mode", operation)

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
        if mode.y_window and not mode.x_window:
            status = (
                f"{mode.label} — burst stripe y=[{mode.y1},{mode.y2}] "
                "(32 outputs)"
            )
        elif mode.x_window or mode.y_window:
            status = (
                f"{mode.label} — x=[{mode.x1},{mode.x2}] y=[{mode.y1},{mode.y2}]"
            )
        else:
            status = mode.label
        self.status_updated.emit(status)
        self._refresh_exposure_timing(macie)
        if self._initialized:
            self._on_exposure_fields_changed()

    def _apply_detector_mode_to_macie(
        self, macie, mode_index: int, window_index: int
    ) -> None:
        config_file = detector_config_file(mode_index)
        self.status_updated.emit(f"Switching to {DETECTOR_MODES[mode_index]} mode…")
        macie.reinit_camera(config_file)
        if 0 <= window_index < len(WINDOW_MODES):
            self._apply_window_mode_to_macie(macie, window_index)
        self._sync_save_dir_from_server(macie)
        self._refresh_readouts(macie)
        self._refresh_exposure_timing(macie)
        self.status_updated.emit(f"Detector mode: {DETECTOR_MODES[mode_index]}")

    def _on_exposure_fields_changed(self) -> None:
        self._update_total_integration_label()
        if self._initialized and self._macie is not None:
            self._exposure_preview_timer.start()

    def _on_set_exposure_clicked(self) -> None:
        self._update_total_integration_label()
        if not self._initialized:
            self._set_status("Initialize camera before setting exposure")
            return

        def operation() -> None:
            self._apply_exposure_settings(self._ensure_macie())

        self._run_macie_operation("Set exposure", operation)

    def _autoscale_image(self) -> None:
        if self.image is None or self._current_frame is None:
            return
        self._auto_levels_next = True
        self._refresh_display()

    def _show_fits_header(self) -> None:
        path = self._last_fits_path
        if path is not None and is_science_fits_name(path.name):
            path = None
        text = fits_header_text(self._raw_fits_header, path)
        if not text:
            QMessageBox.information(
                self,
                "FITS header",
                "No FITS file loaded yet.",
            )
            return
        title = "FITS header"
        if self._last_fits_path is not None:
            title = f"FITS header — {self._last_fits_path.name}"
        dialog = FitsHeaderDialog(self, title=title, text=text)
        dialog.exec_()

    def _open_fits_in_ds9(self) -> None:
        path = local_fits_file_for_viewer(self._last_fits_path)
        if path is None:
            QMessageBox.information(
                self,
                "Open in DS9",
                "No FITS file is available on disk yet. "
                "Acquire or load a frame from a local path first.",
            )
            return
        try:
            launch_ds9(path)
        except FileNotFoundError:
            QMessageBox.warning(
                self,
                "Open in DS9",
                f"DS9 executable not found ({MACIE_DS9_EXECUTABLE!r}). "
                "Install SAOImage DS9 or set MACIE ds9_executable in config.ini.",
            )
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Open in DS9",
                f"Failed to launch DS9 for {path.name}: {exc}",
            )

    def _resolve_fits_save_dir_for_open(self) -> Path | None:
        macie = getattr(self, "_macie", None)
        if macie is not None:
            try:
                self._sync_save_dir_from_server(macie)
            except Exception:
                pass

        if self._local_fits_accessible(allow_probe=True):
            return self._save_dir

        configured = config.get("MACIE", "fits_directory", fallback="").strip()
        if configured:
            path = Path(os.path.expanduser(configured))
            try:
                if path.is_dir():
                    return path
            except OSError:
                pass

        return None

    def _open_fits_save_dir(self) -> None:
        directory = self._resolve_fits_save_dir_for_open()
        if directory is None:
            QMessageBox.information(
                self,
                "Open save directory",
                "The FITS save directory is not available on this machine.\n\n"
                f"Configured path: {self._save_dir}\n\n"
                "Set [MACIE] fits_directory (and fits_linux_path_prefix / "
                "fits_windows_unc_root on Windows) in config.ini to a local "
                "or mapped path.",
            )
            return
        try:
            open_directory_in_file_manager(directory)
        except FileNotFoundError:
            QMessageBox.warning(
                self,
                "Open save directory",
                f"Directory not found:\n{directory}",
            )
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Open save directory",
                f"Failed to open {directory}:\n{exc}",
            )

    def _set_status(self, message: str) -> None:
        if self.ui is None:
            return
        status = self.ui.lineEdit_status
        status.setText(message)
        status.setCursorPosition(0)
        status.home(False)

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
        if hasattr(self, "_button_set_exposure"):
            self._button_set_exposure.setEnabled(enabled)

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
        self._lineEdit_frame_time.setText(f"{timing['frametime_s'] * 1000:.4g}")
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

    def _on_live_macie_error(self, exc: Exception) -> None:
        self.live_acquisition_failed.emit(str(exc))

    def _on_live_acquisition_failed(self, message: str) -> None:
        if self._macie is not None:
            try:
                self._macie.stop_continuous_acquisition()
            except Exception:
                pass
        self._stop_live_ui()
        self._set_status(f"Live acquisition stopped: {message}")
        QMessageBox.warning(self, "H2RG", f"Live acquisition stopped: {message}")

    def _ensure_macie(self, config_file: str | None = None):
        from nottcontrol.camera.macie.macie_interface import MacieInterface

        if config_file is None:
            config_file = detector_config_file(
                self.ui.comboBox_detector_mode.currentIndex()
            )
        if self._macie is None:
            self._macie = MacieInterface(
                offline_mode=MACIE_OFFLINE_MODE,
                config_file=config_file,
                zmq_address=self._resolved_zmq_address(),
            )
        else:
            self._macie.set_config_file(config_file)
        self._macie.set_live_error_callback(self._on_live_macie_error)
        return self._macie

    def _run_macie_operation(self, label: str, operation) -> None:
        def worker() -> None:
            macie = self._macie
            if macie is not None:
                macie.pause_live_acquisition()
            try:
                with self._operation_lock:
                    operation()
            except Exception as exc:
                self.operation_failed.emit(f"{label} failed: {exc}")
            finally:
                if macie is not None:
                    macie.resume_live_acquisition()

        threading.Thread(target=worker, daemon=True).start()

    def init_camera(self) -> None:
        if self._live_active:
            self._on_operation_failed("Stop live mode before initializing")
            return
        self.init_button_state.emit("busy")
        self.status_updated.emit("Initializing…")
        window_index = self.ui.comboBox_window_mode.currentIndex()
        detector_index = self.ui.comboBox_detector_mode.currentIndex()

        def operation() -> None:
            macie = self._ensure_macie(detector_config_file(detector_index))
            macie.reinit_camera()
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
        if self._live_active:
            self._on_operation_failed("Stop live mode before power on")
            return
        self._run_macie_operation("Power on", lambda: self._ensure_macie().power_on())

    def power_off(self) -> None:
        if self._live_active:
            self._on_operation_failed("Stop live mode before power off")
            return
        self._run_macie_operation("Power off", lambda: self._ensure_macie().power_off())

    def _apply_exposure_settings(self, macie) -> dict[str, float | int]:
        try:
            ncoadds = int(self.ui.lineEdit_nb_coadd.text().strip() or "1")
            nseq = int(self.ui.lineEdit_nb_frames.text().strip() or "1")
            self._fowler_pairs = self._fowler_pairs_value()
        except ValueError as exc:
            raise ValueError(f"Invalid exposure field: {exc}") from exc

        ramp_mode = self._selected_ramp_mode()
        if ramp_mode in ("Fowler", "SingleFrame"):
            try:
                preview_timing = macie.read_exposure_timing()
                tint_ms = preview_timing["frametime_s"] * 1000.0
            except Exception:
                tint_ms = 1.0
        else:
            try:
                tint_ms = float(self.ui.lineEdit_integration_time.text().strip())
            except ValueError as exc:
                raise ValueError(f"Invalid integration time: {exc}") from exc
            if tint_ms <= 0:
                raise ValueError("Integration time must be greater than zero")

        result = macie.configure_ramp_exposure(
            tint_ms,
            ramp_mode=ramp_mode,
            fowler_pairs=self._fowler_pairs,
            ngmax=MACIE_INTEGRATION_NGROUPS_MAX,
            ncoadds=ncoadds,
            nseq=nseq,
            save=True,
            windowed_cds=self._windowed_cds_layout() and ramp_mode == "CDS",
        )
        self._last_tint_ms = float(result["inttime_ms"])
        if ramp_mode != "Fowler":
            self.ui.lineEdit_integration_time.setText(f"{self._last_tint_ms:.6g}")
        self._update_total_integration_label(actual_tint_ms=self._last_tint_ms)
        self._refresh_exposure_timing(macie)
        if ramp_mode == "Fowler":
            mode_detail = f"Fowler-{result['fowler_pairs']}, reads={result['nreads']}"
        elif ramp_mode == "SingleFrame":
            mode_detail = "single frame, groups=1, drops=0, reads=1"
        elif ramp_mode == "Ramp":
            mode_detail = (
                f"raw sample, groups={result['ngroups']}, "
                f"drops={result['ndrops']}, reads={result['nreads']}"
            )
        else:
            mode_detail = (
                f"groups={result['ngroups']}, drops={result['ndrops']}, "
                f"reads={result['nreads']}"
                + (" (window CDS)" if self._windowed_cds_layout() else "")
            )
        self.status_updated.emit(
            f"Ramp {ramp_mode}: {self._last_tint_ms:.3g} ms photon ({mode_detail}, "
            f"saved ramps={nseq})"
        )
        return result

    def acquire(self) -> None:
        if self._live_active:
            self._on_operation_failed("Stop live mode before acquiring")
            return

        def operation() -> None:
            from nottcontrol.camera.macie.macie_interface import ZMQ_ACQUIRE_TIMEOUT_MS

            macie = self._ensure_macie()
            try:
                ncoadds = int(self.ui.lineEdit_nb_coadd.text().strip() or "1")
                nseq = int(self.ui.lineEdit_nb_frames.text().strip() or "1")
            except ValueError as exc:
                raise ValueError(f"Invalid exposure field: {exc}") from exc

            exposure = self._apply_exposure_settings(macie)
            self._fits_dir_ok = None
            before_mtime, before_name = self._fits_snapshot_before_acquire(macie)
            wait_timeout_s = fits_wait_timeout_s(
                float(exposure["execution_s"]),
                ncoadds=ncoadds,
                nseq=nseq,
                margin_s=MACIE_FITS_WAIT_MARGIN_S,
                maximum_s=(ZMQ_ACQUIRE_TIMEOUT_MS / 1000.0) + MACIE_FITS_WAIT_MARGIN_S,
            )
            macie.acquire()
            ramp_paths, frame, preview_path = self._wait_for_acquire_frames(
                before_mtime,
                macie,
                before_name=before_name,
                expected_count=max(1, nseq),
                timeout_s=wait_timeout_s,
            )
            if frame is not None and preview_path is not None:
                science_paths: list[Path] = []
                for ramp_path in ramp_paths:
                    if (
                        ramp_path.name == preview_path.name
                        and self._raw_fits_header is not None
                    ):
                        science_path = self._save_science_fits(frame, ramp_path)
                    else:
                        science_path = self._save_science_fits_from_ramp(ramp_path)
                    if science_path is not None:
                        science_paths.append(science_path)
                preview_science = (
                    science_paths[-1] if science_paths else preview_path
                )
                self._last_fits_path = preview_science
                self._auto_levels_next = True
                self.frame_ready.emit(frame)
                self.status_updated.emit(self._acquire_complete_status(ramp_paths, science_paths))
            else:
                self.status_updated.emit(self._missing_fits_status())

        self._run_macie_operation("Acquire", operation)

    def _acquire_complete_status(
        self, ramp_paths: list[Path], science_paths: list[Path]
    ) -> str:
        if len(ramp_paths) > 1:
            base = (
                f"Acquire complete — {len(ramp_paths)} ramps "
                f"({ramp_paths[0].name} … {ramp_paths[-1].name})"
            )
        elif ramp_paths:
            base = f"Acquire complete — {ramp_paths[0].name}"
        else:
            base = "Acquire complete"
        if science_paths:
            if len(science_paths) > 1:
                return (
                    f"{base}; science FITS ×{len(science_paths)} "
                    f"({science_paths[-1].name})"
                )
            return f"{base}; science FITS: {science_paths[0].name}"
        return base

    def _fits_staging_dir(self) -> Path:
        directory = Path.home() / "nott_h2rg_fits" / "staging"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _cache_fetched_fits(self, filename: str, payload: bytes) -> Path:
        path = self._fits_staging_dir() / filename
        path.write_bytes(payload)
        return path

    def _resolve_ramp_path(self, ramp_path: Path) -> Path | None:
        return resolve_ramp_fits_path(
            ramp_path,
            search_dirs=[
                self._save_dir,
                self._fits_staging_dir(),
                self._local_science_save_dir(),
            ],
        )

    def _local_science_save_dir(self) -> Path:
        if self._local_fits_accessible(allow_probe=True):
            return self._save_dir

        configured = config.get("MACIE", "fits_directory", fallback="").strip()
        if configured:
            path = Path(os.path.expanduser(configured))
            try:
                path.mkdir(parents=True, exist_ok=True)
                return path
            except OSError:
                pass

        fallback = Path.home() / "nott_h2rg_fits"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def _science_output_path(self, ramp_path: Path) -> Path:
        return science_fits_path(self._local_science_save_dir() / ramp_path.name)

    def _save_science_fits(
        self, frame: numpy.ndarray, ramp_path: Path | None
    ) -> Path | None:
        if not MACIE_SAVE_SCIENCE_FITS or ramp_path is None:
            return None
        output_path = self._science_output_path(ramp_path)
        try:
            save_science_fits(
                output_path,
                frame,
                source_header=self._raw_fits_header,
                tint_ms=self._last_tint_ms,
                reduction=self._selected_ramp_mode(),  # type: ignore[arg-type]
                fowler_pairs=self._fowler_pairs_value(),
            )
            return output_path
        except OSError as exc:
            print(f"H2RG failed to save science FITS: {exc}")
            return None

    def _save_science_fits_from_ramp(self, ramp_path: Path) -> Path | None:
        if not MACIE_SAVE_SCIENCE_FITS:
            return None
        resolved = self._resolve_ramp_path(ramp_path)
        if resolved is None:
            print(
                f"H2RG failed to load ramp for science save {ramp_path.name}: "
                "file not found locally (check SMB mapping or ZMQ fetch)"
            )
            return None
        try:
            data, header = load_fits_data(resolved)
        except Exception as exc:
            print(f"H2RG failed to load ramp for science save {ramp_path.name}: {exc}")
            return None
        frame = science_image_from_cube(
            data,
            header,
            reduction=self._selected_ramp_mode(),  # type: ignore[arg-type]
            fowler_pairs=self._fowler_pairs_value(),
        )
        output_path = self._science_output_path(ramp_path)
        try:
            save_science_fits(
                output_path,
                frame,
                source_header=header,
                tint_ms=self._last_tint_ms,
                reduction=self._selected_ramp_mode(),  # type: ignore[arg-type]
                fowler_pairs=self._fowler_pairs_value(),
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
        if mapped is None:
            return
        try:
            if mapped.is_dir():
                self._save_dir = mapped
        except OSError:
            pass

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
        self,
        path: Path | None,
        before_mtime: float,
        *,
        before_name: str | None = None,
    ) -> tuple[numpy.ndarray, Path] | None:
        if path is None:
            return None
        if is_science_fits_name(path.name):
            return None
        try:
            if not path.is_file():
                return None
            mtime = path.stat().st_mtime
        except OSError:
            return None
        if not is_new_ramp_fits(
            path.name,
            mtime,
            before_name=before_name,
            before_mtime=before_mtime,
        ):
            return None
        try:
            return self._load_fits_from_path(path), path
        except Exception as exc:
            print(f"H2RG skipped unreadable FITS {path.name}: {exc}")
            return None

    def _resolve_server_fits_path(self, macie) -> Path | None:
        try:
            server_path = macie.get_newest_fits_path()
        except Exception:
            return None
        if not server_path:
            return None
        mapped = map_server_fits_path(server_path)
        if mapped is not None and is_science_fits_name(mapped.name):
            return None
        return mapped

    def _server_fits_is_new(
        self,
        macie,
        *,
        before_name: str | None,
        before_mtime: float,
    ) -> bool:
        try:
            server_path = macie.get_newest_fits_path()
        except Exception:
            return False
        if not server_path:
            return False
        name = fits_basename(server_path)
        if not name or is_science_fits_name(name):
            return False
        if before_name and name == before_name:
            return False
        mapped = map_server_fits_path(server_path)
        if mapped is not None:
            try:
                mtime = mapped.stat().st_mtime
            except OSError:
                mtime = before_mtime
            return is_new_ramp_fits(
                name,
                mtime,
                before_name=before_name,
                before_mtime=before_mtime,
            )
        return bool(before_name and name != before_name)

    def _fetch_fits_from_server(
        self,
        macie,
        *,
        before_mtime: float = 0.0,
        before_name: str | None = None,
        require_new: bool = True,
    ) -> tuple[numpy.ndarray, Path] | None:
        if require_new and not self._server_fits_is_new(
            macie,
            before_name=before_name,
            before_mtime=before_mtime,
        ):
            return None
        try:
            fetched = macie.fetch_newest_fits()
        except Exception as exc:
            print(f"H2RG FITS fetch over ZMQ failed: {exc}")
            return None
        if fetched is None:
            return None
        filename, payload = fetched
        if is_science_fits_name(filename):
            return None
        if require_new and before_name and filename == before_name:
            return None
        path = self._cache_fetched_fits(filename, payload)
        try:
            frame = self._load_fits_from_bytes(payload, path)
        except Exception as exc:
            print(f"H2RG failed to decode FITS {filename}: {exc}")
            return None
        self._last_fits_path = path
        self._last_loaded_basename = path.name
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
            self._stop_live_ui()
            self._set_status("Live stopped")
            return

        self._set_status("Starting live acquisition…")

        def worker() -> None:
            try:
                self._apply_exposure_settings(self._macie)
                self._macie.start_continuous_acquisition()
                QTimer.singleShot(0, self._activate_live_ui)
                self.status_updated.emit("Live acquiring…")
            except Exception as exc:
                self.live_acquisition_failed.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def halt(self) -> None:
        if self._live_active and self._macie is not None:
            self._macie.stop_continuous_acquisition()
            self._stop_live_ui()

        if self._macie is not None:
            self._run_macie_operation("Halt", self._macie.halt_acquisition)
        self._set_status("Halted")

    def take_background(self) -> None:
        frame = self._frame_from_display_mode()
        if frame is None:
            loaded = self._load_latest_frame()
            if loaded is None:
                self._on_operation_failed("No FITS frame available for background")
                return
            frame, _path = loaded
            frame = self._frame_from_display_mode() or frame
        self._background = numpy.asarray(frame, dtype=numpy.float32).copy()
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
                "tint_unavailable": tint_s is None,
            }
        )

    def _apply_readouts(self, data: dict) -> None:
        combo = self.ui.comboBox_detector_mode
        combo.blockSignals(True)
        combo.setCurrentIndex(data["mode_index"])
        combo.blockSignals(False)
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
        elif data.get("tint_unavailable"):
            self._set_status(
                "Could not read integration time from detector — "
                "enter a value and press Set"
            )
        self._update_total_integration_label()

    def _update_total_integration_label(self, actual_tint_ms: float | None = None) -> None:
        try:
            per_frame = actual_tint_ms
            if per_frame is None and self._selected_ramp_mode() == "Fowler":
                per_frame = self._last_tint_ms
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

    def _collect_new_ramp_paths(
        self,
        before_mtime: float,
        *,
        before_name: str | None,
    ) -> list[Path]:
        if not self._local_fits_accessible(allow_probe=True):
            return []
        return list_new_ramp_fits_in_dir(
            self._save_dir,
            before_mtime=before_mtime,
            before_name=before_name,
            dir_ok=True,
        )

    def _wait_for_acquire_frames(
        self,
        before_mtime: float,
        macie,
        *,
        before_name: str | None = None,
        expected_count: int = 1,
        timeout_s: float = 30.0,
    ) -> tuple[list[Path], numpy.ndarray | None, Path | None]:
        import time

        self._sync_save_dir_from_server(macie)
        deadline = time.monotonic() + timeout_s
        seen: dict[str, Path] = {}
        zmq_seen: set[str] = set()
        server_path_checked_at = 0.0
        stable_since: float | None = None

        while time.monotonic() < deadline:
            for path in self._collect_new_ramp_paths(
                before_mtime, before_name=before_name
            ):
                seen[path.name] = path

            if not self._local_fits_accessible(allow_probe=True):
                now = time.monotonic()
                if now - server_path_checked_at >= 1.0:
                    server_path_checked_at = now
                    if self._server_fits_is_new(
                        macie,
                        before_name=before_name,
                        before_mtime=before_mtime,
                    ):
                        fetched = self._fetch_fits_from_server(
                            macie,
                            before_mtime=before_mtime,
                            before_name=before_name,
                            require_new=True,
                        )
                        if fetched is not None:
                            _frame, path = fetched
                            seen[path.name] = path
                            zmq_seen.add(path.name)
                            before_name = path.name
                if len(seen) >= expected_count:
                    break
            elif len(seen) >= expected_count:
                stable_since = None
                break
            elif seen:
                if stable_since is None:
                    stable_since = time.monotonic()
                elif time.monotonic() - stable_since >= 1.0:
                    break
            else:
                stable_since = None

            now = time.monotonic()
            if self._local_fits_accessible(allow_probe=True):
                if now - server_path_checked_at >= 2.0:
                    server_path_checked_at = now
                    server_path = self._resolve_server_fits_path(macie)
                    loaded = self._try_load_path_if_new(
                        server_path,
                        before_mtime,
                        before_name=before_name,
                    )
                    if loaded is not None:
                        _frame, path = loaded
                        seen[path.name] = path
            time.sleep(0.2)

        ramp_paths = sorted(
            seen.values(),
            key=lambda path: (
                path.stat().st_mtime if path.exists() else 0.0,
                path.name.lower(),
            ),
        )
        if not ramp_paths and self._local_fits_accessible(allow_probe=True):
            fetched = self._fetch_fits_from_server(
                macie,
                before_mtime=before_mtime,
                before_name=before_name,
                require_new=True,
            )
            if fetched is not None:
                _frame, path = fetched
                ramp_paths = [path]

        if not ramp_paths:
            return [], None, None

        preview_path = ramp_paths[-1]
        try:
            if preview_path.is_file():
                frame = self._load_fits_from_path(preview_path)
            else:
                loaded = self._try_load_path_if_new(
                    preview_path,
                    before_mtime,
                    before_name=before_name,
                )
                if loaded is None:
                    fetched = self._fetch_fits_from_server(
                        macie,
                        before_mtime=before_mtime,
                        before_name=before_name,
                        require_new=False,
                    )
                    if fetched is None:
                        return ramp_paths, None, preview_path
                    frame, preview_path = fetched
                else:
                    frame, preview_path = loaded
        except Exception as exc:
            print(f"H2RG failed to load preview ramp {preview_path.name}: {exc}")
            return ramp_paths, None, preview_path

        return ramp_paths, frame, preview_path

    def _wait_for_new_frame(
        self,
        before_mtime: float,
        macie,
        *,
        before_name: str | None = None,
        timeout_s: float = 30.0,
    ) -> tuple[numpy.ndarray | None, Path | None]:
        _paths, frame, path = self._wait_for_acquire_frames(
            before_mtime,
            macie,
            before_name=before_name,
            expected_count=1,
            timeout_s=timeout_s,
        )
        return frame, path

    def _store_raw_fits(self, data: numpy.ndarray, header: dict) -> numpy.ndarray:
        self._raw_fits_cube = numpy.asarray(data)
        self._raw_fits_header = dict(header)
        return science_image_from_cube(
            data,
            header,
            reduction=self._selected_ramp_mode(),  # type: ignore[arg-type]
            fowler_pairs=self._fowler_pairs_value(),
        )

    def _load_fits_from_path(self, path: Path) -> numpy.ndarray:
        data, header = load_fits_data(path)
        self._last_fits_path = path
        self._last_fits_mtime = path.stat().st_mtime
        self._last_loaded_basename = path.name
        self._fits_dir_ok = True
        return self._store_raw_fits(data, header)

    def _load_fits_from_bytes(self, payload: bytes, path: Path) -> numpy.ndarray:
        data, header = load_fits_data(payload)
        self._last_fits_path = path
        self._last_loaded_basename = path.name
        return self._store_raw_fits(data, header)

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
            try:
                server_path = macie.get_newest_fits_path()
            except Exception:
                return None
            server_name = fits_basename(server_path)
            if (
                not force
                and server_name
                and server_name == self._last_loaded_basename
            ):
                return None
            return self._fetch_fits_from_server(
                macie,
                require_new=not force,
            )

        path = self._newest_fits_file(allow_probe=True)
        if path is None and macie is not None:
            path = self._resolve_server_fits_path(macie)
        if path is None:
            if force and macie is not None:
                return self._fetch_fits_from_server(macie, require_new=False)
            return None
        if not force and path.name == self._last_loaded_basename:
            return None
        try:
            mtime = path.stat().st_mtime
        except OSError:
            if macie is not None:
                return self._fetch_fits_from_server(macie, require_new=not force)
            return None
        if not force and mtime == self._last_fits_mtime:
            return None
        try:
            return self._load_fits_from_path(path), path
        except OSError:
            if macie is not None:
                return self._fetch_fits_from_server(macie, require_new=not force)
            return None

    def _refresh_display(self) -> None:
        if self._current_frame is not None or self._raw_fits_cube is not None:
            self._display_frame()

    def _display_frame(self, frame: numpy.ndarray | None = None) -> None:
        self._ensure_image_view()
        if self.image is None:
            return
        if frame is not None:
            self._current_frame = frame
        self._update_central_value(self._current_frame)
        display = self._build_display_frame()
        if display is None:
            self._central_value = None
            self._sync_cursor_readout_label()
            return

        auto_levels = self._auto_levels_next
        self.image.setImage(display, autoLevels=auto_levels)
        if auto_levels:
            self._auto_levels_next = False

        self._update_image_statistics(self._stats_array(display))
        self._layout_image_frame()
        self._sync_cursor_readout_label()

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
        if self._shutting_down:
            event.accept()
            return
        self._shutting_down = True

        halt_server = self._live_active
        self._cursor_readout_timer.stop()
        self._live_poll_stop.set()
        self._stop_live_ui()

        macie = self._macie
        zmq_server = self._zmq_server
        operation_lock = self._operation_lock
        shutdown_server = (
            zmq_server is not None and zmq_server.started_by_gui
        )
        self._macie = None
        self._zmq_server = None

        self.closing.emit()
        event.accept()
        super().closeEvent(event)

        def cleanup() -> None:
            if macie is not None:
                macie.stop_continuous_acquisition()
                if operation_lock.acquire(timeout=2.0):
                    operation_lock.release()
                try:
                    macie.disconnect(
                        halt_server=halt_server or shutdown_server,
                        shutdown_server=shutdown_server,
                    )
                except Exception as exc:
                    print(f"H2RG MACIE shutdown: {exc}")
            if zmq_server is not None:
                try:
                    zmq_server.stop()
                except Exception as exc:
                    print(f"H2RG zmq_server shutdown: {exc}")

        threading.Thread(target=cleanup, name="h2rg-shutdown", daemon=True).start()
