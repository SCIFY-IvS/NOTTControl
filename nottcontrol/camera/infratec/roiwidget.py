from collections import deque

import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QCheckBox, QGridLayout, QLabel, QWidget

from nottcontrol.camera.infratec.roi import Roi
from nottcontrol.camera.infratec.utils.utils import BrightnessResults

ROI_COUNT = 10
NAME_WIDTH = 52
PLOT_WIDTH = 36
VALUE_WIDTH = 58
ROW_HEIGHT = 20
HEADER_HEIGHT = 18
PANEL_CHROME_HEIGHT = 34

VALUE_STYLE = 'font: 10pt "Consolas", monospace; color: rgb(30, 30, 30);'
HEADER_STYLE = 'font: 700 9pt "Segoe UI"; color: rgb(90, 90, 90);'


def roi_panel_height() -> int:
    return PANEL_CHROME_HEIGHT + HEADER_HEIGHT + ROI_COUNT * ROW_HEIGHT


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

        row_bg = "background: rgb(248, 250, 251);" if index % 2 == 0 else ""

        self.name_label = QLabel(self.name, parent)
        self.name_label.setFixedWidth(NAME_WIDTH)
        self.name_label.setFixedHeight(ROW_HEIGHT)
        self.name_label.setStyleSheet(row_bg)

        self.plot_checkbox = QCheckBox(parent)
        self.plot_checkbox.setFixedWidth(PLOT_WIDTH)
        self.plot_checkbox.setToolTip("Plot in ROI graph")

        self.min_label = self._make_value_label(parent, row_bg)
        self.max_label = self._make_value_label(parent, row_bg)
        self.avg_label = self._make_value_label(parent, row_bg)

        grid.addWidget(self.name_label, row, 0)
        grid.addWidget(self.plot_checkbox, row, 1, Qt.AlignCenter)
        grid.addWidget(self.min_label, row, 2, Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(self.max_label, row, 3, Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(self.avg_label, row, 4, Qt.AlignRight | Qt.AlignVCenter)

        self.setColor(color)

    def _make_value_label(self, parent: QWidget, row_bg: str) -> QLabel:
        label = QLabel("—", parent)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setFixedWidth(VALUE_WIDTH)
        label.setFixedHeight(ROW_HEIGHT)
        label.setStyleSheet(f"{row_bg} {VALUE_STYLE}")
        return label

    def setColor(self, color: QColor) -> None:
        self.color = color
        self.name_label.setStyleSheet(
            "font: 700 10pt 'Segoe UI';"
            f" color: rgb({color.red()}, {color.green()}, {color.blue()});"
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
