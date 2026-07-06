from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from nottcontrol.sensors import format_pressure_value, format_equipment_status


TEAL = "rgb(50, 129, 140)"
PANEL_STYLE = f"""
QGroupBox {{
    font: 700 11pt "Segoe UI";
    color: {TEAL};
    border: 1px solid {TEAL};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}
"""


def _temp_value_style(temp_k: float | None) -> str:
    if temp_k is None:
        return 'font: 11pt "Segoe UI"; color: rgb(140, 140, 140);'
    if temp_k < 10:
        color = "rgb(0, 102, 204)"
    elif temp_k < 50:
        color = "rgb(0, 140, 70)"
    elif temp_k < 100:
        color = "rgb(200, 120, 0)"
    else:
        color = "rgb(200, 50, 0)"
    return f'font: 700 11pt "Segoe UI"; color: {color};'


def _pressure_value_style(value: float | None) -> str:
    if value is None:
        return 'font: 11pt "Segoe UI"; color: rgb(140, 140, 140);'
    return 'font: 700 11pt "Segoe UI"; color: rgb(80, 70, 150);'


def _equipment_status_style(style_key: str) -> str:
    colors = {
        "running": "rgb(0, 140, 70)",
        "stopped": "rgb(180, 60, 60)",
        "unknown": "rgb(140, 140, 140)",
    }
    color = colors.get(style_key, colors["unknown"])
    return (
        f'font: 700 11pt "Segoe UI"; color: {color};'
        " background-color: rgb(245, 248, 249);"
        " border: 1px solid rgb(200, 210, 215); border-radius: 4px;"
        " padding: 2px 8px;"
    )


class CryoTempPanel(QWidget):
    """Equipment and vacuum readouts for the right-hand cryostat panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)

        title = QLabel("Cryostat monitor")
        title.setStyleSheet(f'font: 700 14pt "Segoe UI"; color: {TEAL};')
        title.setAlignment(Qt.AlignCenter)
        outer.addWidget(title)

        self._updated_label = QLabel("Updated: —")
        self._updated_label.setStyleSheet('font: 9pt "Segoe UI"; color: rgb(100, 100, 100);')
        self._updated_label.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._updated_label)

        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(8)
        outer.addLayout(self._layout)
        outer.addStretch(1)

        self._pressure_value_labels: dict[str, QLabel] = {}
        self._equipment_value_labels: dict[str, QLabel] = {}

    def setup_equipment(self, items: list[tuple[str, str]]) -> None:
        if not items:
            return

        box = QGroupBox("Equipment")
        grid = QGridLayout(box)
        grid.setColumnStretch(0, 1)
        grid.setHorizontalSpacing(12)

        for row, (key, label) in enumerate(items):
            name_label = QLabel(label)
            name_label.setStyleSheet('font: 10pt "Segoe UI";')
            value_label = QLabel("Unknown")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setStyleSheet(_equipment_status_style("unknown"))
            grid.addWidget(name_label, row, 0)
            grid.addWidget(value_label, row, 1)
            self._equipment_value_labels[key] = value_label

        self._layout.addWidget(box)

    def setup_pressures(self, tags: list[str], display_names: list[str]) -> None:
        if not tags:
            return

        box = QGroupBox("Vacuum & pressure")
        grid = QGridLayout(box)
        grid.setColumnStretch(0, 1)
        grid.setHorizontalSpacing(12)

        for row, (tag, name) in enumerate(zip(tags, display_names)):
            name_label = QLabel(name)
            name_label.setStyleSheet('font: 10pt "Segoe UI";')
            value_label = QLabel("—")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setStyleSheet(_pressure_value_style(None))
            grid.addWidget(name_label, row, 0)
            grid.addWidget(value_label, row, 1)
            self._pressure_value_labels[tag] = value_label

        self._layout.addWidget(box)

    def update_values(
        self,
        pressure_tag_values: dict[str, float | None] | None = None,
        equipment_status_values: dict[str, object] | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        if equipment_status_values is not None:
            for key, label in self._equipment_value_labels.items():
                text, style_key = format_equipment_status(
                    equipment_status_values.get(key)
                )
                label.setText(text)
                label.setStyleSheet(_equipment_status_style(style_key))

        if pressure_tag_values is not None:
            for tag, label in self._pressure_value_labels.items():
                value = pressure_tag_values.get(tag)
                label.setText(format_pressure_value(tag, value))
                label.setStyleSheet(_pressure_value_style(value))

        if updated_at is not None:
            self._updated_label.setText(f"Updated: {updated_at.strftime('%H:%M:%S')} UTC")
