from __future__ import annotations

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from nottcontrol.components.delay_lines_panel import (
    PANEL_STYLE,
    _header_style,
    _name_style,
    _state_style,
    _status_style,
    format_compact_state,
    format_compact_status,
)

SHUTTER_OPEN_POS_MM = 5.0
SHUTTER_CLOSE_POS_MM = 35.0
SHUTTER_POS_RTOL = 0.02

SHUTTERS = tuple(
    (f"SH {index}", f"ns=4;s=MAIN.nott_ics.Shutters.NSH{index}")
    for index in range(1, 5)
)


def shutter_opc_nodes() -> tuple[list[str], list[str]]:
    """Return (node_ids, shutter_keys) for a batched status/position read."""
    node_ids: list[str] = []
    shutter_keys: list[str] = []
    for shutter_key, prefix in SHUTTERS:
        node_ids.extend([
            f"{prefix}.stat.sStatus",
            f"{prefix}.stat.sState",
            f"{prefix}.stat.lrPosActual",
        ])
        shutter_keys.append(shutter_key)
    return node_ids, shutter_keys


def shutter_hardware_state(position_mm: float | None) -> str | None:
    if position_mm is None:
        return None
    if np.isclose(position_mm, SHUTTER_OPEN_POS_MM, SHUTTER_POS_RTOL):
        return "OPEN"
    if np.isclose(position_mm, SHUTTER_CLOSE_POS_MM, SHUTTER_POS_RTOL):
        return "CLOSED"
    return "Unknown"


def _shutter_state_style(state: str | None) -> str:
    if state is None:
        return 'font: 700 10pt "Segoe UI"; color: rgb(140, 140, 140);'
    upper = state.upper()
    if upper == "OPEN":
        color = "rgb(0, 140, 70)"
    elif upper == "CLOSED":
        color = "rgb(50, 129, 140)"
    else:
        color = "rgb(200, 120, 0)"
    return f'font: 700 10pt "Segoe UI"; color: {color};'


class ShuttersStatusPanel(QWidget):
    """Compact status table for all four shutters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        box = QGroupBox("Shutters")
        grid = QGridLayout(box)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 2)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        headers = ("", "Status", "State", "Shutter")
        for col, text in enumerate(headers):
            header = QLabel(text)
            header.setStyleSheet(_header_style())
            if col > 0:
                header.setAlignment(Qt.AlignCenter)
            grid.addWidget(header, 0, col)

        self._status_labels: dict[str, QLabel] = {}
        self._state_labels: dict[str, QLabel] = {}
        self._shutter_labels: dict[str, QLabel] = {}

        for row, (shutter_key, _) in enumerate(SHUTTERS, start=1):
            name_label = QLabel(shutter_key)
            name_label.setStyleSheet(_name_style())

            status_label = QLabel("—")
            status_label.setAlignment(Qt.AlignCenter)
            status_label.setStyleSheet(_status_style(None))

            state_label = QLabel("—")
            state_label.setAlignment(Qt.AlignCenter)
            state_label.setStyleSheet(_state_style(None))

            shutter_label = QLabel("—")
            shutter_label.setAlignment(Qt.AlignCenter)
            shutter_label.setStyleSheet(_shutter_state_style(None))

            grid.addWidget(name_label, row, 0)
            grid.addWidget(status_label, row, 1)
            grid.addWidget(state_label, row, 2)
            grid.addWidget(shutter_label, row, 3)

            self._status_labels[shutter_key] = status_label
            self._state_labels[shutter_key] = state_label
            self._shutter_labels[shutter_key] = shutter_label

        outer.addWidget(box)

    def update_status(
        self,
        shutter_key: str,
        status: str | None,
        state: str | None,
        position_mm: float | None,
    ) -> None:
        status_label = self._status_labels[shutter_key]
        status_text = format_compact_status(status)
        status_label.setText(status_text)
        status_label.setStyleSheet(_status_style(status))

        state_label = self._state_labels[shutter_key]
        state_text = format_compact_state(state)
        state_label.setText(state_text)
        state_label.setStyleSheet(_state_style(state))

        shutter_state = shutter_hardware_state(position_mm)
        shutter_label = self._shutter_labels[shutter_key]
        shutter_label.setText("—" if shutter_state is None else shutter_state)
        shutter_label.setStyleSheet(_shutter_state_style(shutter_state))
