from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from urllib.parse import urlparse

import numpy
from PyQt5.QtCore import QEvent, QPointF, QRect, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QDesktopServices, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
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
from nottcontrol.camera.macie.fits_header_meta import (
    exposure_fits_cards,
    fits_header_cards_from_redis,
    header_cards_as_value_dict,
)
from nottcontrol.camera.macie.fits_science import (
    load_fits_data,
    save_science_fits,
    science_fits_path,
    science_image_from_cube,
)
from nottcontrol.camera.macie.gui_remote import (
    DEFAULT_TIMEOUT_S as GUI_CONTROL_TIMEOUT_S,
    GuiControlServer,
)
from nottcontrol.camera.macie.h2rg_roi_panel import (
    ROI_COLORS,
    H2rgRoiPanel,
    H2rgRoiPlots,
    compute_roi_brightness,
    redis_key_for_roi,
    roi_profile_1d,
)
from nottcontrol.camera.macie.ramp_plan import RAMP_MODE_ITEMS, RAMP_MODES, fits_wait_timeout_s
from nottcontrol.redisclient import RedisClient

H2RG_SECTION = "H2RG DETECTOR"
MACIE_CONFIG_FILE = config.get(
    H2RG_SECTION, "config_file", fallback="teledyne_cold_slow.cfg"
)
MACIE_CONFIG_FILE_SLOW = config.get(
    H2RG_SECTION, "config_file_slow", fallback="teledyne_cold_slow.cfg"
)
MACIE_CONFIG_FILE_FAST = config.get(
    H2RG_SECTION, "config_file_fast", fallback="basic_fast_H2RG_cold.cfg"
)
MACIE_ZMQ_ADDRESS = config.get(
    H2RG_SECTION, "zmq_address", fallback="tcp://localhost:65534"
)
MACIE_OFFLINE_MODE = config.getboolean(H2RG_SECTION, "offline_mode", fallback=False)
MACIE_IMAGE_SCALE = config.getint(H2RG_SECTION, "image_display_scale", fallback=2)
FITS_DIR_CHECK_TIMEOUT_S = config.getfloat(
    H2RG_SECTION, "fits_directory_check_timeout_s", fallback=1.0
)
FITS_LINUX_PATH_PREFIX = config.get(
    H2RG_SECTION, "fits_linux_path_prefix", fallback=""
).strip()
FITS_WINDOWS_UNC_ROOT = config.get(
    H2RG_SECTION, "fits_windows_unc_root", fallback=""
).strip()
MACIE_INTEGRATION_NGROUPS_MAX = config.getint(
    H2RG_SECTION, "integration_ngroups_max", fallback=2
)
MACIE_FOWLER_PAIRS_DEFAULT = config.getint(
    H2RG_SECTION, "fowler_pairs_default", fallback=2
)
MACIE_SAVE_SCIENCE_FITS = config.getboolean(
    H2RG_SECTION, "save_science_fits", fallback=False
)
MACIE_DS9_EXECUTABLE = config.get(H2RG_SECTION, "ds9_executable", fallback="ds9").strip()
MACIE_FITS_WAIT_MARGIN_S = config.getfloat(
    H2RG_SECTION, "fits_wait_margin_s", fallback=30.0
)
MACIE_RECORD_ROIS = config.getboolean(H2RG_SECTION, "record_rois", fallback=True)
MACIE_FITS_WATCH_S = config.getfloat(H2RG_SECTION, "gui_fits_watch_s", fallback=2.0)
MACIE_ROI_TIME_WINDOW_S = config.getfloat(
    H2RG_SECTION, "roi_time_plot_window_seconds", fallback=60.0
)
MACIE_ROI_PLOT_HZ = config.getfloat(H2RG_SECTION, "roi_plot_refresh_hz", fallback=1.0)
MACIE_ROI_GRAPH_HEIGHT = config.getint(H2RG_SECTION, "graph_height", fallback=240)
MACIE_ROI_TIME_PLOT_MAX_HZ = config.getfloat(
    H2RG_SECTION, "roi_time_plot_max_framerate", fallback=30.0
)
MACIE_ROI_DEQUE_LENGTH = max(
    60, int(MACIE_ROI_TIME_WINDOW_S * MACIE_ROI_TIME_PLOT_MAX_HZ)
)
MACIE_ROI_PLOT_INTERVAL_S = 1.0 / max(MACIE_ROI_PLOT_HZ, 0.1)
MACIE_SHUTTER_WAIT_TIMEOUT_S = 30.0
MACIE_SHUTTER_NODES = (
    ("ns=4;s=MAIN.nott_ics.Shutters.NSH1", "Shutter 1"),
    ("ns=4;s=MAIN.nott_ics.Shutters.NSH2", "Shutter 2"),
    ("ns=4;s=MAIN.nott_ics.Shutters.NSH3", "Shutter 3"),
    ("ns=4;s=MAIN.nott_ics.Shutters.NSH4", "Shutter 4"),
)

from nottcontrol.theme import (
    APP_MONO_FAMILY,
    CHECKBOX_STYLE,
    FONT,
    H2RG_WINDOW_STYLE,
    IMAGE_FRAME_STYLE,
    MONO_FONT,
    PANEL_BUTTON_STYLE,
    PANEL_FIELD_STYLE,
    PANEL_GROUP_STYLE,
    PANEL_LABEL_STYLE,
    linux_safe_stylesheet,
    sanitize_widget_fonts,
    style_line_edit_field,
)

_MACIE_UI = Path(__file__).resolve().parent / "ui" / "MacieControl.ui"
RIGHT_PANEL_WIDTH = 360
CURSOR_READOUT_HEIGHT = 28
CURSOR_READOUT_INTERVAL_MS = 50
H2RG_ARRAY_SIZE = 2048
H2RG_NUM_CHANNELS = 32
CAMERA_SQUARE_MIN = 420


