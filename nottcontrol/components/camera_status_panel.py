from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from nottcontrol.components.delay_lines_panel import PANEL_STYLE
from nottcontrol.ui_scale import scaled


def _value_style(style_key: str) -> str:
    colors = {
        "recording": "rgb(0, 140, 70)",
        "idle": "rgb(50, 129, 140)",
        "disconnected": "rgb(140, 140, 140)",
        "neutral": "rgb(60, 60, 60)",
    }
    color = colors.get(style_key, colors["neutral"])
    return f'font: 700 10pt "Segoe UI"; color: {color};'


class CameraStatusPanel(QWidget):
    """Compact INFRATEC camera status for the main dashboard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        box = QGroupBox("Camera")
        grid = QGridLayout(box)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        rows = (
            ("Acquisition", "_acquisition_label"),
            ("Files today", "_files_label"),
            ("Frame size", "_frame_size_label"),
        )
        for row, (name, attr) in enumerate(rows):
            name_label = QLabel(name)
            name_label.setStyleSheet('font: 10pt "Segoe UI";')
            value_label = QLabel("—")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setMinimumWidth(scaled(96))
            value_label.setMinimumHeight(scaled(22))
            value_label.setStyleSheet(_value_style("neutral"))
            grid.addWidget(name_label, row, 0)
            grid.addWidget(value_label, row, 1)
            setattr(self, attr, value_label)

        box.setMinimumHeight(scaled(28) + len(rows) * scaled(26))
        outer.addWidget(box)

    def update_status(
        self,
        *,
        connected: bool,
        recording: bool,
        files_today: int | None,
        frame_size: str,
        utc_day: str | None = None,
    ) -> None:
        if not connected:
            acquisition = "Disconnected"
            style_key = "disconnected"
        elif recording:
            acquisition = "Recording"
            style_key = "recording"
        else:
            acquisition = "Idle"
            style_key = "idle"

        self._acquisition_label.setText(acquisition)
        self._acquisition_label.setStyleSheet(_value_style(style_key))

        if files_today is None:
            files_text = "—"
        elif utc_day:
            files_text = f"{files_today:,} ({utc_day})"
        else:
            files_text = f"{files_today:,}"

        self._files_label.setText(files_text)
        self._files_label.setStyleSheet(_value_style("neutral"))

        self._frame_size_label.setText(frame_size or "—")
        self._frame_size_label.setStyleSheet(_value_style("neutral"))
