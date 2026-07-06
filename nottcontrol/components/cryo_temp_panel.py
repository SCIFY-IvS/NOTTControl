from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nottcontrol.sensors import format_pressure_value, temperature_group


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


class CryoTempPanel(QWidget):
    """Scrollable grouped display of cryostat temperature and pressure sensors."""

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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        self._content = QWidget()
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(8)
        scroll.setWidget(self._content)

        self._temp_value_labels: dict[str, QLabel] = {}
        self._pressure_value_labels: dict[str, QLabel] = {}

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

    def setup(self, tags: list[str], display_names: list[str]) -> None:
        grouped: dict[str, list[tuple[str, str]]] = {}
        for tag, name in zip(tags, display_names):
            grouped.setdefault(temperature_group(tag), []).append((tag, name))

        group_order = [
            "Detector",
            "Base plate",
            "Shield",
            "Photonic chip",
            "Flat field",
            "Master",
            "Sidecar",
            "Thermal box",
            "Cabinet",
            "Other",
        ]

        for group_name in group_order:
            items = grouped.get(group_name)
            if not items:
                continue

            box = QGroupBox(group_name)
            grid = QGridLayout(box)
            grid.setColumnStretch(0, 1)
            grid.setHorizontalSpacing(12)

            for row, (tag, name) in enumerate(sorted(items, key=lambda item: item[1])):
                name_label = QLabel(name)
                name_label.setStyleSheet('font: 10pt "Segoe UI";')
                value_label = QLabel("—")
                value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                value_label.setStyleSheet(_temp_value_style(None))
                grid.addWidget(name_label, row, 0)
                grid.addWidget(value_label, row, 1)
                self._temp_value_labels[tag] = value_label

            self._layout.addWidget(box)

        self._layout.addStretch(1)

    def update_values(
        self,
        temp_tag_values: dict[str, float | None],
        pressure_tag_values: dict[str, float | None] | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        for tag, label in self._temp_value_labels.items():
            temp_k = temp_tag_values.get(tag)
            if temp_k is None:
                label.setText("—")
            else:
                label.setText(f"{temp_k:.2f} K")
            label.setStyleSheet(_temp_value_style(temp_k))

        if pressure_tag_values is not None:
            for tag, label in self._pressure_value_labels.items():
                value = pressure_tag_values.get(tag)
                label.setText(format_pressure_value(tag, value))
                label.setStyleSheet(_pressure_value_style(value))

        if updated_at is not None:
            self._updated_label.setText(f"Updated: {updated_at.strftime('%H:%M:%S')} UTC")
