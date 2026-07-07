from collections import deque

import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QCheckBox, QGridLayout, QLabel, QSizePolicy, QWidget

from nottcontrol.camera.infratec.roi import Roi
from nottcontrol.camera.infratec.utils.utils import BrightnessResults
from nottcontrol.ui_scale import scaled, scaled_font_pt

ROI_COUNT = 10
NAME_WIDTH = 42
PLOT_WIDTH = 22
VALUE_WIDTH = 54
ROW_HEIGHT = 22
HEADER_HEIGHT = 18
PANEL_CHROME_HEIGHT = 30
GRID_H_SPACING = 3
PANEL_SIDE_MARGIN = 14


def _value_style(row_bg: str = "") -> str:
    pt = scaled_font_pt(10)
    return f'{row_bg} font: {pt}pt "Consolas", monospace; color: rgb(30, 30, 30);'


def _header_style() -> str:
    pt = scaled_font_pt(9)
    return f'font: 700 {pt}pt "Segoe UI"; color: rgb(90, 90, 90);'


def header_style() -> str:
    return _header_style()


def roi_panel_height() -> int:
    return scaled(PANEL_CHROME_HEIGHT) + scaled(HEADER_HEIGHT) + ROI_COUNT * scaled(
        ROW_HEIGHT
    )


def roi_panel_width() -> int:
    grid_width = (
        scaled(NAME_WIDTH)
        + scaled(PLOT_WIDTH)
        + scaled(VALUE_WIDTH) * 3
        + scaled(GRID_H_SPACING) * 4
    )
    return grid_width + scaled(PANEL_SIDE_MARGIN) * 2


class RoiWidget:
    """Readout widgets for one ROI row in a shared grid."""

    def __init__(
        self,
        parent: QWidget,
        grid: QGridLayout,
        row: int,
        index: int,
        color: QColor,
        deque_length: int = 6000,
    ) -> None:
        self.name = f"ROI {index}"
        self.db_key = f"roi{index}"
        self.color = color
        self.max_values = deque(maxlen=deque_length)
        self.roi = None
        self._row_bg = "background: rgb(248, 250, 251);" if index % 2 == 0 else ""

        row_height = scaled(ROW_HEIGHT)

        self.name_label = QLabel(self.name, parent)
        self.name_label.setMinimumWidth(scaled(NAME_WIDTH))
        self.name_label.setFixedHeight(row_height)
        self.name_label.setStyleSheet(self._row_bg)

        self.plot_checkbox = QCheckBox(parent)
        self.plot_checkbox.setFixedWidth(scaled(PLOT_WIDTH))
        self.plot_checkbox.setToolTip("Plot in ROI graph")

        self.min_label = self._make_value_label(parent, row_height)
        self.max_label = self._make_value_label(parent, row_height)
        self.avg_label = self._make_value_label(parent, row_height)

        grid.addWidget(self.name_label, row, 0)
        grid.addWidget(self.plot_checkbox, row, 1, Qt.AlignCenter)
        grid.addWidget(self.min_label, row, 2, Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(self.max_label, row, 3, Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(self.avg_label, row, 4, Qt.AlignRight | Qt.AlignVCenter)

        self.setColor(color)

    def _make_value_label(self, parent: QWidget, row_height: int) -> QLabel:
        label = QLabel("—", parent)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setMinimumWidth(scaled(VALUE_WIDTH))
        label.setFixedHeight(row_height)
        label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        label.setStyleSheet(_value_style(self._row_bg))
        return label

    def setColor(self, color: QColor) -> None:
        self.color = color
        pt = scaled_font_pt(10)
        self.name_label.setStyleSheet(
            f"font: 700 {pt}pt 'Segoe UI';"
            f" color: rgb({color.red()}, {color.green()}, {color.blue()});"
            f" {self._row_bg}"
        )

    def setValues(self, brightnessResults: BrightnessResults) -> None:
        self.min_label.setText(f"{brightnessResults.min:.1f}")
        self.max_label.setText(f"{brightnessResults.max:.1f}")
        self.avg_label.setText(f"{brightnessResults.avg:.1f}")

    def isChecked(self) -> bool:
        return self.plot_checkbox.isChecked()

    def setConfig(self, config: Roi) -> None:
        self.config = config

    def createRoi(self):
        self.roi = pg.RectROI(
            [self.config.x, self.config.y],
            [self.config.w, self.config.h],
            pen=self.color,
        )
        return self.roi

    def updateRoi_from_config(self) -> None:
        self.roi.setPos([self.config.x, self.config.y])
        self.roi.setSize([self.config.w, self.config.h])

    def clear_max_values(self) -> None:
        self.max_values.clear()

    def add_max_value(self, value) -> None:
        self.max_values.appendleft(value)
