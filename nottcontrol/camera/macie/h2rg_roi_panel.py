"""H2RG ROI brightness panel, Redis keys, and time/1D plots."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

import numpy
import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
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


def compute_roi_brightness(
    frame: numpy.ndarray,
    rois: dict[int, tuple[int, int, int, int]],
) -> tuple[dict[int, BrightnessResults], dict[int, numpy.ndarray]]:
    """Return per-ROI brightness and cropped regions for configured ROIs."""
    results: dict[int, BrightnessResults] = {}
    regions: dict[int, numpy.ndarray] = {}
    for index, geom in rois.items():
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
    pt = scaled_font_pt(10)
    return f'{row_bg} font: {pt}pt "Consolas", monospace; color: rgb(30, 30, 30);'


def _header_style() -> str:
    pt = scaled_font_pt(9)
    return f'font: 700 {pt}pt "Segoe UI"; color: rgb(90, 90, 90);'


def _title_style() -> str:
    pt = scaled_font_pt(10)
    return f'font: 600 {pt}pt "Segoe UI"; color: rgb(50, 50, 50);'


def _style_light_plot(plot: pg.PlotWidget) -> None:
    plot.setBackground("w")
    item = plot.getPlotItem()
    for name in ("left", "bottom", "right", "top"):
        axis = item.getAxis(name)
        axis.setPen(pg.mkPen(color=(40, 40, 40)))
        axis.setTextPen(pg.mkPen(color=(40, 40, 40)))
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
        row_height = scaled(22)

        self.name_label = QLabel(self.name, parent)
        self.name_label.setFixedHeight(row_height)
        self.name_label.setStyleSheet(self._row_bg)

        self.show_checkbox = QCheckBox(parent)
        self.show_checkbox.setToolTip("Show ROI overlay on image")
        self.time_plot_checkbox = QCheckBox(parent)
        self.time_plot_checkbox.setToolTip("Plot brightness vs time")
        self.profile_plot_checkbox = QCheckBox(parent)
        self.profile_plot_checkbox.setToolTip("Plot 1D profile")

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
        label.setMinimumWidth(scaled(54))
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setStyleSheet(_value_style(self._row_bg))
        return label

    def set_color(self, color: QColor) -> None:
        self.color = color
        self.name_label.setStyleSheet(
            f"{self._row_bg} color: {color.name()}; font-weight: 600;"
        )

    def set_values(self, result: BrightnessResults | None) -> None:
        if result is None:
            for label in (self.min_label, self.max_label, self.avg_label):
                label.setText("—")
            return
        self.min_label.setText(f"{result.min:.1f}")
        self.max_label.setText(f"{result.max:.1f}")
        self.avg_label.setText(f"{result.avg:.1f}")

    def add_max_value(self, value: float) -> None:
        self.max_values.append(float(value))

    def clear_history(self) -> None:
        self.max_values.clear()


class H2rgRoiPanel(QGroupBox):
    """Per-ROI min/max/avg table with overlay / Time / 1D toggles."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        deque_length: int = 3600,
    ) -> None:
        super().__init__("H2RG ROI values", parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 12, 8, 8)
        grid.setHorizontalSpacing(scaled(3))
        grid.setVerticalSpacing(0)

        headers = ("", "On", "T", "1D", "Min", "Max", "Avg")
        for col, text in enumerate(headers):
            label = QLabel(text, self)
            label.setStyleSheet(_header_style())
            label.setAlignment(Qt.AlignCenter if col in (1, 2, 3) else Qt.AlignRight)
            grid.addWidget(label, 0, col)

        self.rows: dict[int, H2rgRoiRow] = {}
        for index in range(1, ROI_COUNT + 1):
            color = QColor(ROI_COLORS[(index - 1) % len(ROI_COLORS)])
            self.rows[index] = H2rgRoiRow(
                self, grid, index, index, color, deque_length=deque_length
            )


class H2rgRoiPlots(QWidget):
    """Side-by-side ROI brightness-vs-time and 1D profile plots."""

    def __init__(self, parent: QWidget | None = None, *, graph_height: int = 190) -> None:
        super().__init__(parent)
        strip_h = scaled(max(graph_height, 180))
        self.setFixedHeight(strip_h)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        self.btn_rescale = QPushButton("Rescale Y", self)
        self.btn_rescale.setToolTip("Auto-scale Y on both ROI plots")
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
        time_item.setLabel("left", "ROI brightness [ADU]")
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
        profile_item.setLabel("left", "ADU")
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
