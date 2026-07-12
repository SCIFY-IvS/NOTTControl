from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

TEAL = (50, 129, 140)

TIMESPAN_OPTIONS: tuple[tuple[str, int], ...] = (
    ("5 min", 5),
    ("10 min", 10),
    ("30 min", 30),
    ("1 h", 60),
    ("3 h", 180),
    ("24 h", 24 * 60),
)

PLOT_COLORS = [
    (0, 102, 204),
    (0, 140, 70),
    (200, 120, 0),
    (180, 60, 60),
    (120, 80, 180),
    (80, 160, 160),
    (200, 50, 0),
    (100, 100, 100),
]

TEMP_CHART_Y_MIN = 0.0
TEMP_CHART_Y_MAX = 300.0
PRESSURE_CHART_LOG_Y_MIN = -8.0  # log10(mbar)
PRESSURE_CHART_LOG_Y_MAX = 3.0   # log10(1000 mbar)


class PressureLogAxis(pg.AxisItem):
    """Left axis with log10 pressure coordinates labeled in mbar."""

    def tickStrings(self, values, scale, spacing):
        labels = []
        for value in values:
            if value < PRESSURE_CHART_LOG_Y_MIN - 0.5 or value > PRESSURE_CHART_LOG_Y_MAX + 0.5:
                labels.append("")
                continue
            pressure_mbar = 10.0 ** value
            if pressure_mbar < 1e-4:
                labels.append(f"{pressure_mbar:.0e}")
            elif pressure_mbar < 1.0:
                labels.append(f"{pressure_mbar:.0e}")
            elif pressure_mbar < 10.0:
                labels.append(f"{pressure_mbar:.2g}")
            else:
                labels.append(f"{pressure_mbar:.0f}")
        return labels


def _styled_legend(plot: pg.PlotWidget) -> pg.LegendItem:
    legend = plot.addLegend(offset=(12, 12))
    legend.setBrush(pg.mkBrush(255, 255, 255, 240))
    legend.setPen(pg.mkPen(190, 190, 190, 255, width=1))
    legend.labelTextSize = "9pt"
    return legend


@dataclass(frozen=True)
class SeriesConfig:
    redis_key: str
    label: str


def _downsample(
    times: list[float], values: list[float], max_points: int = 800
) -> tuple[np.ndarray, np.ndarray]:
    if len(times) <= max_points:
        return np.asarray(times, dtype=float), np.asarray(values, dtype=float)
    indices = np.linspace(0, len(times) - 1, max_points, dtype=int)
    indices = np.unique(indices)
    return np.asarray(times, dtype=float)[indices], np.asarray(values, dtype=float)[indices]


class CryoRedisChart(QWidget):
    """Single pyqtgraph chart for Redis TimeSeries history."""

    def __init__(
        self,
        title: str,
        y_label: str,
        parent=None,
        *,
        y_min: float | None = None,
        y_max: float | None = None,
        log_pressure: bool = False,
    ):
        super().__init__(parent)
        self._y_min = y_min
        self._y_max = y_max
        self._log_pressure = log_pressure

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._title = title
        plot_kwargs = {}
        if log_pressure:
            plot_kwargs["axisItems"] = {"left": PressureLogAxis(orientation="left")}
        self._plot = pg.PlotWidget(**plot_kwargs)
        self._plot.setBackground("w")
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        self._plot.setLabel("left", y_label)
        self._plot.setLabel("bottom", "Hours from range start")
        _styled_legend(self._plot)
        self._plot.setTitle(self._title, color=TEAL, size="12pt")
        layout.addWidget(self._plot)
        self._apply_y_limits()

    def _apply_y_limits(self) -> None:
        if self._y_min is None or self._y_max is None:
            return
        view_box = self._plot.getViewBox()
        view_box.enableAutoRange(axis="y", enable=False)
        self._plot.setYRange(self._y_min, self._y_max, padding=0)
        if not self._log_pressure:
            view_box.setLimits(
                yMin=self._y_min,
                yMax=self._y_max,
                minYRange=self._y_max - self._y_min,
                maxYRange=self._y_max - self._y_min,
            )

    def update_series(
        self,
        series_data: list[tuple[SeriesConfig, list[float], list[float]]],
        window_start: datetime,
        window_hours: float,
    ) -> None:
        self._plot.clear()
        _styled_legend(self._plot)
        self._plot.setTitle(self._title, color=TEAL, size="12pt")
        start_ts = window_start.timestamp()

        has_data = False
        for index, (series, times, values) in enumerate(series_data):
            if not times:
                continue
            has_data = True
            x_hours = np.asarray([(t - start_ts) / 3600.0 for t in times], dtype=float)
            y_values = np.asarray(values, dtype=float)
            if self._log_pressure:
                valid = y_values > 0
                x_hours = x_hours[valid]
                y_values = np.log10(y_values[valid])
                if y_values.size == 0:
                    continue
            x_hours, y_values = _downsample(x_hours.tolist(), y_values.tolist())
            color = PLOT_COLORS[index % len(PLOT_COLORS)]
            pen = pg.mkPen(color=color, width=2)
            self._plot.plot(
                x_hours,
                y_values,
                pen=pen,
                name=series.label,
            )

        if not has_data:
            self._plot.setTitle(
                f"{self._title} — no Redis data in range",
                color=TEAL,
                size="12pt",
            )

        view_box = self._plot.getViewBox()
        view_box.enableAutoRange(axis="x", enable=False)
        self._plot.setXRange(0.0, window_hours, padding=0)
        self._apply_y_limits()