class _SquareCameraHost(QWidget):
    """Host that keeps its child camera frame square and centered.

    Optional *bottom* widget (e.g. pixel readout) is centered under the frame
    and kept the same width as the square image.
    """

    def __init__(
        self,
        camera: QWidget,
        bottom: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._camera = camera
        self._bottom = bottom
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(CAMERA_SQUARE_MIN, CAMERA_SQUARE_MIN)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6 if bottom is not None else 0)
        layout.addStretch(1)
        layout.addWidget(camera, alignment=Qt.AlignHCenter)
        if bottom is not None:
            layout.addWidget(bottom, alignment=Qt.AlignHCenter)
        layout.addStretch(1)

    def _bottom_height(self) -> int:
        if self._bottom is None:
            return 0
        spacing = self.layout().spacing() if self.layout() is not None else 0
        return spacing + max(self._bottom.sizeHint().height(), CURSOR_READOUT_HEIGHT)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return max(CAMERA_SQUARE_MIN, width) + self._bottom_height()

    def sizeHint(self) -> QSize:
        side = 640
        return QSize(side, side + self._bottom_height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        extra = self._bottom_height()
        available_h = max(CAMERA_SQUARE_MIN, self.height() - extra)
        side = max(CAMERA_SQUARE_MIN, min(self.width(), available_h))
        self._camera.setFixedSize(side, side)
        if self._bottom is not None:
            self._bottom.setFixedWidth(side)


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
    """Full-width central rows (Y window) for SC burst stripe.

    For a 1024-row stripe on a 2048 array this is y=[512, 1535].
    Applied via soft-tracked burst counters (ASIC Y stays full-frame).
    """
    y0 = (array_size - height) // 2
    return 0, array_size - 1, y0, y0 + height - 1


def _bottom_vertical_stripe(
    height: int, array_size: int = H2RG_ARRAY_SIZE
) -> tuple[int, int, int, int]:
    """Full-width bottom-aligned rows (edge burst path).

    Prefer `_centered_vertical_stripe` for SC presets; this remains for tests
    and any explicit bottom ROI.
    """
    if height < 1 or height > array_size:
        raise ValueError(f"height must be in 1..{array_size}, got {height}")
    return 0, array_size - 1, 0, height - 1


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


def _use_pixmap_image_backend() -> bool:
    """QGraphicsView/ImageView paint often segfaults under Linux VNC/remote X."""
    return sys.platform.startswith("linux")


class _PixmapImageView(QLabel):
    """Software frame display that avoids QGraphicsScene (safe under VNC).

    Supports mouse-wheel zoom, left-drag pan, and interactive ROI move/resize.
    """

    roiGeometryChanged = pyqtSignal(int, int, int, int, int)  # index, x, y, w, h

    _ZOOM_MIN = 1.0
    _ZOOM_MAX = 32.0
    _ZOOM_STEP = 1.25
    _ROI_HANDLE_IMG_PX = 8
    _ROI_PEN_PX = 1
    _ROI_HANDLE_DISP_PX = 5

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background: #1a1a2e;")
        self.image: numpy.ndarray | None = None
        self._levels: tuple[float, float] = (0.0, 1.0)
        self._roi_rects: dict[int, tuple[int, int, int, int]] = {}
        self._roi_visible: set[int] = set()
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._panning = False
        self._pan_last = None
        self._source_pix: QPixmap | None = None
        # ROI interaction: {"mode": "move"|"resize", "index", "origin", "geom"}
        self._roi_drag: dict | None = None

    def getImageItem(self):
        return self

    def getView(self):
        return self

    def setMouseEnabled(self, x: bool = True, y: bool = True) -> None:
        return None

    def setAspectLocked(self, locked: bool = True) -> None:
        return None

    def setAntialiasing(self, enabled: bool = False) -> None:
        return None

    def getLevels(self) -> tuple[float, float]:
        return self._levels

    def setLevels(self, *args) -> None:
        if len(args) == 1 and isinstance(args[0], (tuple, list)):
            vmin, vmax = args[0][0], args[0][1]
        else:
            vmin, vmax = args[0], args[1]
        self._levels = (float(vmin), float(vmax))
        self._rebuild_pixmap()

    def setImage(
        self,
        data: numpy.ndarray,
        autoLevels: bool = True,
        levels=None,
    ) -> None:
        arr = numpy.asarray(data)
        if arr.ndim > 2:
            arr = arr[..., 0]
        self.image = numpy.ascontiguousarray(arr)
        if autoLevels:
            finite = self.image[numpy.isfinite(self.image)]
            if finite.size:
                vmin = float(numpy.min(finite))
                vmax = float(numpy.max(finite))
                if vmin >= vmax:
                    vmax = vmin + 1.0
                self._levels = (vmin, vmax)
        elif levels is not None:
            self._levels = (float(levels[0]), float(levels[1]))
        self._rebuild_pixmap()

    def set_roi_overlays(
        self,
        rects: dict[int, tuple[int, int, int, int]],
        visible: set[int],
    ) -> None:
        self._roi_rects = dict(rects)
        self._roi_visible = set(visible)
        self._rebuild_pixmap()

    def reset_view(self) -> None:
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._rebuild_pixmap()

    def _fit_scale(self, img_w: int, img_h: int) -> float:
        tw = max(1, self.width())
        th = max(1, self.height())
        return min(tw / max(img_w, 1), th / max(img_h, 1))

    def _clamp_pan(self, disp_w: int, disp_h: int) -> None:
        tw = max(1, self.width())
        th = max(1, self.height())
        max_x = max(0.0, (disp_w - tw) / 2.0)
        max_y = max(0.0, (disp_h - th) / 2.0)
        self._pan_x = float(numpy.clip(self._pan_x, -max_x, max_x))
        self._pan_y = float(numpy.clip(self._pan_y, -max_y, max_y))
        if self._zoom <= 1.0 + 1e-6:
            self._pan_x = 0.0
            self._pan_y = 0.0

    def _visible_origin(self, disp_w: int, disp_h: int) -> tuple[int, int]:
        tw = max(1, self.width())
        th = max(1, self.height())
        self._clamp_pan(disp_w, disp_h)
        ox = int(round((disp_w - tw) / 2.0 + self._pan_x))
        oy = int(round((disp_h - th) / 2.0 + self._pan_y))
        ox = int(numpy.clip(ox, 0, max(0, disp_w - tw)))
        oy = int(numpy.clip(oy, 0, max(0, disp_h - th)))
        return ox, oy

    def widget_pos_to_image_xy(self, pos) -> tuple[int, int] | None:
        if self.image is None or self._source_pix is None or self._source_pix.isNull():
            return None
        if hasattr(pos, "x"):
            px, py = float(pos.x()), float(pos.y())
        else:
            px, py = float(pos[0]), float(pos[1])
        img_h, img_w = self.image.shape[:2]
        disp_w = self._source_pix.width()
        disp_h = self._source_pix.height()
        tw = max(1, self.width())
        th = max(1, self.height())
        ox, oy = self._visible_origin(disp_w, disp_h)
        # Letterbox when zoomed-out pixmap is smaller than the widget.
        pad_x = max(0, (tw - disp_w) // 2)
        pad_y = max(0, (th - disp_h) // 2)
        x = px - pad_x + ox
        y = py - pad_y + oy
        if x < 0 or y < 0 or x >= disp_w or y >= disp_h:
            return None
        ix = int(x * img_w / max(disp_w, 1))
        iy = int(y * img_h / max(disp_h, 1))
        if ix < 0 or iy < 0 or ix >= img_w or iy >= img_h:
            return None
        return ix, iy

    def _hit_test_roi(self, ix: int, iy: int) -> tuple[int | None, str | None]:
        """Return (roi_index, 'move'|'resize') for the topmost visible ROI under the point."""
        handle = max(4, int(round(self._ROI_HANDLE_IMG_PX / max(self._zoom, 1.0))))
        for index in sorted(self._roi_visible, reverse=True):
            geom = self._roi_rects.get(index)
            if geom is None:
                continue
            x, y, w, h = geom
            if not (x <= ix < x + w and y <= iy < y + h):
                continue
            if ix >= x + w - handle and iy >= y + h - handle:
                return index, "resize"
            return index, "move"
        return None, None

    def _clamp_roi_geom(
        self, x: int, y: int, w: int, h: int
    ) -> tuple[int, int, int, int]:
        if self.image is None:
            return x, y, max(1, w), max(1, h)
        img_h, img_w = self.image.shape[:2]
        w = max(1, min(w, img_w))
        h = max(1, min(h, img_h))
        x = int(numpy.clip(x, 0, img_w - w))
        y = int(numpy.clip(y, 0, img_h - h))
        return x, y, w, h

    def _apply_roi_drag(self, ix: int, iy: int) -> None:
        drag = self._roi_drag
        if drag is None:
            return
        index = drag["index"]
        ox, oy = drag["origin"]
        sx, sy, sw, sh = drag["geom"]
        dx = ix - ox
        dy = iy - oy
        if drag["mode"] == "resize":
            x, y, w, h = self._clamp_roi_geom(sx, sy, sw + dx, sh + dy)
        else:
            x, y, w, h = self._clamp_roi_geom(sx + dx, sy + dy, sw, sh)
        self._roi_rects[index] = (x, y, w, h)
        self._rebuild_pixmap()

    def _finish_roi_drag(self) -> None:
        drag = self._roi_drag
        self._roi_drag = None
        self.unsetCursor()
        if drag is None:
            return
        index = drag["index"]
        geom = self._roi_rects.get(index)
        if geom is None:
            return
        x, y, w, h = geom
        if (x, y, w, h) != drag["geom"]:
            self.roiGeometryChanged.emit(index, x, y, w, h)

    def wheelEvent(self, event) -> None:
        if self.image is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y()
        if delta == 0:
            return
        factor = self._ZOOM_STEP if delta > 0 else 1.0 / self._ZOOM_STEP
        old_zoom = self._zoom
        new_zoom = float(numpy.clip(old_zoom * factor, self._ZOOM_MIN, self._ZOOM_MAX))
        if abs(new_zoom - old_zoom) < 1e-9:
            event.accept()
            return

        # Keep the image point under the cursor stable while zooming.
        before = self.widget_pos_to_image_xy(event.pos())
        self._zoom = new_zoom
        self._rebuild_pixmap()
        if before is not None:
            after = self.widget_pos_to_image_xy(event.pos())
            if after is not None and self._source_pix is not None:
                img_h, img_w = self.image.shape[:2]
                disp_w = self._source_pix.width()
                disp_h = self._source_pix.height()
                sx = disp_w / max(img_w, 1)
                sy = disp_h / max(img_h, 1)
                self._pan_x += (before[0] - after[0]) * sx
                self._pan_y += (before[1] - after[1]) * sy
                self._rebuild_pixmap()
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            xy = self.widget_pos_to_image_xy(event.pos())
            if xy is not None:
                index, mode = self._hit_test_roi(xy[0], xy[1])
                if index is not None and mode is not None:
                    geom = self._roi_rects.get(index)
                    if geom is not None:
                        self._roi_drag = {
                            "mode": mode,
                            "index": index,
                            "origin": xy,
                            "geom": geom,
                        }
                        self.setCursor(
                            Qt.SizeFDiagCursor if mode == "resize" else Qt.SizeAllCursor
                        )
                        event.accept()
                        return
            if self._zoom > 1.0 + 1e-6:
                self._panning = True
                self._pan_last = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._roi_drag is not None:
            xy = self.widget_pos_to_image_xy(event.pos())
            if xy is not None:
                self._apply_roi_drag(xy[0], xy[1])
            event.accept()
            return
        if self._panning and self._pan_last is not None:
            dx = event.pos().x() - self._pan_last.x()
            dy = event.pos().y() - self._pan_last.y()
            self._pan_last = event.pos()
            # Dragging the image with the mouse (grab-hand feel).
            self._pan_x -= float(dx)
            self._pan_y -= float(dy)
            self._rebuild_pixmap()
            event.accept()
            return
        # Hover cursor over ROI / resize handle.
        xy = self.widget_pos_to_image_xy(event.pos())
        if xy is not None:
            _index, mode = self._hit_test_roi(xy[0], xy[1])
            if mode == "resize":
                self.setCursor(Qt.SizeFDiagCursor)
            elif mode == "move":
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.unsetCursor()
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._roi_drag is not None:
            self._finish_roi_drag()
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._panning:
            self._panning = False
            self._pan_last = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.reset_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rebuild_pixmap()

    def _rebuild_pixmap(self) -> None:
        if self.image is None:
            return
        img = self.image
        h, w = img.shape[:2]
        vmin, vmax = self._levels
        scale = 255.0 / max(vmax - vmin, 1e-12)
        gray = numpy.clip((img - vmin) * scale, 0, 255)
        gray = numpy.nan_to_num(gray, nan=0.0, posinf=255.0, neginf=0.0)
        gray8 = numpy.ascontiguousarray(gray.astype(numpy.uint8))
        qimg = QImage(gray8.data, w, h, w, QImage.Format_Grayscale8).copy()
        base = QPixmap.fromImage(qimg)

        tw = max(1, self.width())
        th = max(1, self.height())
        fit = self._fit_scale(w, h)
        zoom = max(self._ZOOM_MIN, float(self._zoom))
        disp_w = max(1, int(round(w * fit * zoom)))
        disp_h = max(1, int(round(h * fit * zoom)))
        source = base.scaled(disp_w, disp_h, Qt.IgnoreAspectRatio, Qt.FastTransformation)

        if self._roi_rects and self._roi_visible:
            painter = QPainter(source)
            try:
                sx = source.width() / max(w, 1)
                sy = source.height() / max(h, 1)
                for index, (rx, ry, rw, rh) in self._roi_rects.items():
                    if index not in self._roi_visible:
                        continue
                    color = QColor(ROI_COLORS[(index - 1) % len(ROI_COLORS)])
                    painter.setPen(QPen(color, self._ROI_PEN_PX))
                    rx_s = int(rx * sx)
                    ry_s = int(ry * sy)
                    rw_s = max(1, int(rw * sx))
                    rh_s = max(1, int(rh * sy))
                    painter.drawRect(rx_s, ry_s, rw_s, rh_s)
                    # SE resize handle (screen pixels; keep small and readable).
                    handle = self._ROI_HANDLE_DISP_PX
                    painter.fillRect(
                        rx_s + rw_s - handle,
                        ry_s + rh_s - handle,
                        handle,
                        handle,
                        color,
                    )
            finally:
                painter.end()

        self._source_pix = source
        ox, oy = self._visible_origin(source.width(), source.height())
        if source.width() <= tw and source.height() <= th:
            # Fit / letterbox: show the whole scaled image centered.
            canvas = QPixmap(tw, th)
            canvas.fill(QColor(0x1A, 0x1A, 0x2E))
            painter = QPainter(canvas)
            try:
                painter.drawPixmap((tw - source.width()) // 2, (th - source.height()) // 2, source)
            finally:
                painter.end()
            self.setPixmap(canvas)
            return

        crop_w = min(tw, source.width())
        crop_h = min(th, source.height())
        self.setPixmap(source.copy(QRect(ox, oy, crop_w, crop_h)))


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
        editor.setFontFamily(APP_MONO_FAMILY)
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
    """Return the WINDOW_MODES index matching the programmed geometry, or -1."""
    exact = -1
    sc_fallback = -1
    ny = y2 - y1 + 1
    nx = x2 - x1 + 1
    full = H2RG_ARRAY_SIZE - 1
    for index, mode in enumerate(WINDOW_MODES):
        if (mode.x_window, mode.y_window) != (x_window, y_window):
            continue
        if not mode.x_window and not mode.y_window:
            return index
        if (
            mode.x1,
            mode.x2,
            mode.y1,
            mode.y2,
        ) == (x1, x2, y1, y2):
            exact = index
            break
        # SC presets: full-width vertical stripe matched by height when the ASIC
        # reports a slightly different y1 (e.g. ref-row offset in stripe mode).
        if (
            not mode.x_window
            and mode.y_window
            and not x_window
            and y_window
            and mode.x1 == 0
            and mode.x2 == full
            and x1 == 0
            and x2 == full
            and (mode.y2 - mode.y1 + 1) == ny
            and sc_fallback < 0
        ):
            sc_fallback = index
        # Centered XY windows matched by size when origin is close.
        if (
            mode.x_window
            and mode.y_window
            and x_window
            and y_window
            and (mode.x2 - mode.x1 + 1) == nx
            and (mode.y2 - mode.y1 + 1) == ny
            and abs(mode.x1 - x1) <= 4
            and abs(mode.y1 - y1) <= 4
            and sc_fallback < 0
        ):
            sc_fallback = index
    if exact >= 0:
        return exact
    return sc_fallback


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


def _looks_like_windows_unc(path: str) -> bool:
    """True for \\\\server\\share or //server/share style paths."""
    normalized = path.strip()
    if normalized.startswith("\\\\") or normalized.startswith("//"):
        return True
    # config.ini often stores a single leading backslash before the server name
    if normalized.startswith("\\") and not normalized.startswith("\\/"):
        return True
    return False


def resolve_fits_save_dir(config_path: Path) -> Path:
    configured = config.get(H2RG_SECTION, "fits_directory", fallback="").strip()
    # On Linux/macOS, never use the Windows SMB path from config.ini as a local
    # directory — it becomes a relative junk path under the process cwd.
    if configured and not (
        sys.platform != "win32" and _looks_like_windows_unc(configured)
    ):
        return Path(os.path.expanduser(configured))
    return parse_macie_save_dir(config_path)


def zmq_server_hostname(zmq_address: str) -> str | None:
    normalized = zmq_address if "://" in zmq_address else f"tcp://{zmq_address}"
    return urlparse(normalized).hostname


def map_server_fits_path(server_path: str, zmq_address: str = MACIE_ZMQ_ADDRESS) -> Path | None:
    """Map a Linux server FITS path to a local path when configured.

    On Linux/macOS, absolute server paths are returned unchanged (e.g. /data/nott).
    On Windows, optional UNC mapping is applied; without mapping, returns None so
    callers fall back to ZMQ fetch instead of inventing invalid UNC paths.
    """
    normalized = server_path.replace("\\", "/").strip()
    if not normalized:
        return None

    if sys.platform != "win32":
        if normalized.startswith("/"):
            return Path(normalized)
        return Path(server_path)

    if FITS_LINUX_PATH_PREFIX and FITS_WINDOWS_UNC_ROOT:
        prefix = FITS_LINUX_PATH_PREFIX.replace("\\", "/").rstrip("/")
        if normalized.startswith(prefix):
            suffix = normalized[len(prefix) :].lstrip("/")
            unc_root = FITS_WINDOWS_UNC_ROOT.rstrip("\\/")
            return Path(unc_root) / PureWindowsPath(suffix.replace("/", "\\"))

    if normalized.startswith("/"):
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


def fits_frame_number_label(name: str | None) -> str:
    """Return the ramp index from a FITS basename (e.g. 000018)."""
    if not name:
        return "—"
    stem = Path(name).stem
    if stem.lower().endswith("_science"):
        stem = stem[: -len("_science")]
    if stem.lower() == "preview":
        return "—"
    # Names look like nott_YYYYMMDD_000018
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[1]
    return stem


def next_fits_frame_number(
    directory: Path, *, dir_ok: bool | None = None, width: int = 6
) -> str:
    """Return the next free ramp index in *directory* (matches MACIE getFileNumStart)."""
    max_index = -1
    for path in list_ramp_fits_in_dir(directory, dir_ok=dir_ok):
        label = fits_frame_number_label(path.name)
        if label.isdigit():
            max_index = max(max_index, int(label))
    return f"{max_index + 1:0{width}d}"


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
            values = config.getarray(H2RG_SECTION, key, dtype=int)
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
    # Same basename can still be new when MACIE overwrites or SMB reuses a name
    # with a newer mtime (previously this returned False and the GUI spun forever).
    if before_name and name == before_name:
        return mtime > before_mtime
    if mtime > before_mtime:
        return True
    # Same-second filesystem resolution: accept a different basename only when
    # mtime is not older. Never treat an older file as new — that caused Live
    # to flip forever between the latest ramp and the previous one.
    if mtime < before_mtime:
        return False
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
        if not is_science_fits_name(path.name) and path.name.lower() != "preview.fits"
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
    # Multi-frame Acquire: emit each ramp as it is written (Queued → GUI paint).
    acquire_preview_frame = pyqtSignal(object, str)
    operation_failed = pyqtSignal(str)
    live_acquisition_failed = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    controls_enabled = pyqtSignal(bool)
    readouts_updated = pyqtSignal(object)
    init_button_state = pyqtSignal(str)
    exposure_timing_updated = pyqtSignal(object)
    integration_time_updated = pyqtSignal(str)
    macie_operation_busy = pyqtSignal(bool)
    remote_acquire_requested = pyqtSignal()
    remote_load_newest_requested = pyqtSignal()
    background_ready = pyqtSignal()

    def __init__(self, opcua_conn=None) -> None:
        super().__init__()
        self.setWindowTitle("H2RG / MACIE")
        app_icon = load_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        self.setMinimumSize(1100, 920)
        self.ui = None
        self._opcua_conn = opcua_conn
        self._shutters = None
        self._init_runtime_state()

        self.frame_ready.connect(self._display_frame, Qt.QueuedConnection)
        self.acquire_preview_frame.connect(
            self._display_acquire_preview, Qt.QueuedConnection
        )
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
        self.integration_time_updated.connect(
            self._apply_integration_time_text, Qt.QueuedConnection
        )
        self.macie_operation_busy.connect(
            self._apply_macie_operation_busy, Qt.QueuedConnection
        )
        self.remote_acquire_requested.connect(
            self._on_remote_acquire, Qt.QueuedConnection
        )
        self.remote_load_newest_requested.connect(
            self._on_remote_load_newest, Qt.QueuedConnection
        )
        self.background_ready.connect(self._on_background_ready, Qt.QueuedConnection)

        loading = QLabel("Loading H2RG controls…", self)
        loading.setAlignment(Qt.AlignCenter)
        loading.setStyleSheet(
            linux_safe_stylesheet(
                f'font: 13pt {FONT}; color: rgb(100, 100, 100); background: rgb(245, 248, 249);'
            )
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
        self._roi_panel: H2rgRoiPanel | None = None
        self._roi_plots: H2rgRoiPlots | None = None
        self._last_roi_profiles: dict[int, numpy.ndarray] | None = None
        self._last_roi_plot_refresh = 0.0
        self._redis: RedisClient | None = None
        try:
            self._redis = RedisClient(config["DEFAULT"]["databaseurl"])
        except Exception as exc:
            print(f"H2RG Redis client unavailable: {exc}")
        self._live_poll_stop = threading.Event()
        self._live_frame_available = threading.Event()
        self._live_pending_frame: numpy.ndarray | None = None
        self._frame_timing_t0: float | None = None
        self._frame_timing_label = "Acquire"
        self._frame_timing_skip_report = False
        self._frame_timing_status: str | None = None
        self._operation_lock = threading.Lock()
        self._zmq_server = None
        self._zmq_address: str | None = None
        self._shutting_down = False
        self._last_tint_ms: float | None = None
        self._last_exposure_report: dict[str, float | int | str] | None = None
        self._initialized = False
        self._macie_operation_busy = False
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
        self._button_autoscale: QPushButton | None = None
        self._button_header: QPushButton | None = None
        self._button_ds9: QPushButton | None = None
        self._button_save_dir: QPushButton | None = None
        self._checkBox_save_image: QCheckBox | None = None
        self._checkBox_autoscale: QCheckBox | None = None
        self._button_apply_levels: QPushButton | None = None
        self._lineEdit_level_min: QLineEdit | None = None
        self._lineEdit_level_max: QLineEdit | None = None
        self._manual_levels: tuple[float, float] | None = None
        self._acquire_previewed_names: set[str] = set()
        self._acquire_preview_lock = threading.Lock()
        self._acquire_preview_reduction = "CDS"
        self._acquire_preview_fowler = 2
        self._pending_roi_display: numpy.ndarray | None = None
        self._cached_files_today: int | None = None
        self._pending_roi_record = False
        self._applied_exposure_fingerprint: tuple | None = None
        self._roi_update_timer = QTimer(self)
        self._roi_update_timer.setSingleShot(True)
        self._roi_update_timer.timeout.connect(self._flush_pending_roi_update)
        self._exposure_preview_timer = QTimer(self)
        self._exposure_preview_timer.setSingleShot(True)
        self._exposure_preview_timer.setInterval(450)
        self._exposure_preview_timer.timeout.connect(
            self._schedule_exposure_timing_preview
        )
        self._gui_control: GuiControlServer | None = None
        self._fits_watch_timer: QTimer | None = None
        self._pending_remote_acquire_done: threading.Event | None = None
        self._pending_remote_load: tuple[dict, threading.Event] | None = None
        self._remote_op_error: str | None = None

    def _stage_load_ui(self) -> None:
        QApplication.processEvents()
        self.ui = loadUi(str(_MACIE_UI))
        self.setCentralWidget(self.ui)
        QTimer.singleShot(0, self._stage_connect_ui)

    def _stage_connect_ui(self) -> None:
        QApplication.processEvents()
        self._set_status("Loading…")
        self._set_controls_enabled(False)
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
            self._button_apply_levels.clicked.connect(self._apply_manual_levels)
            self._lineEdit_level_min.editingFinished.connect(self._apply_manual_levels)
            self._lineEdit_level_max.editingFinished.connect(self._apply_manual_levels)
            if self._checkBox_autoscale is not None:
                self._checkBox_autoscale.toggled.connect(self._on_autoscale_toggled)
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
            self._start_gui_services()
            threading.Thread(target=self._background_startup, daemon=True).start()
        except Exception as exc:
            print(f"H2RG GUI setup failed: {exc}")
            self._set_status(f"GUI setup failed: {exc}")

    def _start_gui_services(self) -> None:
        """Local control socket + optional FITS directory watcher."""
        self._gui_control = GuiControlServer(
            on_acquire=self._remote_acquire_handler,
            on_load_newest=self._remote_load_newest_handler,
            on_status=self._remote_status_handler,
        )
        try:
            self._gui_control.start()
            print(f"H2RG GUI control listening on {self._gui_control.endpoint}")
        except OSError as exc:
            print(f"H2RG GUI control socket not started: {exc}")
            self._gui_control = None

        if MACIE_FITS_WATCH_S > 0:
            self._fits_watch_timer = QTimer(self)
            self._fits_watch_timer.setInterval(max(200, int(MACIE_FITS_WATCH_S * 1000)))
            self._fits_watch_timer.timeout.connect(self._poll_new_fits)
            self._fits_watch_timer.start()

    def _stop_gui_services(self) -> None:
        if self._fits_watch_timer is not None:
            self._fits_watch_timer.stop()
            self._fits_watch_timer = None
        if self._gui_control is not None:
            self._gui_control.stop()
            self._gui_control = None

    def _remote_status_handler(self) -> str:
        return (
            "ok;"
            f"initialized={int(self._initialized)};"
            f"busy={int(self._macie_operation_busy)};"
            f"live={int(self._live_active)}"
        )

    def _remote_acquire_handler(self) -> str:
        if self._shutting_down:
            return "nok;shutting_down"
        if not self._initialized:
            return "nok;not_initialized"
        if self._live_active:
            return "nok;live_active"
        if self._macie_operation_busy:
            return "nok;busy"
        done = threading.Event()
        self._remote_op_error = None
        self._pending_remote_acquire_done = done
        self.remote_acquire_requested.emit()
        if not done.wait(timeout=GUI_CONTROL_TIMEOUT_S):
            return "nok;timeout"
        if self._remote_op_error:
            return f"nok;{self._remote_op_error}"
        return "ok;acquire_done"

    def _on_remote_acquire(self) -> None:
        done = self._pending_remote_acquire_done
        self._pending_remote_acquire_done = None
        try:
            if self._live_active:
                self._remote_op_error = "live_active"
                self._on_operation_failed("Stop live mode before acquiring")
                return
            if self._macie_operation_busy:
                self._remote_op_error = "busy"
                return
            self.acquire(done_event=done)
            done = None
        finally:
            if done is not None:
                done.set()

    def _remote_load_newest_handler(self) -> str:
        if self._shutting_down:
            return "nok;shutting_down"
        holder: dict[str, str] = {"reply": "nok;internal"}
        done = threading.Event()
        self._pending_remote_load = (holder, done)
        self.remote_load_newest_requested.emit()
        if not done.wait(timeout=60.0):
            return "nok;timeout"
        return holder.get("reply", "nok;internal")

    def _on_remote_load_newest(self) -> None:
        pending = self._pending_remote_load
        self._pending_remote_load = None
        if pending is None:
            return
        holder, done = pending
        try:
            loaded = self._load_latest_frame(force=True, macie=self._macie)
            if loaded is None:
                holder["reply"] = "nok;no_fits"
                return
            frame, path = loaded
            self._last_fits_path = path
            self._frame_timing_skip_report = True
            self.frame_ready.emit(frame)
            self.status_updated.emit(f"Loaded {path.name}")
            holder["reply"] = f"ok;{path.name}"
        except Exception as exc:  # noqa: BLE001 — surface to control client
            holder["reply"] = f"nok;{exc}"
        finally:
            done.set()

    def _poll_new_fits(self) -> None:
        """Refresh the display when a new ramp appears on disk (e.g. script ZMQ)."""
        if self._shutting_down or not self._initialized:
            return
        if self._live_active or self._macie_operation_busy:
            return
        loaded = self._load_latest_frame(force=False, macie=self._macie)
        if loaded is None:
            return
        frame, path = loaded
        self._frame_timing_skip_report = True
        self.frame_ready.emit(frame)
        self.status_updated.emit(f"New FITS: {path.name}")

    def _setup_image_placeholder(self) -> None:
        host = self._ensure_camera_host_layout()
        self._clear_layout_widgets(host)
        self._image_placeholder = QLabel("No image yet", self.ui.frame_camera)
        self._image_placeholder.setAlignment(Qt.AlignCenter)
        self._image_placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._image_placeholder.setStyleSheet(
            linux_safe_stylesheet(
                f'color: rgb(200, 200, 220); font: 13pt {FONT};'
                " background: transparent;"
            )
        )
        host.addWidget(self._image_placeholder)

    def _clear_widget_layout(self, widget: QWidget) -> None:
        layout = widget.layout()
        if layout is None:
            return
        while layout.count():
            layout.takeAt(0)
        QWidget().setLayout(layout)

    def _clear_layout_widgets(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.hide()
                child.setParent(None)
                child.deleteLater()

    def _ensure_camera_host_layout(self):
        layout = self.ui.frame_camera.layout()
        if layout is None:
            layout = QVBoxLayout(self.ui.frame_camera)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.setSpacing(0)
        return layout

    def _clear_frame_camera_layout(self) -> None:
        layout = self.ui.frame_camera.layout()
        if layout is None:
            return
        self._clear_layout_widgets(layout)
        QWidget().setLayout(layout)

    def _make_image_tool_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setStyleSheet(PANEL_BUTTON_STYLE)
        button.setMinimumHeight(CURSOR_READOUT_HEIGHT)
        button.setFixedWidth(96)
        return button

    def _make_level_field(self, label_text: str) -> tuple[QWidget, QLineEdit]:
        host = QWidget()
        host.setFixedWidth(96)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        label = QLabel(label_text, host)
        label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        label.setStyleSheet(PANEL_LABEL_STYLE)
        field = QLineEdit(host)
        field.setFixedHeight(CURSOR_READOUT_HEIGHT)
        style_line_edit_field(field)
        # Right-align + QSS/margins often offsets the caret from the glyphs on
        # macOS; left-align keeps the insertion point matched to the text.
        field.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        field.setPlaceholderText("—")
        # Typing in Min/Max should lock the scale (setText does not emit textEdited).
        field.textEdited.connect(lambda _text: self._set_autoscale_checked(False))
        layout.addWidget(label)
        layout.addWidget(field)
        return host, field

    def _setup_image_tool_buttons(self) -> QWidget:
        """Tool column left of the image: buttons then Min/Max, packed at top."""
        host = QWidget()
        host.setFixedWidth(110)
        host.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        column = QVBoxLayout(host)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        column.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self._button_autoscale = self._make_image_tool_button("Autoscale")
        column.addWidget(self._button_autoscale, 0, Qt.AlignHCenter)

        self._button_apply_levels = self._make_image_tool_button("Apply")
        self._button_apply_levels.setToolTip("Apply min/max color scale")
        column.addWidget(self._button_apply_levels, 0, Qt.AlignHCenter)

        self._button_header = self._make_image_tool_button("Header")
        column.addWidget(self._button_header, 0, Qt.AlignHCenter)

        self._button_ds9 = self._make_image_tool_button("DS9")
        column.addWidget(self._button_ds9, 0, Qt.AlignHCenter)

        self._button_save_dir = self._make_image_tool_button("Folder")
        self._button_save_dir.setToolTip("Open FITS save directory")
        column.addWidget(self._button_save_dir, 0, Qt.AlignHCenter)

        min_host, self._lineEdit_level_min = self._make_level_field("Min")
        column.addWidget(min_host, 0, Qt.AlignHCenter)
        max_host, self._lineEdit_level_max = self._make_level_field("Max")
        column.addWidget(max_host, 0, Qt.AlignHCenter)

        autoscale_box = QCheckBox("Autoscale")
        autoscale_box.setChecked(True)
        autoscale_box.setToolTip(
            "When checked, the color scale tracks each frame's min/max. "
            "When unchecked, the color scale follows the Min/Max fields."
        )
        autoscale_box.setStyleSheet(CHECKBOX_STYLE)
        self._checkBox_autoscale = autoscale_box
        column.addWidget(autoscale_box, 0, Qt.AlignHCenter)

        column.addStretch(1)
        return host

    def _ensure_cursor_readout(self) -> QLabel:
        if self._cursor_readout is None:
            self._cursor_readout = QLabel("Pixel: —  CV: —")
            self._cursor_readout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._cursor_readout.setFixedHeight(CURSOR_READOUT_HEIGHT)
            self._cursor_readout.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self._cursor_readout.setStyleSheet(
                linux_safe_stylesheet(
                    f"font: 10pt {MONO_FONT};"
                    " color: rgb(50, 50, 50);"
                    " background-color: rgb(255, 255, 255);"
                    " border: 1px solid rgb(50, 129, 140);"
                    " border-radius: 4px;"
                    " padding-left: 8px;"
                )
            )
        return self._cursor_readout

    def _setup_cursor_readout_row(self, parent_layout: QVBoxLayout) -> None:
        parent_layout.addWidget(self._ensure_cursor_readout())

    def _setup_nott_logo(self, parent_layout: QVBoxLayout) -> None:
        parent_layout.addWidget(make_nott_logo_title_header("H2RG / MACIE"))

    def _setup_cursor_readout(self) -> None:
        if self.image is None or self._cursor_readout is None:
            return
        if self._cursor_readout_proxy is not None:
            return

        if isinstance(self.image, _PixmapImageView):
            self.image.setMouseTracking(True)
            self.image.installEventFilter(self)
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
        # ImageView / placeholder are managed by the frame_camera layout.
        return

    def _scene_pos_to_image_xy(self, pos) -> tuple[int, int] | None:
        if self.image is None:
            return None
        if isinstance(self.image, _PixmapImageView):
            return self.image.widget_pos_to_image_xy(pos)
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

    def eventFilter(self, obj, event) -> bool:
        if (
            self.ui is not None
            and obj is self.ui.frame_camera
            and event.type() == QEvent.Resize
        ):
            self._layout_image_frame()

        if self.image is not None and obj is self.image.getView():
            if event.type() == QEvent.MouseMove:
                if isinstance(self.image, _PixmapImageView):
                    self._update_cursor_readout_from_view_pos(event.pos())
                else:
                    view = self.image.getView()
                    self._update_cursor_readout_from_view_pos(view.mapToScene(event.pos()))
            elif event.type() == QEvent.Leave:
                self._cursor_readout_pending = None
                if self._cursor_readout is not None:
                    self._cursor_readout.setText(
                        self._format_cursor_readout_text(None, None, None)
                    )

        return super().eventFilter(obj, event)

    def _ensure_image_view(self) -> None:
        if self.image is not None:
            return

        host = self._ensure_camera_host_layout()
        self._clear_layout_widgets(host)
        self._image_placeholder = None

        if _use_pixmap_image_backend():
            self.image = _PixmapImageView(self.ui.frame_camera)
            host.addWidget(self.image)
            self.image.show()
            try:
                self._setup_cursor_readout()
            except Exception as exc:
                print(f"H2RG cursor readout setup failed: {exc}")
            self._setup_roi_overlays()
            return

        import pyqtgraph as pg

        # OpenGL under VNC/remote X often segfaults after setImage; use software path.
        pg.setConfigOptions(
            imageAxisOrder="row-major",
            useOpenGL=False,
            antialias=False,
        )
        pg.setConfigOption("background", "#1a1a2e")
        pg.setConfigOption("foreground", "w")

        self.image = pg.ImageView(self.ui.frame_camera)
        self.image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image.ui.histogram.hide()
        self.image.ui.roiBtn.hide()
        self.image.ui.menuBtn.hide()
        try:
            # Detach unused ImageView chrome so paintSiblings is shallower.
            for w in (
                self.image.ui.histogram,
                self.image.ui.roiBtn,
                self.image.ui.menuBtn,
            ):
                w.setParent(None)
        except Exception:
            pass
        try:
            self.image.getView().setAntialiasing(False)
        except Exception:
            pass
        host.addWidget(self.image)
        self.image.show()
        self.image.getView().setMouseEnabled(x=True, y=True)
        self.image.getView().setAspectLocked(True)
        try:
            self._setup_cursor_readout()
        except Exception as exc:
            print(f"H2RG cursor readout setup failed: {exc}")

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
                    f"{message} — also set [H2RG DETECTOR] fits_directory for FITS preview"
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
            combo.setMinimumContentsLength(14)
            combo.setMaximumWidth(168)
            combo.setSizePolicy(combo_policy)
        outer.addLayout(form, stretch=1)

    def _layout_acquisition_panel(self) -> None:
        box = self.ui.groupBox_acquisition
        self._clear_widget_layout(box)
        box.setMinimumHeight(0)
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        outer = QVBoxLayout(box)
        outer.setContentsMargins(8, 10, 8, 8)
        outer.setSpacing(6)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        editable_rows = (
            ("label_5", "lineEdit_integration_time"),
            ("label_6", "lineEdit_nb_coadd"),
            ("label_7", "lineEdit_nb_frames"),
        )
        self.ui.label_5.setText("Integration time:")
        self.ui.label_7.setText("Number of frames:")
        self.ui.label_4.setText("Total integration time:")
        self.ui.label_8.setText("Next frame:")
        self.ui.lineEdit_frame_nb.setReadOnly(True)
        self.ui.lineEdit_frame_nb.setToolTip(
            "Next FITS ramp index that will be written in the save directory"
        )
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
        ramp_index = next(
            (i for i, (_, mode) in enumerate(RAMP_MODE_ITEMS) if mode == "Ramp"),
            0,
        )
        self._comboBox_ramp_mode.setCurrentIndex(ramp_index)
        self._label_fowler_pairs = QLabel("Fowler pairs:")
        self._lineEdit_fowler_pairs = QLineEdit(str(self._fowler_pairs))
        self._lineEdit_fowler_pairs.setFixedWidth(48)
        for widget in (
            self._label_ramp_mode,
            self._comboBox_ramp_mode,
            self._label_fowler_pairs,
            self._lineEdit_fowler_pairs,
        ):
            if isinstance(widget, QLabel):
                widget.setStyleSheet(PANEL_LABEL_STYLE)
            elif isinstance(widget, QLineEdit):
                style_line_edit_field(widget)
            else:
                widget.setStyleSheet(PANEL_FIELD_STYLE)
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
        self._label_frame_time = QLabel("Frame time:")
        self._lineEdit_frame_time = QLineEdit("—")
        self._lineEdit_frame_time.setReadOnly(True)
        self._label_photon_time = QLabel("Photon time:")
        self._lineEdit_photon_time = QLineEdit("—")
        self._lineEdit_photon_time.setReadOnly(True)
        self._label_execution_time = QLabel("Execution time:")
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
            style_line_edit_field(
                field,
                PANEL_FIELD_STYLE + " QLineEdit { background: rgb(250, 252, 252); }",
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

        options = QHBoxLayout()
        options.setSpacing(12)
        bg_box = self.ui.checkBox_substract_background
        bg_box.setText("Subtract background")
        bg_box.setEnabled(False)
        bg_box.setToolTip(
            "Subtract the stored background from the displayed image"
        )
        bg_box.show()
        options.addWidget(bg_box)

        save_box = QCheckBox("Save image")
        save_box.setChecked(True)
        save_box.setToolTip(
            "Keep archived FITS in the save directory. Unchecked: still acquire and "
            "display via a reusable preview.fits (no numbered archive files)."
        )
        self._checkBox_save_image = save_box
        options.addWidget(save_box)
        options.addStretch(1)
        outer.addLayout(options)

        self._button_acquire_background = QPushButton("Take Background")
        self._button_acquire_background.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        self._button_acquire_background.setToolTip(
            "Close all shutters, acquire one frame as background, then re-open shutters"
        )
        outer.addWidget(self._button_acquire_background)

        self.ui.button_take_background.setText("Use as Background")
        self.ui.button_take_background.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        self.ui.button_take_background.setToolTip(
            "Store the currently displayed image as the background"
        )
        outer.addWidget(self.ui.button_take_background)
        self._sync_background_buttons_enabled()

        actions = QHBoxLayout()
        actions.setSpacing(6)
        for name in ("button_live", "button_acquire", "button_halt"):
            button = getattr(self.ui, name)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            actions.addWidget(button)
        outer.addLayout(actions)
        self._update_next_frame_number()

    def _layout_visualisation_panel(self) -> None:
        # Replaced by H2RG ROI values panel; hide unused .ui controls.
        self.ui.groupBox_visualisation.hide()
        for name in ("checkBox_avg", "checkBox_max", "checkBox_min"):
            getattr(self.ui, name).hide()
        for index in range(1, 11):
            checkbox = getattr(self.ui, f"checkBox_ROI{index}", None)
            if checkbox is not None:
                checkbox.hide()

    def _rebuild_layout(self) -> None:
        form = self.ui
        form.setObjectName("h2rg_root")

        root = QVBoxLayout(form)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(16)

        # Left: tool buttons beside image, cursor + compact ROI below.
        self.ui.frame_camera.setMinimumSize(CAMERA_SQUARE_MIN, CAMERA_SQUARE_MIN)
        self.ui.frame_camera.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        image_column = QWidget()
        image_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        image_column_layout = QVBoxLayout(image_column)
        image_column_layout.setContentsMargins(0, 0, 0, 0)
        image_column_layout.setSpacing(6)

        image_row = QHBoxLayout()
        image_row.setContentsMargins(0, 0, 0, 0)
        image_row.setSpacing(8)
        image_row.setAlignment(Qt.AlignTop)
        image_row.addWidget(
            self._setup_image_tool_buttons(),
            stretch=0,
            alignment=Qt.AlignHCenter | Qt.AlignTop,
        )
        self._camera_host = _SquareCameraHost(
            self.ui.frame_camera,
            bottom=self._ensure_cursor_readout(),
        )
        image_row.addWidget(self._camera_host, stretch=1)
        image_column_layout.addLayout(image_row, stretch=1)

        self._roi_panel = H2rgRoiPanel(deque_length=MACIE_ROI_DEQUE_LENGTH)
        self._roi_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        for index, row in self._roi_panel.rows.items():
            row.show_checkbox.setChecked(index in self._h2rg_rois)
            row.show_checkbox.setEnabled(index in self._h2rg_rois)
        image_column_layout.addWidget(self._roi_panel, stretch=0)
        top.addWidget(image_column, stretch=1)

        # Right: logo + config at top; acquisition at bottom (aligns with ROI bottom).
        right_width = max(RIGHT_PANEL_WIDTH, 380)
        right_column = QWidget()
        right_column.setFixedWidth(right_width)
        right_column.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        self._setup_nott_logo(right_layout)
        self.ui.groupBox_conf.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Maximum
        )
        right_layout.addWidget(self.ui.groupBox_conf, stretch=0)
        right_layout.addStretch(1)
        self.ui.groupBox_acquisition.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Maximum
        )
        right_layout.addWidget(self.ui.groupBox_acquisition, stretch=0)
        top.addWidget(right_column, stretch=0)
        root.addLayout(top, stretch=1)

        self._roi_plots = H2rgRoiPlots(graph_height=max(MACIE_ROI_GRAPH_HEIGHT, 240))
        self._roi_plots.set_history_limits(
            maxlen=MACIE_ROI_DEQUE_LENGTH,
            window_seconds=MACIE_ROI_TIME_WINDOW_S,
        )
        self._roi_plots.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        root.addWidget(self._roi_plots, stretch=0)

    def _apply_styles(self) -> None:
        self.setStyleSheet(H2RG_WINDOW_STYLE)
        self.ui.frame_camera.setStyleSheet(IMAGE_FRAME_STYLE)

        for box in (
            self.ui.groupBox_conf,
            self.ui.groupBox_acquisition,
        ):
            box.setStyleSheet(
                PANEL_GROUP_STYLE
                + """
                QGroupBox {
                    background: transparent;
                }
                """
            )

        if self._roi_panel is not None:
            self._roi_panel.setStyleSheet(
                PANEL_GROUP_STYLE
                + """
                QGroupBox {
                    margin-top: 6px;
                    padding-top: 2px;
                }
                """
            )

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
        if getattr(self, "_button_acquire_background", None) is not None:
            self._button_acquire_background.setStyleSheet(PANEL_BUTTON_STYLE)

        self.ui.checkBox_substract_background.setStyleSheet(CHECKBOX_STYLE)
        if getattr(self, "_checkBox_save_image", None) is not None:
            self._checkBox_save_image.setStyleSheet(CHECKBOX_STYLE)
        if getattr(self, "_checkBox_autoscale", None) is not None:
            self._checkBox_autoscale.setStyleSheet(CHECKBOX_STYLE)

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
            widget = getattr(self.ui, name)
            if isinstance(widget, QLineEdit):
                style_line_edit_field(widget)
            else:
                widget.setStyleSheet(PANEL_FIELD_STYLE)

        style_line_edit_field(
            self.ui.lineEdit_status,
            PANEL_FIELD_STYLE + " QLineEdit { background: rgb(250, 252, 252); }",
        )

        for button in (
            getattr(self, "_button_set_exposure", None),
            getattr(self, "_button_autoscale", None),
            getattr(self, "_button_apply_levels", None),
            getattr(self, "_button_header", None),
            getattr(self, "_button_ds9", None),
            getattr(self, "_button_save_dir", None),
        ):
            if button is not None:
                button.setStyleSheet(PANEL_BUTTON_STYLE)

        for field in (
            getattr(self, "_lineEdit_level_min", None),
            getattr(self, "_lineEdit_level_max", None),
        ):
            if field is not None:
                style_line_edit_field(field)

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
                readonly_bg = (
                    PANEL_FIELD_STYLE
                    + " QLineEdit { background: rgb(250, 252, 252); }"
                    if widget.isReadOnly()
                    else None
                )
                style_line_edit_field(widget, readonly_bg)
            else:
                widget.setStyleSheet(PANEL_FIELD_STYLE)

        sanitize_widget_fonts(self)

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
        self.ui.button_take_background.clicked.connect(self.use_as_background)
        if getattr(self, "_button_acquire_background", None) is not None:
            self._button_acquire_background.clicked.connect(self.acquire_background)
        self.ui.button_live.clicked.connect(self.live_clicked)
        self.ui.button_acquire.clicked.connect(lambda: self.acquire())
        self.ui.button_halt.clicked.connect(self.halt)
        self.ui.checkBox_substract_background.toggled.connect(self._refresh_display)

        if self._roi_panel is not None:
            for row in self._roi_panel.rows.values():
                row.show_checkbox.toggled.connect(self._on_roi_toggled)
                row.time_plot_checkbox.stateChanged.connect(self._on_roi_plot_toggled)
                row.profile_plot_checkbox.stateChanged.connect(self._on_roi_plot_toggled)

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

    def _on_roi_toggled(self, _checked: bool) -> None:
        self._update_roi_overlays()
        self._refresh_display()

    def _on_roi_plot_toggled(self, _state: int = 0) -> None:
        self._refresh_roi_plots(force=True)

    def _selected_ramp_mode(self) -> str:
        if hasattr(self, "_comboBox_ramp_mode"):
            data = self._comboBox_ramp_mode.currentData()
            if data in RAMP_MODES:
                return str(data)
        return "Ramp"

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
        self._comboBox_ramp_mode.setEnabled(True)
        if hasattr(self, "ui") and self.ui is not None:
            self.ui.lineEdit_nb_coadd.setEnabled(True)
            self.ui.lineEdit_nb_frames.setEnabled(True)
            self.ui.label_5.setEnabled(True)
        fowler = self._selected_ramp_mode() == "Fowler"
        single_frame = self._selected_ramp_mode() == "SingleFrame"
        if hasattr(self, "_lineEdit_fowler_pairs"):
            self._lineEdit_fowler_pairs.setEnabled(fowler)
        if hasattr(self, "_label_fowler_pairs"):
            self._label_fowler_pairs.setEnabled(fowler)
        if hasattr(self, "ui") and self.ui is not None:
            self.ui.lineEdit_integration_time.setEnabled(not fowler and not single_frame)
            if fowler:
                label = "Integration time:"
                tooltip = (
                    "Fowler timing is controlled by Fowler pairs and ASIC registers. "
                    "Photon time is shown below after Set (ms)."
                )
            elif single_frame:
                label = "Integration time:"
                tooltip = (
                    "Single Frame uses one clocked frame (no drops). "
                    "Photon time equals the frame time shown below after Set (ms)."
                )
            elif self._selected_ramp_mode() == "Ramp":
                label = "Integration time:"
                tooltip = (
                    "Target DIT (ms), rounded to N×frame time on Set "
                    "(minimum one frame). On SC, 1×frame can show the wrong "
                    "Y band; use ≥2×frame or CDS if the window must stay fixed."
                )
            else:
                label = "Integration time:"
                tooltip = "Target photon-collection time for CDS ramps (ms)."
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

    def _frame_from_display_mode(self) -> numpy.ndarray | None:
        if self._raw_fits_cube is not None:
            data = numpy.asarray(self._raw_fits_cube, dtype=numpy.float32)
            header = self._raw_fits_header or {}
            if data.ndim <= 2:
                return data
            return science_image_from_cube(
                data,
                header,
                reduction=self._selected_ramp_mode(),  # type: ignore[arg-type]
                fowler_pairs=self._fowler_pairs_value(),
            )
        return self._current_frame

    def _selected_roi_indices(self) -> list[int]:
        if self._roi_panel is None:
            return []
        selected = []
        for index, row in self._roi_panel.rows.items():
            if row.show_checkbox.isChecked() and index in self._h2rg_rois:
                selected.append(index)
        return selected

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

        if isinstance(self.image, _PixmapImageView):
            try:
                self.image.roiGeometryChanged.disconnect(self._commit_roi_geometry)
            except TypeError:
                pass
            self.image.roiGeometryChanged.connect(self._commit_roi_geometry)
            self._update_roi_overlays()
            return

        import pyqtgraph as pg

        view = self.image.getView()
        for index, (x, y, w, h) in self._h2rg_rois.items():
            if index in self._roi_overlays:
                continue
            color = ROI_COLORS[(index - 1) % len(ROI_COLORS)]
            roi = pg.RectROI(
                [x, y],
                [w, h],
                pen=pg.mkPen(color, width=2),
                movable=True,
                removable=False,
            )
            roi.setZValue(20)
            roi.sigRegionChangeFinished.connect(
                lambda _r, idx=index: self._on_roi_geometry_changed(idx)
            )
            view.addItem(roi)
            self._roi_overlays[index] = roi
        self._update_roi_overlays()

    def _commit_roi_geometry(self, index: int, x: int, y: int, w: int, h: int) -> None:
        w = max(1, int(w))
        h = max(1, int(h))
        x = int(x)
        y = int(y)
        self._h2rg_rois[index] = (x, y, w, h)
        try:
            config.set_local(H2RG_SECTION, f"ROI {index}", f"{x},{y},{w},{h}")
            config.write_local()
        except Exception as exc:
            print(f"H2RG ROI config save failed: {exc}")
        self._refresh_display()

    def _on_roi_geometry_changed(self, index: int) -> None:
        roi = self._roi_overlays.get(index)
        if roi is None:
            return
        pos = roi.pos()
        size = roi.size()
        x = int(round(float(pos.x())))
        y = int(round(float(pos.y())))
        w = max(1, int(round(float(size.x()))))
        h = max(1, int(round(float(size.y()))))
        self._commit_roi_geometry(index, x, y, w, h)

    def _update_roi_overlays(self) -> None:
        selected = set(self._selected_roi_indices())
        if isinstance(self.image, _PixmapImageView):
            # Keep in-progress drag geometry; only sync from config when idle.
            if self.image._roi_drag is None:
                # Skip rebuild when overlays are unchanged (setImage already paints them).
                if (
                    self.image._roi_rects == self._h2rg_rois
                    and self.image._roi_visible == selected
                ):
                    return
                self.image.set_roi_overlays(self._h2rg_rois, selected)
            else:
                self.image._roi_visible = set(selected)
                self.image._rebuild_pixmap()
            return
        for index, roi in self._roi_overlays.items():
            roi.setVisible(index in selected)

    def _flush_pending_roi_update(self) -> None:
        display = self._pending_roi_display
        record = self._pending_roi_record
        self._pending_roi_display = None
        self._pending_roi_record = False
        if display is None:
            return
        self._update_roi_values(display, record=record)

    def _schedule_roi_update(
        self, display: numpy.ndarray, *, record: bool
    ) -> None:
        self._pending_roi_display = display
        self._pending_roi_record = record or self._pending_roi_record
        if not self._roi_update_timer.isActive():
            self._roi_update_timer.start(0)

    def _update_roi_values(
        self, frame: numpy.ndarray, *, record: bool
    ) -> None:
        if self._roi_panel is None or not self._h2rg_rois:
            return
        results, regions = compute_roi_brightness(frame, self._h2rg_rois)
        for index, row in self._roi_panel.rows.items():
            row.set_values(results.get(index))

        profiles: dict[int, numpy.ndarray] = {}
        for index, region in regions.items():
            profiles[index] = roi_profile_1d(region)
        self._last_roi_profiles = profiles

        if record:
            stamp = datetime.now(timezone.utc).replace(tzinfo=None)
            for index, result in results.items():
                row = self._roi_panel.rows.get(index)
                if row is not None:
                    row.add_max_value(result.max)
            if self._roi_plots is not None:
                self._roi_plots.append_timestamp(stamp)
            if MACIE_RECORD_ROIS:
                self._store_rois_to_redis(stamp, results)

        # Throttled redraw of T / 1D plots (do not force every Acquire preview —
        # pyqtgraph axis paints can stall the GUI under VNC).
        self._refresh_roi_plots(force=not record)

    def _store_rois_to_redis(
        self, stamp: datetime, results: dict
    ) -> None:
        if self._redis is None or not results:
            return
        if not self._redis.is_available():
            return
        payload = {
            redis_key_for_roi(index): result for index, result in results.items()
        }
        try:
            self._redis.add_roi_values(stamp, payload)
        except Exception as exc:
            print(f"H2RG Redis ROI write failed: {exc}")
            try:
                self._redis._mark_unavailable(exc)
            except Exception:
                pass

    def _refresh_roi_plots(self, *, force: bool = False) -> None:
        if self._roi_panel is None or self._roi_plots is None:
            return
        now = time.monotonic()
        if not force and (now - self._last_roi_plot_refresh) < MACIE_ROI_PLOT_INTERVAL_S:
            return
        self._last_roi_plot_refresh = now
        self._roi_plots.refresh_time_plot(self._roi_panel.rows)
        self._roi_plots.refresh_profile_plot(
            self._roi_panel.rows, self._last_roi_profiles
        )

    def _exposure_field_widgets(self) -> list:
        widgets = [
            getattr(self.ui, "lineEdit_integration_time", None),
            getattr(self.ui, "lineEdit_nb_coadd", None),
            getattr(self.ui, "lineEdit_nb_frames", None),
            getattr(self, "_comboBox_ramp_mode", None),
            getattr(self, "_lineEdit_fowler_pairs", None),
            getattr(self, "_label_fowler_pairs", None),
            getattr(self.ui, "label_5", None),
        ]
        return [widget for widget in widgets if widget is not None]

    def _set_exposure_panel_enabled(self, enabled: bool) -> None:
        for widget in self._exposure_field_widgets():
            widget.setEnabled(enabled)
        if enabled:
            self._sync_ramp_mode_fields()

    def _sync_background_buttons_enabled(self) -> None:
        """Enable background buttons only when initialized and not acquiring/live."""
        if self.ui is None:
            return
        enabled = (
            self._initialized
            and not self._macie_operation_busy
            and not self._live_active
        )
        self.ui.button_take_background.setEnabled(enabled)
        if getattr(self, "_button_acquire_background", None) is not None:
            self._button_acquire_background.setEnabled(
                enabled and self._opcua_conn is not None
            )

    def _apply_macie_operation_busy(self, busy: bool) -> None:
        self._macie_operation_busy = busy
        if self.ui is None:
            return

        if busy:
            self._set_controls_enabled(False)
            if hasattr(self, "_button_set_exposure"):
                self._button_set_exposure.setEnabled(False)
            self.ui.button_init.setEnabled(False)
            self._set_exposure_panel_enabled(False)
            self._sync_background_buttons_enabled()
            return

        self._update_next_frame_number()
        if self._live_active:
            self._set_live_dependent_controls(True)
            return

        self._set_controls_enabled(self._initialized)
        if hasattr(self, "_button_set_exposure"):
            self._button_set_exposure.setEnabled(self._initialized)
        if self._initialized:
            self.ui.button_init.setEnabled(True)
            self._set_exposure_panel_enabled(True)
        self._sync_background_buttons_enabled()

    def _set_live_dependent_controls(self, live: bool) -> None:
        if self.ui is None or not self._initialized:
            return
        enabled = not live and not self._macie_operation_busy
        self.ui.button_acquire.setEnabled(enabled)
        if hasattr(self, "_button_set_exposure"):
            self._button_set_exposure.setEnabled(enabled)
        self.ui.comboBox_detector_mode.setEnabled(enabled)
        self.ui.comboBox_window_mode.setEnabled(enabled)
        self.ui.button_init.setEnabled(enabled)
        self.ui.button_powerOn.setEnabled(enabled)
        self.ui.button_powerOff.setEnabled(enabled)
        self._set_exposure_panel_enabled(enabled)
        self._sync_background_buttons_enabled()

    def _stop_live_ui(self) -> None:
        self._live_active = False
        self._live_poll_stop.set()
        self._live_frame_available.set()
        if self.ui is not None:
            self.ui.button_live.setText("Live")
        self._set_live_dependent_controls(False)
        if self._macie is not None:
            self._macie.set_live_frame_callback(None)

    def _on_live_frame_written(self, frame=None) -> None:
        """Called from the Macie continuous thread after each acquire completes."""
        self._live_pending_frame = frame
        self._live_frame_available.set()

    def _activate_live_ui(self) -> None:
        self._live_active = True
        self._live_poll_stop.clear()
        self._live_frame_available.clear()
        self._live_pending_frame = None
        if self.ui is not None:
            self.ui.button_live.setText("Stop live")
        self._set_live_dependent_controls(True)
        if self._macie is not None:
            self._macie.set_live_frame_callback(self._on_live_frame_written)
            try:
                self._sync_save_dir_from_server(self._macie)
            except Exception:
                pass

        def poll_frames() -> None:
            while (
                self._live_active
                and self._macie is not None
                and not self._live_poll_stop.is_set()
            ):
                self._live_frame_available.wait(timeout=0.4)
                self._live_frame_available.clear()
                if (
                    not self._live_active
                    or self._macie is None
                    or self._live_poll_stop.is_set()
                ):
                    break
                self._arm_frame_timing("Live")
                pending = self._live_pending_frame
                self._live_pending_frame = None
                if pending is not None:
                    self._raw_fits_cube = None
                    self._raw_fits_header = None
                    self._last_fits_path = None
                    if self._save_image_enabled():
                        status = "Live — ZMQ preview"
                    else:
                        status = "Live — ZMQ preview (not archived)"
                    self._frame_timing_status = status
                    self.frame_ready.emit(numpy.asarray(pending, dtype=numpy.float32))
                    continue
                loaded = self._load_live_frame(self._macie)
                if loaded is not None:
                    frame, path = loaded
                    if self._save_image_enabled():
                        status = f"Live — {path.name}"
                    else:
                        status = f"Live — {path.name} (not archived)"
                    self._frame_timing_status = status
                    self.frame_ready.emit(frame)
                else:
                    self._frame_timing_t0 = None
                    self._frame_timing_status = None

        threading.Thread(target=poll_frames, daemon=True).start()

    def _fits_snapshot_before_acquire(self, macie) -> tuple[float, str | None]:
        self._sync_save_dir_from_server(macie)
        before_mtime = self._latest_fits_mtime()
        before_name = fits_basename(self._newest_fits_file(allow_probe=True))
        # Prefer the server's newest ramp name so a wrong/stale local fits_directory
        # does not poison the "is this file new?" checks used for ZMQ fetch.
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
        # Confirm what the server actually programmed (helps catch SC mis-centers).
        try:
            x_win, y_win, x1, x2, y1, y2 = macie.read_frame_settings()
            x1_i, x2_i, y1_i, y2_i = int(x1), int(x2), int(y1), int(y2)
        except Exception:
            x_win = mode.x_window
            y_win = mode.y_window
            x1_i, x2_i, y1_i, y2_i = mode.x1, mode.x2, mode.y1, mode.y2

        matched = window_mode_index(x_win, y_win, x1_i, x2_i, y1_i, y2_i)
        if mode.y_window and not mode.x_window:
            if mode.y1 < 4:
                stripe_note = "burst stripe, bottom-aligned, 32 outputs"
            elif mode.y2 > H2RG_ARRAY_SIZE - 5:
                stripe_note = "burst stripe, top-aligned, 32 outputs"
            else:
                stripe_note = "burst stripe, centered, 32 outputs"
            status = (
                f"{mode.label} — requested y=[{mode.y1},{mode.y2}], "
                f"ASIC y=[{y1_i},{y2_i}] ({stripe_note})"
            )
            if (y1_i, y2_i) != (mode.y1, mode.y2):
                status += " — WARNING: Y readback differs from request"
        elif mode.x_window or mode.y_window:
            status = (
                f"{mode.label} — ASIC x=[{x1_i},{x2_i}] y=[{y1_i},{y2_i}]"
            )
        else:
            status = mode.label
        if matched >= 0 and matched != index:
            status += f" (readback matches {WINDOW_MODES[matched].label})"
        self.status_updated.emit(status)
        # Frametime changed with the window — apply the same ramp plan Acquire
        # uses so photon/execution match immediately (not only on Acquire).
        self._applied_exposure_fingerprint = None
        self._apply_exposure_settings(macie)

    def _apply_detector_mode_to_macie(
        self, macie, mode_index: int, window_index: int
    ) -> None:
        config_file = detector_config_file(mode_index)
        self.status_updated.emit(f"Switching to {DETECTOR_MODES[mode_index]} mode…")
        macie.reinit_camera(config_file)
        self._applied_exposure_fingerprint = None
        if 0 <= window_index < len(WINDOW_MODES):
            self._apply_window_mode_to_macie(macie, window_index)
        self._sync_save_dir_from_server(macie)
        self._refresh_readouts(macie)
        self.status_updated.emit(f"Detector mode: {DETECTOR_MODES[mode_index]}")

    def _on_exposure_fields_changed(self) -> None:
        # GUI-only preview until Set / Acquire / window apply latches the ASIC.
        # Drop the fingerprint so the next Apply/Acquire does not skip reconfigure.
        self._applied_exposure_fingerprint = None
        self._update_total_integration_label()

    def _on_set_exposure_clicked(self) -> None:
        self._update_total_integration_label()
        if not self._initialized:
            self._set_status("Initialize camera before setting exposure")
            return

        def operation() -> None:
            self._apply_exposure_settings(self._ensure_macie(), force=True)

        self._run_macie_operation(
            "Set exposure",
            operation,
            status="Setting exposure…",
        )

    def _format_level_value(self, value: float) -> str:
        if not numpy.isfinite(value):
            return ""
        rounded = float(numpy.round(value))
        if abs(rounded - value) < 1e-6:
            return str(int(rounded))
        return f"{value:.2f}"

    def _sync_level_fields(self, vmin: float, vmax: float) -> None:
        # Never overwrite a field the user is editing — that jumps the caret.
        if self._lineEdit_level_min is not None and not self._lineEdit_level_min.hasFocus():
            self._lineEdit_level_min.setText(self._format_level_value(vmin))
        if self._lineEdit_level_max is not None and not self._lineEdit_level_max.hasFocus():
            self._lineEdit_level_max.setText(self._format_level_value(vmax))

    def _sync_level_fields_from_image(self) -> None:
        if self.image is None:
            return
        try:
            levels = self.image.getLevels()
        except Exception:
            return
        if levels is None:
            return
        try:
            vmin, vmax = float(levels[0]), float(levels[1])
        except (TypeError, ValueError, IndexError):
            return
        self._manual_levels = (vmin, vmax)
        self._sync_level_fields(vmin, vmax)

    def _read_level_fields(self) -> tuple[float, float] | None:
        if self._lineEdit_level_min is None or self._lineEdit_level_max is None:
            return None
        try:
            vmin = float(self._lineEdit_level_min.text().strip())
            vmax = float(self._lineEdit_level_max.text().strip())
        except ValueError:
            return None
        if not numpy.isfinite(vmin) or not numpy.isfinite(vmax) or vmin >= vmax:
            return None
        return vmin, vmax

    def _set_autoscale_checked(self, checked: bool) -> None:
        box = getattr(self, "_checkBox_autoscale", None)
        if box is None or box.isChecked() == checked:
            return
        box.blockSignals(True)
        box.setChecked(checked)
        box.blockSignals(False)

    def _on_autoscale_toggled(self, checked: bool) -> None:
        if not checked:
            # Lock to the current scale (or Min/Max fields if already set).
            levels = self._read_level_fields()
            if levels is None and self.image is not None:
                try:
                    current = self.image.getLevels()
                    if current is not None:
                        levels = (float(current[0]), float(current[1]))
                except Exception:
                    levels = None
            if levels is not None:
                self._manual_levels = levels
                self._sync_level_fields(levels[0], levels[1])
        self._refresh_display()

    def _autoscale_image(self) -> None:
        display = self._build_display_frame()
        if self.image is None or display is None:
            return
        finite = display[numpy.isfinite(display)]
        if finite.size == 0:
            return
        vmin = float(numpy.min(finite))
        vmax = float(numpy.max(finite))
        if vmin >= vmax:
            vmax = vmin + 1.0
        self._manual_levels = (vmin, vmax)
        self._sync_level_fields(vmin, vmax)
        self._set_autoscale_checked(True)
        self.image.setLevels(vmin, vmax)
        self._refresh_display()

    def _apply_manual_levels(self) -> None:
        levels = self._read_level_fields()
        if levels is None or self.image is None:
            return
        self._manual_levels = levels
        self._set_autoscale_checked(False)
        self.image.setLevels(levels[0], levels[1])
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
                "Install SAOImage DS9 or set [H2RG DETECTOR] ds9_executable in config.ini.",
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

        configured = config.get(H2RG_SECTION, "fits_directory", fallback="").strip()
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
                "Set [H2RG DETECTOR] fits_directory (and fits_linux_path_prefix / "
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
        # Avoid home()/setCursorPosition on Linux: extra text-layout work under
        # broken conda FreeType. Cursor position is irrelevant for read-only status.
        if not sys.platform.startswith("linux"):
            status.setCursorPosition(0)
            status.home(False)

    def _set_controls_enabled(self, enabled: bool) -> None:
        if self.ui is None:
            return
        for name in (
            "button_powerOn",
            "button_powerOff",
            "button_live",
            "button_acquire",
            "button_halt",
        ):
            getattr(self.ui, name).setEnabled(enabled)
        if hasattr(self, "_button_set_exposure"):
            self._button_set_exposure.setEnabled(enabled)
        if enabled and not self._macie_operation_busy and not self._live_active:
            self._set_exposure_panel_enabled(True)
        self._sync_background_buttons_enabled()

    def _apply_init_button_state(self, state: str) -> None:
        if self.ui is None:
            return
        button = self.ui.button_init
        if state == "busy":
            button.setEnabled(False)
            button.setText("Initializing…")
            self._sync_background_buttons_enabled()
            return
        if state == "done":
            self._initialized = True
            button.setEnabled(True)
            button.setText("Re-init")
            self._sync_background_buttons_enabled()
            return
        self._initialized = False
        self._applied_exposure_fingerprint = None
        button.setEnabled(True)
        button.setText("Init")
        self._sync_background_buttons_enabled()

    def _apply_exposure_timing(self, timing: dict[str, float]) -> None:
        if self.ui is None:
            return
        self._lineEdit_frame_time.setText(f"{timing['frametime_s'] * 1000:.4g}")
        self._lineEdit_photon_time.setText(f"{timing['inttime_s'] * 1000:.4g}")
        self._lineEdit_execution_time.setText(f"{timing['execution_s'] * 1000:.4g}")
        self._lineEdit_efficiency.setText(f"{timing['efficiency'] * 100:.1f}")

    def _apply_integration_time_text(self, text: str) -> None:
        if self.ui is None:
            return
        field = self.ui.lineEdit_integration_time
        # Avoid fighting the caret if the user is mid-edit when a late Set reply arrives.
        if field.hasFocus() and field.text() == text:
            return
        field.setText(text)
        self._update_total_integration_label()

    def _refresh_exposure_timing(self, macie) -> None:
        try:
            timing = macie.read_exposure_timing()
        except Exception:
            return
        self.exposure_timing_updated.emit(timing)

    def _schedule_exposure_timing_preview(self) -> None:
        # Kept for the timer wiring; field edits no longer push to the ASIC.
        self._update_total_integration_label()

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
        self._macie.set_live_frame_callback(
            self._on_live_frame_written if self._live_active else None
        )
        return self._macie

    def _run_macie_operation(
        self,
        label: str,
        operation,
        *,
        status: str | None = None,
        done_event: threading.Event | None = None,
    ) -> None:
        if status:
            self.status_updated.emit(status)
        # Set busy synchronously so worker-side checks (save-dir sync, next-frame
        # rglob) see it before the Queued GUI slot runs.
        self._macie_operation_busy = True
        self._sync_background_buttons_enabled()
        self.macie_operation_busy.emit(True)

        def worker() -> None:
            macie = self._macie
            if macie is not None:
                macie.pause_live_acquisition()
            try:
                with self._operation_lock:
                    operation()
            except Exception as exc:
                message = f"{label} failed: {exc}"
                if isinstance(done_event, threading.Event):
                    self._remote_op_error = message
                self.operation_failed.emit(message)
            finally:
                if macie is not None:
                    macie.resume_live_acquisition()
                self._macie_operation_busy = False
                self.macie_operation_busy.emit(False)
                if isinstance(done_event, threading.Event):
                    done_event.set()

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
            self._applied_exposure_fingerprint = None
            if 0 <= window_index < len(WINDOW_MODES):
                self._apply_window_mode_to_macie(macie, window_index)
            self._sync_save_dir_from_server(macie)
            self._refresh_readouts(macie)
            self.status_updated.emit(
                "Initialized — edit DIT then Set (or Acquire latches DIT automatically)"
            )
            # Mark initialized before enabling controls (QueuedConnection order).
            self.init_button_state.emit("done")
            self.controls_enabled.emit(True)

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

    def _save_image_enabled(self) -> bool:
        box = getattr(self, "_checkBox_save_image", None)
        if box is None:
            return True
        return bool(box.isChecked())

    def _autoscale_enabled(self) -> bool:
        box = getattr(self, "_checkBox_autoscale", None)
        if box is None:
            return True
        return bool(box.isChecked())

    def _exposure_request_fingerprint(self) -> tuple:
        """GUI fields that define the ramp plan (skip ASIC reconfigure if unchanged)."""
        ramp_mode = self._selected_ramp_mode()
        ncoadds = int(self.ui.lineEdit_nb_coadd.text().strip() or "1")
        nseq = int(self.ui.lineEdit_nb_frames.text().strip() or "1")
        fowler_pairs = self._fowler_pairs_value()
        window_index = self.ui.comboBox_window_mode.currentIndex()
        windowed = self._windowed_cds_layout()
        windowed_cds = windowed and ramp_mode == "CDS"
        if ramp_mode in ("Fowler", "SingleFrame"):
            tint_key: str | float = "auto"
        else:
            text = (
                self.ui.lineEdit_integration_time.text()
                .strip()
                .replace(",", ".")
            )
            tint_key = float(text) if text else "default"
        return (
            ramp_mode,
            int(fowler_pairs),
            ncoadds,
            nseq,
            self._save_image_enabled(),
            tint_key,
            window_index,
            windowed,  # soft SC / any window — ramp plan must stay geometry-stable
            MACIE_INTEGRATION_NGROUPS_MAX,
        )

    def _requested_tint_ms(self, macie, ramp_mode: str) -> float:
        """Integration time from the GUI, or frametime if the field is empty."""
        if ramp_mode in ("Fowler", "SingleFrame"):
            try:
                return float(macie.read_exposure_timing()["frametime_s"] * 1000.0)
            except Exception:
                return 1.0
        text = self.ui.lineEdit_integration_time.text().strip().replace(",", ".")
        if not text:
            try:
                return float(macie.read_exposure_timing()["frametime_s"] * 1000.0)
            except Exception:
                return 1.0
        tint_ms = float(text)
        if tint_ms <= 0:
            raise ValueError("Integration time must be greater than zero")
        return tint_ms

    def _exposure_report_from_server(self, macie) -> dict[str, float | int]:
        """Timing/ramp snapshot for Acquire when Set has not been clicked yet."""
        timing = macie.read_exposure_timing()
        _save, ncoadds, nseq, ngroups, nreads, ndrops, _nresets = (
            macie.read_exposure_settings()
        )
        return {
            "ngroups": int(ngroups),
            "nreads": int(nreads),
            "ndrops": int(ndrops),
            "fowler_pairs": int(self._fowler_pairs),
            "inttime_ms": float(timing["inttime_s"] * 1000.0),
            "ramptime_ms": float(timing["ramptime_s"] * 1000.0),
            "execution_s": float(timing["execution_s"]),
            "frametime_ms": float(timing["frametime_s"] * 1000.0),
            "efficiency": float(timing["efficiency"]),
            "ncoadds": int(ncoadds),
            "nseq": int(nseq),
            "ramp_mode": self._selected_ramp_mode(),
            "mode_detail": "server",
        }

    def _apply_exposure_settings(
        self, macie, *, force: bool = False
    ) -> dict[str, float | int]:
        try:
            fingerprint = self._exposure_request_fingerprint()
        except ValueError as exc:
            raise ValueError(f"Invalid exposure field: {exc}") from exc

        if (
            not force
            and fingerprint == self._applied_exposure_fingerprint
            and self._last_exposure_report is not None
        ):
            self._refresh_exposure_timing(macie)
            return self._last_exposure_report

        try:
            ncoadds = int(self.ui.lineEdit_nb_coadd.text().strip() or "1")
            nseq = int(self.ui.lineEdit_nb_frames.text().strip() or "1")
            self._fowler_pairs = self._fowler_pairs_value()
        except ValueError as exc:
            raise ValueError(f"Invalid exposure field: {exc}") from exc

        ramp_mode = self._selected_ramp_mode()
        try:
            tint_ms = self._requested_tint_ms(macie, ramp_mode)
        except ValueError as exc:
            raise ValueError(f"Invalid integration time: {exc}") from exc

        result = macie.configure_ramp_exposure(
            tint_ms,
            ramp_mode=ramp_mode,
            fowler_pairs=self._fowler_pairs,
            ngmax=MACIE_INTEGRATION_NGROUPS_MAX,
            ncoadds=ncoadds,
            nseq=nseq,
            save=self._save_image_enabled(),
            # Soft SC / any window: keep a geometry-stable plan (never 1-read).
            windowed_cds=self._windowed_cds_layout(),
        )
        self._last_tint_ms = float(result["inttime_ms"])
        # Ramp/CDS on soft SC quantize DIT to N×frametime — mirror in the box.
        rounded = result.get("rounded_tint_ms")
        if ramp_mode in ("Ramp", "CDS") and rounded is not None:
            rounded_f = float(rounded)
            self.integration_time_updated.emit(f"{rounded_f:.6g}")
            fingerprint = (
                fingerprint[0],
                fingerprint[1],
                fingerprint[2],
                fingerprint[3],
                fingerprint[4],
                rounded_f,
                fingerprint[6],
                fingerprint[7],
                fingerprint[8],
            )
        # Photon time (read-only) shows the achieved value.
        self._update_total_integration_label(actual_tint_ms=self._last_tint_ms)
        self._refresh_exposure_timing(macie)
        if ramp_mode == "Fowler":
            mode_detail = f"Fowler-{result['fowler_pairs']}, reads={result['nreads']}"
        elif ramp_mode == "SingleFrame":
            mode_detail = "single frame"
        elif ramp_mode == "Ramp":
            mode_detail = "raw sample"
        else:
            mode_detail = "CDS"
            if self._windowed_cds_layout():
                mode_detail = "window CDS"
        self.status_updated.emit(
            f"Ramp {ramp_mode}: {self._last_tint_ms:.3g} ms photon, "
            f"{mode_detail}, frames={nseq}"
        )
        self._last_exposure_report = {
            **result,
            "mode_detail": mode_detail,
        }
        self._applied_exposure_fingerprint = fingerprint
        self._print_efficiency_report(self._last_exposure_report)
        return result

    def _print_efficiency_report(
        self,
        report: dict[str, float | int | str],
        *,
        wall_s: float | None = None,
        label: str = "Exposure",
    ) -> None:
        """Print ASIC duty-cycle efficiency and ramp timing to the terminal."""
        try:
            frametime_ms = float(report.get("frametime_ms", 0.0))
            inttime_ms = float(report.get("inttime_ms", 0.0))
            ramptime_ms = float(report.get("ramptime_ms", 0.0))
            execution_s = float(report.get("execution_s", 0.0))
            efficiency = float(report.get("efficiency", 0.0))
            ngroups = int(report.get("ngroups", 0))
            nreads = int(report.get("nreads", 0))
            ndrops = int(report.get("ndrops", 0))
            ncoadds = int(report.get("ncoadds", 1))
            nseq = int(report.get("nseq", 1))
            ramp_mode = str(report.get("ramp_mode", "?"))
            mode_detail = str(report.get("mode_detail", ramp_mode))
        except (TypeError, ValueError):
            return

        overhead_ms = max(0.0, ramptime_ms - inttime_ms)
        lines = [
            f"H2RG: {label} efficiency",
            f"  mode: {ramp_mode} ({mode_detail})",
            f"  ramp: ngroups={ngroups} nreads={nreads} ndrops={ndrops} "
            f"ncoadds={ncoadds} nseq={nseq}",
            f"  frame={frametime_ms:.3f} ms  photon={inttime_ms:.3f} ms  "
            f"ramp={ramptime_ms:.3f} ms  overhead={overhead_ms:.3f} ms",
            f"  ASIC duty cycle: {efficiency * 100:.1f}%  "
            f"(photon/ramp; estimated ASIC exec {execution_s:.3f} s)",
        ]
        if wall_s is not None and wall_s > 0:
            wall_eff = (inttime_ms / 1000.0) / wall_s if inttime_ms > 0 else 0.0
            asic_vs_wall = (execution_s / wall_s) if execution_s > 0 else 0.0
            lines.append(
                f"  wall clock: {wall_s:.2f} s  "
                f"(photon/wall {wall_eff * 100:.1f}%, "
                f"ASIC-est/wall {asic_vs_wall * 100:.1f}%)"
            )
        print("\n".join(lines), flush=True)

    def acquire(self, done_event: threading.Event | None = None) -> None:
        # Guard: QPushButton.clicked emits a bool; never treat that as done_event.
        if done_event is not None and not isinstance(done_event, threading.Event):
            done_event = None
        if self._live_active:
            self._on_operation_failed("Stop live mode before acquiring")
            if isinstance(done_event, threading.Event):
                done_event.set()
            return

        def operation() -> None:
            from nottcontrol.camera.macie.macie_interface import ZMQ_ACQUIRE_TIMEOUT_MS

            macie = self._ensure_macie()
            # Latch current GUI DIT/mode before trigger (Init alone left a stale
            # plan if the user edited integration time and skipped Set).
            exposure = self._apply_exposure_settings(macie)
            try:
                ncoadds = int(exposure.get("ncoadds", 1))
                nseq = int(exposure.get("nseq", 1))
            except (TypeError, ValueError):
                ncoadds, nseq = 1, 1
            keep_files = self._save_image_enabled()
            self._fits_dir_ok = None
            self._arm_frame_timing("Acquire")

            if not keep_files:
                preview = self._preview_fits_path()
                try:
                    before_mtime = preview.stat().st_mtime if preview.is_file() else 0.0
                except OSError:
                    before_mtime = 0.0
                result = macie.acquire()
                if result.frame is not None:
                    self._raw_fits_cube = None
                    self._raw_fits_header = None
                    self._last_fits_path = None
                    self._frame_timing_status = (
                        "Acquire complete — displayed via ZMQ preview (not archived)"
                    )
                    self.frame_ready.emit(
                        numpy.asarray(result.frame, dtype=numpy.float32)
                    )
                    return
                frame, path = self._wait_for_preview_fits(
                    preview,
                    before_mtime=before_mtime,
                    timeout_s=fits_wait_timeout_s(
                        float(exposure["execution_s"]),
                        ncoadds=ncoadds,
                        nseq=nseq,
                        margin_s=MACIE_FITS_WAIT_MARGIN_S,
                        maximum_s=(ZMQ_ACQUIRE_TIMEOUT_MS / 1000.0)
                        + MACIE_FITS_WAIT_MARGIN_S,
                    ),
                )
                if frame is None:
                    self._frame_timing_t0 = None
                    self.status_updated.emit(self._missing_fits_status())
                    return
                self._last_fits_path = None
                self._frame_timing_status = (
                    f"Acquire complete — displayed via {path.name} (not archived)"
                )
                self.frame_ready.emit(frame)
                return

            before_mtime, before_name = self._fits_snapshot_before_acquire(macie)
            wait_timeout_s = fits_wait_timeout_s(
                float(exposure["execution_s"]),
                ncoadds=ncoadds,
                nseq=nseq,
                margin_s=MACIE_FITS_WAIT_MARGIN_S,
                maximum_s=(ZMQ_ACQUIRE_TIMEOUT_MS / 1000.0) + MACIE_FITS_WAIT_MARGIN_S,
            )
            expected = max(1, nseq)
            self._acquire_previewed_names = set()
            self._acquire_preview_reduction = self._selected_ramp_mode()
            self._acquire_preview_fowler = self._fowler_pairs_value()
            # Poll local FITS while acquire() runs so each soft-SC ramp paints
            # as it is written (natural cadence), not as a burst after ZMQ returns.
            stop_preview = threading.Event()
            preview_thread = None
            if expected > 1:
                preview_thread = threading.Thread(
                    target=self._poll_acquire_previews,
                    args=(
                        before_mtime,
                        before_name,
                        expected,
                        stop_preview,
                    ),
                    daemon=True,
                    name="h2rg-acquire-preview",
                )
                preview_thread.start()
            result = None
            ramp_paths: list[Path] = []
            frame = None
            preview_path = None
            try:
                result = macie.acquire()
                # Multi-frame: skip early ZMQ paint — it is only the last ramp.
                if result.frame is not None and expected <= 1:
                    self._frame_timing_skip_report = True
                    self.frame_ready.emit(
                        numpy.asarray(result.frame, dtype=numpy.float32)
                    )
                    self.status_updated.emit("Acquire: preview — ZMQ")

                ramp_paths, frame, preview_path = self._wait_for_acquire_frames(
                    before_mtime,
                    macie,
                    before_name=before_name,
                    expected_count=expected,
                    timeout_s=wait_timeout_s,
                    display_each=expected > 1,
                )
            finally:
                stop_preview.set()
                if preview_thread is not None:
                    preview_thread.join(timeout=2.0)

            if frame is not None and preview_path is not None:
                science_paths: list[Path] = []
                for ramp_path in ramp_paths:
                    # Always stamp DETMODE / cryo cards on the ramp archive,
                    # including when science FITS writes are disabled.
                    self._stamp_ramp_fits_headers(ramp_path)
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
                self._frame_timing_status = self._acquire_complete_status(
                    ramp_paths, science_paths
                )
                # Intermediates already painted during acquire; final frame_ready
                # refreshes ROI/timing once without a rapid replay burst.
                self.frame_ready.emit(frame)
            else:
                if result is not None and result.frame is not None:
                    self._last_fits_path = None
                    self._frame_timing_status = (
                        "Acquire complete — ZMQ preview (archive FITS missing)"
                    )
                    self.frame_ready.emit(
                        numpy.asarray(result.frame, dtype=numpy.float32)
                    )
                else:
                    self._frame_timing_t0 = None
                    self.status_updated.emit(self._missing_fits_status())

        self._run_macie_operation("Acquire", operation, done_event=done_event)

    def _arm_frame_timing(self, label: str = "Acquire") -> None:
        """Start wall-clock timing; reported when the frame is displayed."""
        self._frame_timing_t0 = time.perf_counter()
        self._frame_timing_label = label

    def _report_frame_timing(self) -> float | None:
        t0 = self._frame_timing_t0
        if t0 is None:
            return None
        elapsed = time.perf_counter() - t0
        self._frame_timing_t0 = None
        label = self._frame_timing_label or "Frame"
        print(
            f"H2RG: {label} took {elapsed:.2f} s (take + display)",
            flush=True,
        )
        if self._last_exposure_report is not None:
            if label == "Live":
                try:
                    inttime_ms = float(self._last_exposure_report.get("inttime_ms", 0.0))
                    execution_s = float(self._last_exposure_report.get("execution_s", 0.0))
                    efficiency = float(self._last_exposure_report.get("efficiency", 0.0))
                except (TypeError, ValueError):
                    inttime_ms = execution_s = efficiency = 0.0
                wall_eff = (inttime_ms / 1000.0) / elapsed if elapsed > 0 else 0.0
                print(
                    f"H2RG: Live efficiency — ASIC duty {efficiency * 100:.1f}%, "
                    f"photon/wall {wall_eff * 100:.1f}%, "
                    f"ASIC-est {execution_s:.3f} s / wall {elapsed:.2f} s",
                    flush=True,
                )
            else:
                self._print_efficiency_report(
                    self._last_exposure_report,
                    wall_s=elapsed,
                    label=label,
                )
        status = self._frame_timing_status
        self._frame_timing_status = None
        if status:
            self.status_updated.emit(f"{status}  [{elapsed:.2f} s]")
        return elapsed

    def _acquire_complete_status(
        self, ramp_paths: list[Path], science_paths: list[Path]
    ) -> str:
        if len(ramp_paths) > 1:
            base = (
                f"Acquire complete — {len(ramp_paths)} frames "
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

        configured = config.get(H2RG_SECTION, "fits_directory", fallback="").strip()
        if configured and not (
            sys.platform != "win32" and _looks_like_windows_unc(configured)
        ):
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

    def _cryo_fits_header_cards(self):
        """Instrument status from Redis (temps, pressures, DL positions) for FITS."""
        return fits_header_cards_from_redis(self._redis)

    def _acquisition_fits_header_cards(self):
        """Cards stamped on ramp/science FITS after acquire (mode + timing + cryo)."""
        report = self._last_exposure_report or {}
        cards = exposure_fits_cards(
            mode=self._selected_ramp_mode(),
            tint_ms=self._last_tint_ms,
            ngroups=report.get("ngroups"),
            nreads=report.get("nreads"),
            ndrops=report.get("ndrops"),
        )
        cards.extend(self._cryo_fits_header_cards())
        return cards

    def _apply_cryo_temps_to_ramp(self, ramp_path: Path | None, cards) -> None:
        """Stamp Redis status onto the in-memory and on-disk ramp headers when possible."""
        if not cards:
            return
        if self._raw_fits_header is not None:
            for keyword, (value, _comment) in header_cards_as_value_dict(cards).items():
                self._raw_fits_header[keyword] = value
        if ramp_path is None:
            return
        resolved = self._resolve_ramp_path(ramp_path)
        if resolved is None or not resolved.is_file():
            return
        from nottcontrol.camera.macie.fits_header_meta import update_fits_file_header_cards

        update_fits_file_header_cards(resolved, cards)

    def _stamp_ramp_fits_headers(self, ramp_path: Path | None) -> list:
        """Write DETMODE/EXPTIME (+ cryo cards) onto the on-disk ramp FITS."""
        cards = self._acquisition_fits_header_cards()
        self._apply_cryo_temps_to_ramp(ramp_path, cards)
        return cards

    def _discard_fits_files(self, paths: list[Path]) -> None:
        """Remove temporary ramp FITS used only for display when Save image is off."""
        for path in paths:
            try:
                resolved = self._resolve_ramp_path(path) or path
                if resolved.is_file():
                    resolved.unlink()
            except OSError as exc:
                print(f"H2RG failed to remove unsaved FITS {path}: {exc}")

    def _preview_fits_path(self) -> Path:
        """Reusable preview FITS written when Save image is off."""
        return self._save_dir / "preview.fits"

    def _wait_for_preview_fits(
        self,
        preview: Path,
        *,
        before_mtime: float,
        timeout_s: float,
    ) -> tuple[numpy.ndarray | None, Path]:
        deadline = time.monotonic() + max(1.0, float(timeout_s))
        while time.monotonic() < deadline:
            try:
                if preview.is_file():
                    mtime = preview.stat().st_mtime
                    if mtime > before_mtime or before_mtime <= 0.0:
                        # Allow a brief settle so the write is complete.
                        time.sleep(0.05)
                        frame = self._load_fits_from_path(preview)
                        return frame, preview
            except Exception as exc:
                print(f"H2RG preview wait: {exc}")
            time.sleep(0.1)
        return None, preview

    def _save_science_fits(
        self, frame: numpy.ndarray, ramp_path: Path | None
    ) -> Path | None:
        if not MACIE_SAVE_SCIENCE_FITS or ramp_path is None:
            return None
        if not self._save_image_enabled():
            return None
        output_path = self._science_output_path(ramp_path)
        cards = self._acquisition_fits_header_cards()
        try:
            save_science_fits(
                output_path,
                frame,
                source_header=self._raw_fits_header,
                tint_ms=self._last_tint_ms,
                reduction=self._selected_ramp_mode(),  # type: ignore[arg-type]
                fowler_pairs=self._fowler_pairs_value(),
                extra_cards=cards,
            )
            return output_path
        except OSError as exc:
            print(f"H2RG failed to save science FITS: {exc}")
            return None

    def _save_science_fits_from_ramp(self, ramp_path: Path) -> Path | None:
        if not MACIE_SAVE_SCIENCE_FITS:
            return None
        if not self._save_image_enabled():
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
        cards = self._acquisition_fits_header_cards()
        for keyword, (value, _comment) in header_cards_as_value_dict(cards).items():
            header[keyword] = value
        self._raw_fits_header = dict(header)
        try:
            save_science_fits(
                output_path,
                frame,
                source_header=header,
                tint_ms=self._last_tint_ms,
                reduction=self._selected_ramp_mode(),  # type: ignore[arg-type]
                fowler_pairs=self._fowler_pairs_value(),
                extra_cards=cards,
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
        # Always track the server's saveDir (incl. dated subfolder). Requiring
        # is_dir() left the GUI on a stale fits_directory share when the SMB
        # mapping was slow or pointed at a different root.
        if mapped != self._save_dir:
            self._save_dir = mapped
            self._fits_dir_ok = None
        # Never call this from the mid-acquire preview poll: acquire() holds the
        # MACIE ZMQ lock for the whole soft-SC sequence, so get_save_dir() would
        # block until the end and all previews would fire at once.
        if not self._macie_operation_busy:
            self._update_next_frame_number()

    def _update_next_frame_number(self) -> None:
        """Show the next free FITS ramp index in the acquisition panel."""
        if self.ui is None:
            return
        try:
            text = next_fits_frame_number(
                self._save_dir, dir_ok=self._fits_dir_ok
            )
        except Exception:
            text = "—"
        self.ui.lineEdit_frame_nb.setText(text)

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
        already_seen: set[str] | None = None,
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
        if already_seen is not None and name in already_seen:
            return False
        mapped = map_server_fits_path(server_path)
        if mapped is not None:
            try:
                mtime = mapped.stat().st_mtime
            except OSError:
                # Mapped UNC/path not readable from this PC — trust basename.
                if before_name and name == before_name:
                    # Same name as pre-acquire snapshot: still fetch if we have
                    # not loaded anything yet (already_seen empty / unknown).
                    return already_seen is not None and len(already_seen) == 0
                return True
            return is_new_ramp_fits(
                name,
                mtime,
                before_name=before_name,
                before_mtime=before_mtime,
            )
        # No local mapping (typical Windows without SMB) — basename is enough,
        # but allow a post-acquire fetch of the snapshot name when seen is empty.
        if before_name and name == before_name:
            return already_seen is not None and len(already_seen) == 0
        return True

    def _fetch_fits_from_server(
        self,
        macie,
        *,
        before_mtime: float = 0.0,
        before_name: str | None = None,
        require_new: bool = True,
        already_seen: set[str] | None = None,
    ) -> tuple[numpy.ndarray, Path] | None:
        if require_new and not self._server_fits_is_new(
            macie,
            before_name=before_name,
            before_mtime=before_mtime,
            already_seen=already_seen,
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
        if already_seen is not None and filename in already_seen:
            return None
        if (
            require_new
            and before_name
            and filename == before_name
            and already_seen is not None
            and len(already_seen) > 0
        ):
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
                # Latch GUI DIT/mode before arming continuous acquires.
                self._apply_exposure_settings(self._macie)
                # Live arms a single-ramp session (nseq=1) and keeps GigE open.
                self._macie.start_continuous_acquisition()
                QTimer.singleShot(0, self._activate_live_ui)
                self.status_updated.emit(
                    "Live acquiring… (1 ramp/frame, GigE keep-alive)"
                )
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

    def use_as_background(self) -> None:
        """Store the currently displayed image as the background (no shutter move)."""
        frame = self._frame_from_display_mode()
        if frame is None:
            loaded = self._load_latest_frame()
            if loaded is None:
                self._on_operation_failed("No FITS frame available for background")
                return
            frame, _path = loaded
            frame = self._frame_from_display_mode() or frame
        self._store_background_frame(frame)
        self._set_status("Background stored")

    def take_background(self) -> None:
        """Alias kept for older call sites / UI hooks."""
        self.use_as_background()

    def _on_background_ready(self) -> None:
        if self.ui is None:
            return
        self.ui.checkBox_substract_background.setEnabled(True)
        self.ui.checkBox_substract_background.setChecked(True)
        self._refresh_display()

    def _store_background_frame(self, frame) -> None:
        self._background = numpy.asarray(frame, dtype=numpy.float32).copy()
        self.background_ready.emit()

    def _ensure_shutters(self):
        if self._opcua_conn is None:
            raise RuntimeError("OPC UA connection is not available for shutters")
        if self._shutters is None:
            from nottcontrol.components.shutter import Shutter

            self._shutters = [
                Shutter(self._opcua_conn, prefix, name)
                for prefix, name in MACIE_SHUTTER_NODES
            ]
        return self._shutters

    def _shutter_states_summary(self, shutters) -> str:
        parts = []
        for shutter in shutters:
            try:
                parts.append(f"{shutter.name}={shutter.get_hardware_state()}")
            except Exception as exc:
                parts.append(f"{shutter.name}=error({exc})")
        return ", ".join(parts)

    def _shutters_all_closed(self, shutters) -> bool:
        return all(shutter.is_closed for shutter in shutters)

    def _shutters_all_open(self, shutters) -> bool:
        return all(shutter.is_open for shutter in shutters)

    def _drive_shutters_to_state(
        self,
        shutters,
        *,
        closed: bool,
        timeout_s: float = MACIE_SHUTTER_WAIT_TIMEOUT_S,
    ) -> None:
        """Command all shutters, wait until motors stand, then verify Closed/Open."""
        target = "Closed" if closed else "Open"
        commands = []
        for shutter in shutters:
            pos = shutter._close_pos if closed else shutter._open_pos
            # Skip move if already at the requested end-stop.
            try:
                if closed and shutter.is_closed:
                    continue
                if not closed and shutter.is_open:
                    continue
            except Exception:
                pass
            cmd = shutter.command_move_absolute(pos)
            cmd.execute()
            commands.append((shutter, cmd))

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            moving = False
            for _shutter, cmd in commands:
                try:
                    if not cmd.check_progress():
                        moving = True
                        break
                except Exception:
                    moving = True
                    break
            if not moving:
                try:
                    if closed and self._shutters_all_closed(shutters):
                        return
                    if not closed and self._shutters_all_open(shutters):
                        return
                except Exception:
                    pass
            time.sleep(0.15)

        raise TimeoutError(
            f"Timed out waiting for shutters to be {target}: "
            f"{self._shutter_states_summary(shutters)}"
        )

    def _require_shutters_closed(self, shutters) -> None:
        if not self._shutters_all_closed(shutters):
            raise RuntimeError(
                "Shutters are not Closed — aborting background acquire "
                f"({self._shutter_states_summary(shutters)})"
            )

    def _require_shutters_open(self, shutters) -> None:
        if not self._shutters_all_open(shutters):
            raise RuntimeError(
                "Shutters are not Open after Take Background "
                f"({self._shutter_states_summary(shutters)})"
            )

    def _acquire_single_frame_for_background(self, macie):
        """Run one acquire (nseq forced to 1) and return the science frame."""
        from nottcontrol.camera.macie.macie_interface import ZMQ_ACQUIRE_TIMEOUT_MS

        exposure = self._apply_exposure_settings(macie)
        try:
            ncoadds = int(exposure.get("ncoadds", 1))
        except (TypeError, ValueError):
            ncoadds = 1
        # Background darks only need one ramp.
        try:
            save, _ncoadds, _nseq, ngroups, nreads, ndrops, nresets = (
                macie.read_exposure_settings()
            )
            macie.exposure_settings(
                save, ncoadds, 1, ngroups, nreads, ndrops, nresets
            )
        except Exception:
            pass
        nseq = 1
        keep_files = self._save_image_enabled()
        self._fits_dir_ok = None
        self._arm_frame_timing("Take Background")

        if not keep_files:
            preview = self._preview_fits_path()
            try:
                before_mtime = preview.stat().st_mtime if preview.is_file() else 0.0
            except OSError:
                before_mtime = 0.0
            result = macie.acquire()
            if result.frame is not None:
                return numpy.asarray(result.frame, dtype=numpy.float32)
            frame, _path = self._wait_for_preview_fits(
                preview,
                before_mtime=before_mtime,
                timeout_s=fits_wait_timeout_s(
                    float(exposure["execution_s"]),
                    ncoadds=ncoadds,
                    nseq=nseq,
                    margin_s=MACIE_FITS_WAIT_MARGIN_S,
                    maximum_s=(ZMQ_ACQUIRE_TIMEOUT_MS / 1000.0)
                    + MACIE_FITS_WAIT_MARGIN_S,
                ),
            )
            if frame is None:
                raise RuntimeError(self._missing_fits_status())
            return numpy.asarray(frame, dtype=numpy.float32)

        before_mtime, before_name = self._fits_snapshot_before_acquire(macie)
        wait_timeout_s = fits_wait_timeout_s(
            float(exposure["execution_s"]),
            ncoadds=ncoadds,
            nseq=nseq,
            margin_s=MACIE_FITS_WAIT_MARGIN_S,
            maximum_s=(ZMQ_ACQUIRE_TIMEOUT_MS / 1000.0) + MACIE_FITS_WAIT_MARGIN_S,
        )
        result = macie.acquire()
        ramp_paths, frame, preview_path = self._wait_for_acquire_frames(
            before_mtime,
            macie,
            before_name=before_name,
            expected_count=1,
            timeout_s=wait_timeout_s,
            display_each=False,
        )
        if frame is not None:
            return numpy.asarray(frame, dtype=numpy.float32)
        if result.frame is not None:
            return numpy.asarray(result.frame, dtype=numpy.float32)
        raise RuntimeError(self._missing_fits_status())

    def acquire_background(self) -> None:
        """Close shutters, acquire a dark, store as background, re-open shutters."""
        if self._live_active:
            self._on_operation_failed("Stop live mode before taking background")
            return
        if self._opcua_conn is None:
            self._on_operation_failed(
                "Take Background requires OPC UA (open H2RG from the main GUI)"
            )
            return
        if not self._initialized:
            self._on_operation_failed("Initialize the camera before taking background")
            return

        def operation() -> None:
            shutters = self._ensure_shutters()
            reopen_error: Exception | None = None
            background_stored = False
            try:
                self.status_updated.emit("Take Background: closing shutters…")
                self._drive_shutters_to_state(shutters, closed=True)
                self._require_shutters_closed(shutters)
                self.status_updated.emit(
                    "Take Background: shutters Closed — acquiring…"
                )
                macie = self._ensure_macie()
                frame = self._acquire_single_frame_for_background(macie)
                self._background = numpy.asarray(frame, dtype=numpy.float32).copy()
                background_stored = True
                self._frame_timing_status = "Background stored (shutters Closed)"
                self.frame_ready.emit(self._background)
                self.background_ready.emit()
            finally:
                try:
                    self.status_updated.emit("Take Background: opening shutters…")
                    self._drive_shutters_to_state(shutters, closed=False)
                    self._require_shutters_open(shutters)
                except Exception as exc:
                    reopen_error = exc
            if reopen_error is not None:
                prefix = (
                    "Background stored, but "
                    if background_stored
                    else "Take Background failed, and "
                )
                raise RuntimeError(f"{prefix}re-opening shutters failed: {reopen_error}")
            self.status_updated.emit("Background stored — shutters Open")

        self._run_macie_operation(
            "Take Background",
            operation,
            status="Taking background…",
        )

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

    def _emit_acquire_preview(
        self,
        path: Path,
        *,
        index: int,
        expected_count: int,
    ) -> numpy.ndarray | None:
        """Load *path* (off GUI) and queue a lightweight paint if new."""
        with self._acquire_preview_lock:
            displayed = self._acquire_previewed_names
            if path.name in displayed:
                return None
            try:
                if not path.is_file():
                    return None
                data, header = load_fits_data(path)
                frame = science_image_from_cube(
                    data,
                    header,
                    reduction=self._acquire_preview_reduction,  # type: ignore[arg-type]
                    fowler_pairs=self._acquire_preview_fowler,
                )
            except Exception as exc:
                print(f"H2RG acquire preview skipped {path.name}: {exc}")
                return None
            displayed.add(path.name)
            status = f"Acquire: frame {index}/{expected_count} — {path.name}"
        frame = numpy.asarray(frame, dtype=numpy.float32)
        self.acquire_preview_frame.emit(frame, status)
        return frame

    def _poll_acquire_previews(
        self,
        before_mtime: float,
        before_name: str | None,
        expected_count: int,
        stop_event: threading.Event,
    ) -> None:
        """While acquire() runs, show each new local FITS as soft-SC writes it.

        Must not call macie/ZMQ: acquire() holds the client lock until soft-SC
        finishes, so any get_save_dir() here would stall until the end.
        """
        while not stop_event.wait(0.15):
            if not self._local_fits_accessible(allow_probe=True):
                continue
            for path in self._collect_new_ramp_paths(
                before_mtime, before_name=before_name
            ):
                self._emit_acquire_preview(
                    path,
                    index=len(self._acquire_previewed_names) + 1,
                    expected_count=expected_count,
                )
            if len(self._acquire_previewed_names) >= expected_count:
                break

    def _display_acquire_preview(self, frame, status: str = "") -> None:
        """Paint one Acquire frame + ROI plots (GUI thread; no processEvents)."""
        self._ensure_image_view()
        if self.image is None or frame is None:
            return
        frame = numpy.asarray(frame, dtype=numpy.float32)
        self._current_frame = frame
        # Prefer the 2D plane we were given (avoid restamping a cube mid-sequence).
        display = frame
        if (
            self.ui is not None
            and self.ui.checkBox_substract_background.isChecked()
            and self._background is not None
            and self._background.shape == frame.shape
        ):
            display = frame - self._background
        display = numpy.ascontiguousarray(display, dtype=numpy.float32)
        if self._autoscale_enabled():
            self.image.setImage(display, autoLevels=True)
        else:
            levels = self._read_level_fields() or self._manual_levels
            if levels is not None:
                self._manual_levels = levels
                self.image.setImage(display, autoLevels=False, levels=levels)
            else:
                self.image.setImage(display, autoLevels=False)
        if status:
            self._set_status(status)
        # Sync ROI numbers + plots each frame (natural soft-SC spacing is fine).
        self._update_roi_values(display, record=True)
        self._refresh_roi_plots(force=True)

    def _wait_for_acquire_frames(
        self,
        before_mtime: float,
        macie,
        *,
        before_name: str | None = None,
        expected_count: int = 1,
        timeout_s: float = 30.0,
        display_each: bool = False,
    ) -> tuple[list[Path], numpy.ndarray | None, Path | None]:
        import time

        self._sync_save_dir_from_server(macie)
        deadline = time.monotonic() + timeout_s
        seen: dict[str, Path] = {}
        zmq_seen: set[str] = set()
        last_frame: numpy.ndarray | None = None
        server_path_checked_at = 0.0
        stable_since: float | None = None

        def preview_seen() -> None:
            nonlocal last_frame
            if not display_each:
                return
            displayed = self._acquire_previewed_names
            ordered = sorted(
                seen.values(),
                key=lambda path: (
                    path.stat().st_mtime if path.exists() else 0.0,
                    path.name.lower(),
                ),
            )
            for path in ordered:
                frame = self._emit_acquire_preview(
                    path,
                    index=len(displayed) + 1,
                    expected_count=expected_count,
                )
                if frame is not None:
                    last_frame = frame

        while time.monotonic() < deadline:
            for path in self._collect_new_ramp_paths(
                before_mtime, before_name=before_name
            ):
                seen[path.name] = path
            preview_seen()

            local_ok = self._local_fits_accessible(allow_probe=True)
            # ZMQ fetch when the configured local fits_directory is missing *or*
            # accessible but empty/stale (common when MACIE writes under ~/…/YYYYMMDD
            # while fits_directory points at a different SMB share).
            if not local_ok or not seen:
                now = time.monotonic()
                if now - server_path_checked_at >= 1.0:
                    server_path_checked_at = now
                    if self._server_fits_is_new(
                        macie,
                        before_name=before_name,
                        before_mtime=before_mtime,
                        already_seen=set(seen) | zmq_seen,
                    ):
                        self.status_updated.emit("Fetching FITS from server…")
                        fetched = self._fetch_fits_from_server(
                            macie,
                            before_mtime=before_mtime,
                            before_name=before_name,
                            require_new=True,
                            already_seen=set(seen) | zmq_seen,
                        )
                        if fetched is not None:
                            _frame, path = fetched
                            seen[path.name] = path
                            zmq_seen.add(path.name)
                            before_name = path.name
                            preview_seen()
                if len(seen) >= expected_count:
                    break
            if local_ok and len(seen) >= expected_count:
                stable_since = None
                break
            elif local_ok and seen and expected_count <= 1:
                # Single-frame acquire: stop once the first new file looks stable.
                if stable_since is None:
                    stable_since = time.monotonic()
                elif time.monotonic() - stable_since >= 1.0:
                    break
            else:
                # Still waiting for more of the expected multi-frame set.
                stable_since = None

            now = time.monotonic()
            if local_ok:
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
                        preview_seen()
            time.sleep(0.2)

        ramp_paths = sorted(
            seen.values(),
            key=lambda path: (
                path.stat().st_mtime if path.exists() else 0.0,
                path.name.lower(),
            ),
        )
        if not ramp_paths:
            # Acquire finished but SMB never showed the file — pull newest over ZMQ
            # even if the basename matches the pre-acquire snapshot.
            self.status_updated.emit("Fetching FITS from server…")
            fetched = self._fetch_fits_from_server(
                macie,
                before_mtime=before_mtime,
                before_name=before_name,
                require_new=False,
                already_seen=zmq_seen,
            )
            if fetched is not None:
                _frame, path = fetched
                ramp_paths = [path]

        if not ramp_paths:
            return [], None, None

        preview_seen()
        preview_path = ramp_paths[-1]
        if display_each and last_frame is not None and preview_path.name in getattr(
            self, "_acquire_previewed_names", set()
        ):
            try:
                if preview_path.is_file():
                    return ramp_paths, self._load_fits_from_path(preview_path), preview_path
            except Exception:
                return ramp_paths, last_frame, preview_path
            return ramp_paths, last_frame, preview_path

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
        try:
            self._last_fits_mtime = path.stat().st_mtime
        except OSError:
            pass
        return self._store_raw_fits(data, header)

    def _load_live_frame(
        self, macie
    ) -> tuple[numpy.ndarray, Path] | None:
        """Return the next ramp FITS written since the last displayed frame.

        Prefer a local directory scan so Live display does not block on the same
        ZMQ socket used by continuous acquire.
        """
        before_mtime = self._last_fits_mtime
        before_name = self._last_loaded_basename

        if not self._save_image_enabled():
            preview = self._preview_fits_path()
            try:
                if not preview.is_file():
                    return None
                mtime = preview.stat().st_mtime
            except OSError:
                return None
            if before_name == preview.name and mtime <= before_mtime:
                return None
            try:
                frame = self._load_fits_from_path(preview)
                self._last_fits_path = None
                return frame, preview
            except Exception as exc:
                print(f"H2RG live preview skipped: {exc}")
                return None

        if self._local_fits_accessible(allow_probe=True):
            # Prefer the newest pending ramp so Live stays on the latest frame
            # when the poller falls behind a burst of acquires.
            new_paths = list_new_ramp_fits_in_dir(
                self._save_dir,
                before_mtime=before_mtime,
                before_name=before_name,
                dir_ok=True,
            )
            for path in reversed(new_paths):
                if path.name == "preview.fits":
                    continue
                try:
                    frame = self._load_fits_from_path(path)
                    self._stamp_ramp_fits_headers(path)
                    return frame, path
                except Exception as exc:
                    print(f"H2RG live skipped unreadable FITS {path.name}: {exc}")
            # Local share is available — wait for the next poll instead of
            # contending with continuous acquire on the ZMQ socket.
            return None

        fetched = self._fetch_fits_from_server(
            macie,
            before_mtime=before_mtime,
            before_name=before_name,
            require_new=True,
        )
        if fetched is not None:
            frame, path = fetched
            if path.name != "preview.fits":
                self._stamp_ramp_fits_headers(path)
            return frame, path
        return None

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
            return self._fetch_fits_from_server(
                macie,
                before_mtime=0.0 if force else self._last_fits_mtime,
                before_name=None if force else self._last_loaded_basename,
                require_new=not force,
            )

        path = self._newest_fits_file(allow_probe=True)
        if path is None and macie is not None:
            path = self._resolve_server_fits_path(macie)
        if path is None:
            if force and macie is not None:
                return self._fetch_fits_from_server(macie, require_new=False)
            return None
        try:
            mtime = path.stat().st_mtime
        except OSError:
            if macie is not None:
                return self._fetch_fits_from_server(
                    macie,
                    before_mtime=0.0 if force else self._last_fits_mtime,
                    before_name=None if force else self._last_loaded_basename,
                    require_new=not force,
                )
            return None
        if (
            not force
            and path.name == self._last_loaded_basename
            and mtime <= self._last_fits_mtime
        ):
            if macie is not None:
                return self._fetch_fits_from_server(
                    macie,
                    before_mtime=self._last_fits_mtime,
                    before_name=self._last_loaded_basename,
                    require_new=True,
                )
            return None
        try:
            return self._load_fits_from_path(path), path
        except OSError:
            if macie is not None:
                return self._fetch_fits_from_server(
                    macie,
                    before_mtime=0.0 if force else self._last_fits_mtime,
                    before_name=None if force else self._last_loaded_basename,
                    require_new=not force,
                )
            return None

    def _refresh_display(self) -> None:
        if self._current_frame is not None or self._raw_fits_cube is not None:
            self._display_frame()

    def _display_frame(self, frame: numpy.ndarray | None = None) -> None:
        self._ensure_image_view()
        if self.image is None:
            return
        is_new_frame = frame is not None
        if frame is not None:
            self._current_frame = frame
        self._update_central_value(self._current_frame)
        display = self._build_display_frame()
        if display is None:
            self._central_value = None
            self._sync_cursor_readout_label()
            return

        # Contiguous float32 avoids large paint buffers / exotic dtypes under VNC.
        display = numpy.ascontiguousarray(display, dtype=numpy.float32)

        self.setUpdatesEnabled(False)
        try:
            if self._autoscale_enabled():
                self.image.setImage(display, autoLevels=True)
                self._sync_level_fields_from_image()
            else:
                levels = self._read_level_fields() or self._manual_levels
                if levels is not None:
                    self._manual_levels = levels
                    self.image.setImage(
                        display, autoLevels=False, levels=levels
                    )
                else:
                    self.image.setImage(display, autoLevels=False)
                    self._sync_level_fields_from_image()
            self._update_roi_overlays()
        finally:
            self.setUpdatesEnabled(True)

        if is_new_frame:
            if self._frame_timing_skip_report:
                self._frame_timing_skip_report = False
            else:
                self._report_frame_timing()

        # Defer ROI panel/plot updates so they don't nest QGraphicsScene paints.
        self._schedule_roi_update(display, record=is_new_frame)
        self._layout_image_frame()
        self._sync_cursor_readout_label()
        # Skip during Acquire: next_fits_frame_number rglob's the save tree and
        # freezes the GUI so multi-frame previews never paint.
        if not self._macie_operation_busy:
            self._update_next_frame_number()

    def get_dashboard_status(self) -> dict[str, object]:
        """Fast snapshot for the main Camera panel.

        Must never block on MACIE ZMQ or SMB rglob: the main GUI timer calls
        this on the Qt GUI thread. During Acquire the ZMQ lock is held for the
        whole soft-SC sequence, so get_power() would freeze paints until the
        end (stall then burst).
        """
        utc_day = datetime.now(timezone.utc).strftime("%Y%m%d")
        connected = self._macie is not None
        live = bool(self._live_active)
        acquiring = bool(self._macie_operation_busy) and not live

        frame = self._current_frame
        if frame is not None and getattr(frame, "ndim", 0) >= 2:
            frame_size = f"{int(frame.shape[1])} × {int(frame.shape[0])}"
        else:
            frame_size = "—"

        # Skip directory walks while busy; reuse the last idle count.
        files_today = self._cached_files_today
        if not self._macie_operation_busy and not live:
            try:
                files_today = sum(
                    1
                    for path in list_ramp_fits_in_dir(
                        self._save_dir, dir_ok=self._fits_dir_ok
                    )
                    if utc_day in path.name
                )
                self._cached_files_today = files_today
            except Exception:
                files_today = self._cached_files_today

        return {
            "mode": "H2RG",
            "connected": connected,
            "recording": False,
            "acquiring": acquiring,
            "live": live,
            # Do not call macie.get_power() here — it needs the ZMQ lock.
            "powered": None,
            "files_today": files_today,
            "utc_day": utc_day,
            "frame_size": frame_size,
            "save_dir": str(self._save_dir),
        }

    def closeEvent(self, event) -> None:
        if self._shutting_down:
            event.accept()
            return
        self._shutting_down = True

        self._stop_gui_services()
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
