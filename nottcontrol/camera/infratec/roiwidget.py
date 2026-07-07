from collections import deque

import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget

from nottcontrol.camera.infratec.roi import Roi
from nottcontrol.camera.infratec.utils.utils import BrightnessResults

VALUE_STYLE = 'font: 10pt "Consolas", monospace; color: rgb(30, 30, 30);'
NAME_WIDTH = 44
PLOT_WIDTH = 20
VALUE_WIDTH = 62
ROW_HEIGHT = 22


class RoiWidget(QWidget):
    def __init__(self, parent, index: int, color: QColor, deque_length=6000):
        super().__init__(parent)

        self.name = f"ROI {index}"
        self.db_key = f"roi{index}"
        self.color = color
        self.max_values = deque(maxlen=deque_length)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        self.name_label = QLabel(self.name)
        self.name_label.setFixedWidth(NAME_WIDTH)

        self.plot_checkbox = QCheckBox()
        self.plot_checkbox.setFixedWidth(PLOT_WIDTH)
        self.plot_checkbox.setToolTip("Plot in ROI graph")

        self.min_label = self._make_value_label()
        self.max_label = self._make_value_label()
        self.avg_label = self._make_value_label()

        layout.addWidget(self.name_label)
        layout.addWidget(self.plot_checkbox, 0, Qt.AlignCenter)
        layout.addWidget(self.min_label)
        layout.addWidget(self.max_label)
        layout.addWidget(self.avg_label)

        self.setFixedHeight(ROW_HEIGHT)
        self.setColor(color)

    def _make_value_label(self) -> QLabel:
        label = QLabel("—")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setFixedWidth(VALUE_WIDTH)
        label.setStyleSheet(VALUE_STYLE)
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