class CryoHistoryPanel(QWidget):
    """Timespan selector plus temperature and pressure history charts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._temp_series: list[SeriesConfig] = []
        self._pressure_series: list[SeriesConfig] = []
        self._redis_client = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("History timespan:"))
        self._timespan_combo = QComboBox()
        for label, minutes in TIMESPAN_OPTIONS:
            self._timespan_combo.addItem(label, minutes)
        self._timespan_combo.setCurrentIndex(2)
        self._timespan_combo.currentIndexChanged.connect(self.refresh)
        selector_row.addWidget(self._timespan_combo)
        selector_row.addStretch(1)
        self._updated_label = QLabel("Updated: —")
        self._updated_label.setStyleSheet(
            'font: 9pt "Segoe UI"; color: rgb(100, 100, 100);'
        )
        selector_row.addWidget(self._updated_label)
        layout.addLayout(selector_row)

        self._temp_chart = CryoRedisChart(
            "Temperature history",
            "Temperature (K)",
            y_min=TEMP_CHART_Y_MIN,
            y_max=TEMP_CHART_Y_MAX,
        )
        self._pressure_chart = CryoRedisChart(
            "Pressure history",
            "Pressure (mbar)",
            y_min=PRESSURE_CHART_LOG_Y_MIN,
            y_max=PRESSURE_CHART_LOG_Y_MAX,
            log_pressure=True,
        )
        layout.addWidget(self._temp_chart, stretch=1)
        layout.addWidget(self._pressure_chart, stretch=1)

    def configure(
        self,
        redis_client,
        temp_series: list[SeriesConfig],
        pressure_series: list[SeriesConfig],
    ) -> None:
        self._redis_client = redis_client
        self._temp_series = temp_series
        self._pressure_series = pressure_series
        self.refresh()

    def selected_minutes(self) -> int:
        minutes = self._timespan_combo.currentData()
        return int(minutes) if minutes is not None else 30

    def refresh(self) -> None:
        if self._redis_client is None:
            return

        minutes = self.selected_minutes()
        window_hours = minutes / 60.0
        window_end = datetime.utcnow()
        window_start = window_end - timedelta(minutes=minutes)
        start_ms = self._redis_client.unix_time_ms(window_start)
        end_ms = self._redis_client.unix_time_ms(window_end)

        self._temp_chart.update_series(
            self._load_series(self._temp_series, start_ms, end_ms),
            window_start,
            window_hours,
        )
        self._pressure_chart.update_series(
            self._load_series(self._pressure_series, start_ms, end_ms),
            window_start,
            window_hours,
        )
        self._updated_label.setText(
            "Updated: "
            f"{window_end.strftime('%H:%M:%S')} UTC  "
            f"({window_start.strftime('%H:%M')} – {window_end.strftime('%H:%M')} UTC)"
        )

    def _load_series(
        self,
        series_configs: list[SeriesConfig],
        start_ms: int,
        end_ms: int,
    ) -> list[tuple[SeriesConfig, list[float], list[float]]]:
        loaded: list[tuple[SeriesConfig, list[float], list[float]]] = []
        for series in series_configs:
            times, values = self._redis_client.fetch_timeseries_range(
                series.redis_key, start_ms, end_ms
            )
            loaded.append((series, times, values))
        return loaded
