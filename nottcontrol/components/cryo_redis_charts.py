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

    def __init__(self, title: str, y_label: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._title = title
        self._plot = pg.PlotWidget()
        self._plot.setBackground("w")
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        self._plot.setLabel("left", y_label)
        self._plot.setLabel("bottom", "Hours from range start")
        self._plot.addLegend(offset=(10, 10))
        self._plot.setTitle(self._title, color=TEAL, size="12pt")
        layout.addWidget(self._plot)

    def update_series(
        self,
        series_data: list[tuple[SeriesConfig, list[float], list[float]]],
        window_start: datetime,
    ) -> None:
        self._plot.clear()
        self._plot.addLegend(offset=(10, 10))
        self._plot.setTitle(self._title, color=TEAL, size="12pt")
        start_ts = window_start.timestamp()

        has_data = False
        for index, (series, times, values) in enumerate(series_data):
            if not times:
                continue
            has_data = True
            x_hours = np.asarray([(t - start_ts) / 3600.0 for t in times], dtype=float)
            y_values = np.asarray(values, dtype=float)
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
        layout.addLayout(selector_row)

        self._temp_chart = CryoRedisChart("Temperature history", "Temperature (K)")
        self._pressure_chart = CryoRedisChart("Pressure history", "Value")
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
        window_end = datetime.utcnow()
        window_start = window_end - timedelta(minutes=minutes)
        start_ms = self._redis_client.unix_time_ms(window_start)
        end_ms = self._redis_client.unix_time_ms(window_end)

        self._temp_chart.update_series(
            self._load_series(self._temp_series, start_ms, end_ms),
            window_start,
        )
        self._pressure_chart.update_series(
            self._load_series(self._pressure_series, start_ms, end_ms),
            window_start,
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
