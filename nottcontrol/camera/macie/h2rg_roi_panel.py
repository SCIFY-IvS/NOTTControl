"""H2RG ROI brightness panel, Redis keys, and time/1D plots."""

from __future__ import annotations

import sys
from collections import deque
from datetime import datetime, timezone

import numpy
import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from nottcontrol.camera.infratec.utils.utils import BrightnessResults
from nottcontrol.theme import PANEL_BUTTON_STYLE
from nottcontrol.ui_scale import scaled, scaled_font_pt

ROI_COUNT = 10
ROI_COLORS = (
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

# Redis TimeSeries base keys — distinct from Infratec roi1…roi10.
REDIS_KEY_PREFIX = "h2rg_roi"


def redis_key_for_roi(index: int) -> str:
    return f"{REDIS_KEY_PREFIX}{index}"


def roi_profile_1d(region: numpy.ndarray) -> numpy.ndarray:
    """Collapse a 2D ROI to a 1D profile (mean across the narrow axis)."""
    data = numpy.asarray(region, dtype=numpy.float64)
    if data.ndim != 2 or data.size == 0:
        return numpy.asarray([], dtype=numpy.float64)
    height, width = data.shape
    if width <= height:
        return numpy.mean(data, axis=1)
    return numpy.mean(data, axis=0)


def extract_roi_region(
    frame: numpy.ndarray, roi: tuple[int, int, int, int]
) -> numpy.ndarray | None:
    height, width = frame.shape[:2]
    x, y, w, h = roi
    x_end = min(width, x + w)
    y_end = min(height, y + h)
    if x >= width or y >= height or x_end <= x or y_end <= y:
        return None
    return frame[y:y_end, x:x_end]


def map_roi_full_to_image(
    roi: tuple[int, int, int, int],
    *,
    origin_x: int,
    origin_y: int,
    image_w: int,
    image_h: int,
    pad_top: int = 0,
    window_x1: int | None = None,
    window_x2: int | None = None,
    window_y1: int | None = None,
    window_y2: int | None = None,
) -> tuple[int, int, int, int] | None:
    """Map a full-frame ROI into the current image; None if no overlap.

    *origin_x* / *origin_y* are the full-frame coordinates of image pixel (0, 0)
    for science content (before *pad_top*). Soft-SC middle stripes prepend
    *pad_top* reference rows, so science row *origin_y* lands at image y=*pad_top*.

    Optional *window_** (inclusive full-frame bounds) reject ROIs that miss the
    programmed science window even if image-local clipping would still hit pixels.
    """
    fx, fy, fw, fh = (int(v) for v in roi)
    if None not in (window_x1, window_x2, window_y1, window_y2):
        if (
            fx + fw - 1 < int(window_x1)
            or fx > int(window_x2)
            or fy + fh - 1 < int(window_y1)
            or fy > int(window_y2)
        ):
            return None
    ix = fx - int(origin_x)
    iy = fy - int(origin_y) + int(pad_top)
    x0 = max(0, ix)
    y0 = max(0, iy)
    x1 = min(int(image_w), ix + max(1, fw))
    y1 = min(int(image_h), iy + max(1, fh))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1 - x0, y1 - y0


def map_roi_image_to_full(
    roi: tuple[int, int, int, int],
    *,
    origin_x: int,
    origin_y: int,
    pad_top: int = 0,
) -> tuple[int, int, int, int]:
    """Map an image-local ROI back to full-frame detector coordinates."""
    ix, iy, iw, ih = (int(v) for v in roi)
    return (
        ix + int(origin_x),
        iy - int(pad_top) + int(origin_y),
        max(1, iw),
        max(1, ih),
    )


def remap_rois_to_image(
    rois: dict[int, tuple[int, int, int, int]],
    *,
    origin_x: int,
    origin_y: int,
    image_w: int,
    image_h: int,
    pad_top: int = 0,
    window_x1: int | None = None,
    window_x2: int | None = None,
    window_y1: int | None = None,
    window_y2: int | None = None,
) -> dict[int, tuple[int, int, int, int]]:
    """Return only ROIs that intersect the current image, in image coords."""
    mapped: dict[int, tuple[int, int, int, int]] = {}
    for index, geom in rois.items():
        local = map_roi_full_to_image(
            geom,
            origin_x=origin_x,
            origin_y=origin_y,
            image_w=image_w,
            image_h=image_h,
            pad_top=pad_top,
            window_x1=window_x1,
            window_x2=window_x2,
            window_y1=window_y1,
            window_y2=window_y2,
        )
        if local is not None:
            mapped[index] = local
    return mapped


def compute_roi_brightness(
    frame: numpy.ndarray,
    rois: dict[int, tuple[int, int, int, int]],
    *,
    origin_x: int = 0,
    origin_y: int = 0,
    pad_top: int = 0,
    window_x1: int | None = None,
    window_x2: int | None = None,
    window_y1: int | None = None,
    window_y2: int | None = None,
) -> tuple[dict[int, BrightnessResults], dict[int, numpy.ndarray]]:
    """Return per-ROI brightness and cropped regions for configured ROIs.

    *rois* are full-frame detector coordinates. When the frame is a subframe,
    pass the window *origin_* and optional soft-SC *pad_top* so the correct
    detector pixels are sampled. ROIs outside the science window are omitted.
    """
    height, width = frame.shape[:2]
    local_rois = remap_rois_to_image(
        rois,
        origin_x=origin_x,
        origin_y=origin_y,
        image_w=width,
        image_h=height,
        pad_top=pad_top,
        window_x1=window_x1,
        window_x2=window_x2,
        window_y1=window_y1,
        window_y2=window_y2,
    )
    results: dict[int, BrightnessResults] = {}
    regions: dict[int, numpy.ndarray] = {}
    for index, geom in local_rois.items():
        region = extract_roi_region(frame, geom)
        if region is None or region.size == 0:
            continue
        regions[index] = region
        avg = float(numpy.average(region))
        results[index] = BrightnessResults(
            float(numpy.amin(region)),
            float(numpy.amax(region)),
            avg,
            avg * region.shape[0] * region.shape[1],
        )
    return results, regions


def _value_style(row_bg: str = "") -> str:
    from nottcontrol.theme import MONO_FONT, linux_safe_stylesheet

    pt = scaled_font_pt(9)
    return linux_safe_stylesheet(
        f"{row_bg} font: {pt}pt {MONO_FONT}; color: rgb(30, 30, 30);"
    )


def _header_style() -> str:
    from nottcontrol.theme import FONT, linux_safe_stylesheet

    pt = scaled_font_pt(8)
    return linux_safe_stylesheet(
        f"font: 700 {pt}pt {FONT}; color: rgb(90, 90, 90);"
    )


def _title_style() -> str:
    from nottcontrol.theme import FONT, linux_safe_stylesheet

    pt = scaled_font_pt(10)
    return linux_safe_stylesheet(
        f"font: 600 {pt}pt {FONT}; color: rgb(50, 50, 50);"
    )


def _style_light_plot(plot: pg.PlotWidget) -> None:
    plot.setBackground("w")
    item = plot.getPlotItem()
    tick_font = None
    if sys.platform.startswith("linux"):
        # Pixel-size + PreferBitmap avoids conda Qt FreeType SIGSEGV on VNC.
        from nottcontrol.theme import APP_FONT_FAMILY

        tick_font = QFont(APP_FONT_FAMILY)
        tick_font.setPixelSize(11)
        tick_font.setStyleStrategy(QFont.PreferBitmap)
    for name in ("left", "bottom", "right", "top"):
        axis = item.getAxis(name)
        axis.setPen(pg.mkPen(color=(40, 40, 40)))
        axis.setTextPen(pg.mkPen(color=(40, 40, 40)))
        if tick_font is not None:
            axis.setTickFont(tick_font)
    item.showGrid(x=True, y=True, alpha=0.2)


class H2rgRoiRow:
    """One ROI readout row: overlay/Time/1D toggles, min/max/avg."""

    def __init__(
        self,
        parent: QWidget,
        grid: QGridLayout,
        row: int,
        index: int,
        color: QColor,
        deque_length: int = 3600,
    ) -> None:
        self.index = index
        self.name = f"ROI {index}"
        self.db_key = redis_key_for_roi(index)
        self.color = color
        self.max_values: deque[float] = deque(maxlen=deque_length)
        self._row_bg = "background: rgb(248, 250, 251);" if index % 2 == 0 else ""
        row_height = scaled(16)

        self.name_label = QLabel(self.name, parent)
        self.name_label.setFixedHeight(row_height)
        self.name_label.setMinimumWidth(scaled(40))
        self.name_label.setStyleSheet(self._row_bg)

        self.show_checkbox = QCheckBox(parent)
        self.show_checkbox.setToolTip("Show ROI overlay on image")
        self.show_checkbox.setFixedHeight(row_height)
        self.time_plot_checkbox = QCheckBox(parent)
        self.time_plot_checkbox.setToolTip("Plot brightness vs time")
        self.time_plot_checkbox.setFixedHeight(row_height)
        self.profile_plot_checkbox = QCheckBox(parent)
        self.profile_plot_checkbox.setToolTip("Plot 1D profile")
        self.profile_plot_checkbox.setFixedHeight(row_height)

        self.min_label = self._make_value_label(parent, row_height)
        self.max_label = self._make_value_label(parent, row_height)
        self.avg_label = self._make_value_label(parent, row_height)

        grid.addWidget(self.name_label, row, 0)
        grid.addWidget(self.show_checkbox, row, 1, Qt.AlignCenter)
        grid.addWidget(self.time_plot_checkbox, row, 2, Qt.AlignCenter)
        grid.addWidget(self.profile_plot_checkbox, row, 3, Qt.AlignCenter)
        grid.addWidget(self.min_label, row, 4, Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(self.max_label, row, 5, Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(self.avg_label, row, 6, Qt.AlignRight | Qt.AlignVCenter)
        self.set_color(color)

    def _make_value_label(self, parent: QWidget, row_height: int) -> QLabel:
        label = QLabel("—", parent)
        label.setFixedHeight(row_height)
        label.setMinimumWidth(scaled(44))
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setStyleSheet(_value_style(self._row_bg))
        return label

    def set_color(self, color: QColor) -> None:
        self.color = color
        self.name_label.setStyleSheet(
            f"{self._row_bg} color: {color.name()}; font-weight: 600;"
        )

    @staticmethod
    def _format_int(value: float) -> str:
        if not numpy.isfinite(value):
            return "—"
        return str(int(round(value)))

    def set_values(self, result: BrightnessResults | None) -> None:
        if result is None:
            for label in (self.min_label, self.max_label, self.avg_label):
                label.setText("—")
            return
        self.min_label.setText(self._format_int(result.min))
        self.max_label.setText(self._format_int(result.max))
        self.avg_label.setText(self._format_int(result.avg))

    def add_max_value(self, value: float) -> None:
        self.max_values.append(float(value))

    def clear_history(self) -> None:
        self.max_values.clear()


def _build_roi_column(
    parent: QWidget,
    indices: range,
    *,
    deque_length: int,
) -> tuple[QWidget, dict[int, H2rgRoiRow]]:
    host = QWidget(parent)
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(scaled(2))
    grid.setVerticalSpacing(0)

    headers = ("", "On", "T", "1D", "Min", "Max", "Avg")
    for col, text in enumerate(headers):
        label = QLabel(text, host)
        label.setStyleSheet(_header_style())
        label.setFixedHeight(scaled(14))
        label.setAlignment(Qt.AlignCenter if col in (1, 2, 3) else Qt.AlignRight)
        grid.addWidget(label, 0, col)

    rows: dict[int, H2rgRoiRow] = {}
    for row_offset, index in enumerate(indices, start=1):
        color = QColor(ROI_COLORS[(index - 1) % len(ROI_COLORS)])
        rows[index] = H2rgRoiRow(
            host, grid, row_offset, index, color, deque_length=deque_length
        )
    return host, rows


class H2rgRoiPanel(QGroupBox):
    """Per-ROI min/max/avg table in two tight columns (1–5 and 6–10)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        deque_length: int = 3600,
    ) -> None:
        super().__init__("H2RG ROI values", parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        root = QHBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(scaled(8))

        left_host, left_rows = _build_roi_column(
            self, range(1, 6), deque_length=deque_length
        )
        right_host, right_rows = _build_roi_column(
            self, range(6, 11), deque_length=deque_length
        )
        root.addWidget(left_host, stretch=1)
        root.addWidget(right_host, stretch=1)

        self.rows: dict[int, H2rgRoiRow] = {**left_rows, **right_rows}


class H2rgRoiPlots(QWidget):
    """Side-by-side ROI brightness-vs-time and 1D profile plots."""

    def __init__(self, parent: QWidget | None = None, *, graph_height: int = 190) -> None:
        super().__init__(parent)
        strip_h = scaled(max(graph_height, 240))
        self.setFixedHeight(strip_h)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        self.btn_rescale = QPushButton("Rescale Y", self)
        self.btn_rescale.setToolTip("Auto-scale Y on both ROI plots")
        self.btn_rescale.setStyleSheet(PANEL_BUTTON_STYLE)
        self.btn_rescale.setMinimumHeight(scaled(28))
        self.btn_rescale.setFixedWidth(scaled(96))
        self.btn_rescale.clicked.connect(self.rescale_y)
        toolbar.addWidget(self.btn_rescale)
        root.addLayout(toolbar)

        plots = QHBoxLayout()
        plots.setSpacing(scaled(8))

        time_host = QWidget(self)
        time_layout = QVBoxLayout(time_host)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(2)
        time_title = QLabel("ROI brightness vs time", time_host)
        time_title.setStyleSheet(_title_style())
        time_layout.addWidget(time_title)
        axis = pg.DateAxisItem(orientation="bottom")
        self.pw_time = pg.PlotWidget(axisItems={"bottom": axis})
        _style_light_plot(self.pw_time)
        time_item = self.pw_time.getPlotItem()
        time_item.addLegend(offset=(8, 8))
        time_item.setLabel("left", "ROI Brightness [ADU]")
        time_item.setLabel("bottom", "Time [UTC]")
        time_item.enableAutoRange(axis="y", enable=True)
        time_item.enableAutoRange(axis="x", enable=False)
        self._time_curves: dict[int, object] = {}
        time_layout.addWidget(self.pw_time)
        plots.addWidget(time_host, stretch=1)

        profile_host = QWidget(self)
        profile_layout = QVBoxLayout(profile_host)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(2)
        self.profile_title = QLabel("ROI profile — check 1D", profile_host)
        self.profile_title.setStyleSheet(_title_style())
        profile_layout.addWidget(self.profile_title)
        self.pw_profile = pg.PlotWidget()
        _style_light_plot(self.pw_profile)
        profile_item = self.pw_profile.getPlotItem()
        profile_item.addLegend(offset=(8, 8))
        profile_item.setLabel("left", "ROI Brightness [ADU]")
        profile_item.setLabel("bottom", "Pixel index")
        profile_item.enableAutoRange(axis="y", enable=True)
        self._profile_curves: dict[int, object] = {}
        profile_layout.addWidget(self.pw_profile)
        plots.addWidget(profile_host, stretch=1)

        root.addLayout(plots, stretch=1)
        self._timestamps: deque[float] = deque(maxlen=3600)
        self._window_seconds = 60.0

    def set_history_limits(self, *, maxlen: int, window_seconds: float) -> None:
        self._timestamps = deque(self._timestamps, maxlen=maxlen)
        self._window_seconds = float(window_seconds)

    def clear(self) -> None:
        self._timestamps.clear()
        self._clear_plot(self.pw_time)
        self._clear_plot(self.pw_profile)
        self._time_curves.clear()
        self._profile_curves.clear()

    def append_timestamp(self, when: datetime | None = None) -> None:
        stamp = when or datetime.now(timezone.utc).replace(tzinfo=None)
        self._timestamps.append(stamp.timestamp())

    def refresh_time_plot(self, rows: dict[int, H2rgRoiRow]) -> None:
        times = list(self._timestamps)
        if not times:
            self._clear_plot(self.pw_time)
            self._time_curves.clear()
            return
        t0 = times[-1] - self._window_seconds
        plot_item = self.pw_time.getPlotItem()
        active = {
            index: row
            for index, row in rows.items()
            if row.time_plot_checkbox.isChecked() and row.max_values
        }
        for index in list(self._time_curves):
            if index not in active:
                plot_item.removeItem(self._time_curves.pop(index))
        for index, row in active.items():
            ys = list(row.max_values)
            n = min(len(times), len(ys))
            xs = times[-n:]
            ys = ys[-n:]
            mask = [t >= t0 for t in xs]
            xs = [t for t, keep in zip(xs, mask) if keep]
            ys = [y for y, keep in zip(ys, mask) if keep]
            if not xs:
                continue
            pen = pg.mkPen(row.color, width=2)
            curve = self._time_curves.get(index)
            if curve is None:
                curve = self.pw_time.plot(xs, ys, pen=pen, name=row.name)
                self._time_curves[index] = curve
            else:
                curve.setData(xs, ys)
        self.pw_time.setXRange(max(t0, times[0]), times[-1], padding=0.02)
        plot_item.enableAutoRange(axis="y", enable=True)

    def refresh_profile_plot(
        self,
        rows: dict[int, H2rgRoiRow],
        profiles: dict[int, numpy.ndarray] | None,
    ) -> None:
        plot_item = self.pw_profile.getPlotItem()
        if not profiles:
            self._clear_plot(self.pw_profile)
            self._profile_curves.clear()
            self.profile_title.setText("ROI profile — check 1D")
            return
        active = {
            index: rows[index]
            for index in profiles
            if index in rows and rows[index].profile_plot_checkbox.isChecked()
        }
        for index in list(self._profile_curves):
            if index not in active:
                plot_item.removeItem(self._profile_curves.pop(index))
        names: list[str] = []
        for index, row in active.items():
            profile = numpy.asarray(profiles[index], dtype=numpy.float64)
            if profile.size == 0:
                continue
            xs = numpy.arange(profile.size)
            pen = pg.mkPen(row.color, width=2)
            curve = self._profile_curves.get(index)
            if curve is None:
                curve = self.pw_profile.plot(xs, profile, pen=pen, name=row.name)
                self._profile_curves[index] = curve
            else:
                curve.setData(xs, profile)
            names.append(row.name)
        self.profile_title.setText(
            "ROI profile — " + (", ".join(names) if names else "check 1D")
        )
        plot_item.enableAutoRange(axis="y", enable=True)

    def rescale_y(self) -> None:
        for plot in (self.pw_time, self.pw_profile):
            plot.getPlotItem().enableAutoRange(axis="y", enable=True)

    @staticmethod
    def _clear_plot(plot: pg.PlotWidget) -> None:
        plot.clear()
        _style_light_plot(plot)
        plot.getPlotItem().addLegend(offset=(8, 8))
