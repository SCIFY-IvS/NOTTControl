from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from nottcontrol.components.delay_lines_panel import (
    PANEL_STYLE,
    _header_style,
    _name_style,
    _position_style,
    _state_style,
    _status_style,
    format_compact_state,
    format_compact_status,
)

TIP_TILT_ACTUATORS = tuple(
    (
        f"Beam {beam_index}",
        actuator_id,
        f"ns=4;s=MAIN.nott_ics.TipTilt.{actuator_id}",
    )
    for beam_index in range(4)
    for actuator_id in (f"NTPA{beam_index + 1}", f"NTTA{beam_index + 1}")
)


def tip_tilt_opc_nodes() -> tuple[list[str], list[str]]:
    """Return (node_ids, row_keys) for a batched status/position read."""
    node_ids: list[str] = []
    row_keys: list[str] = []
    for _beam_key, actuator_id, prefix in TIP_TILT_ACTUATORS:
        node_ids.extend([
            f"{prefix}.stat.sStatus",
            f"{prefix}.stat.sState",
            f"{prefix}.stat.lrPosActual",
        ])
        row_keys.append(actuator_id)
    return node_ids, row_keys


class TipTiltStatusPanel(QWidget):
    """Compact status table for tip/tilt actuators (P and T per beam)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        box = QGroupBox("Tip / tilt")
        grid = QGridLayout(box)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)
        grid.setColumnStretch(4, 2)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)

        headers = ("", "Actuator", "Status", "State", "Position")
        for col, text in enumerate(headers):
            header = QLabel(text)
            header.setStyleSheet(_header_style())
            if col > 0:
                header.setAlignment(Qt.AlignCenter)
            grid.addWidget(header, 0, col)

        self._status_labels: dict[str, QLabel] = {}
        self._state_labels: dict[str, QLabel] = {}
        self._position_labels: dict[str, QLabel] = {}

        row = 1
        beam_index = 0
        while beam_index < 4:
            beam_key = f"Beam {beam_index}"
            beam_actuators = [
                item for item in TIP_TILT_ACTUATORS if item[0] == beam_key
            ]
            beam_label = QLabel(beam_key)
            beam_label.setStyleSheet(_name_style())
            beam_label.setAlignment(Qt.AlignCenter)
            grid.addWidget(beam_label, row, 0, len(beam_actuators), 1)

            for offset, (_beam, actuator_id, _) in enumerate(beam_actuators):
                actuator_label = QLabel(actuator_id)
                actuator_label.setStyleSheet('font: 9pt "Segoe UI"; color: rgb(80, 80, 80);')
                actuator_label.setAlignment(Qt.AlignCenter)

                status_label = QLabel("—")
                status_label.setAlignment(Qt.AlignCenter)
                status_label.setStyleSheet(_status_style(None))

                state_label = QLabel("—")
                state_label.setAlignment(Qt.AlignCenter)
                state_label.setStyleSheet(_state_style(None))

                position_label = QLabel("—")
                position_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                position_label.setStyleSheet(_position_style())

                item_row = row + offset
                grid.addWidget(actuator_label, item_row, 1)
                grid.addWidget(status_label, item_row, 2)
                grid.addWidget(state_label, item_row, 3)
                grid.addWidget(position_label, item_row, 4)

                self._status_labels[actuator_id] = status_label
                self._state_labels[actuator_id] = state_label
                self._position_labels[actuator_id] = position_label

            row += len(beam_actuators)
            beam_index += 1

        outer.addWidget(box)

    def update_status(
        self,
        actuator_id: str,
        status: str | None,
        state: str | None,
        position_mm: float | None,
    ) -> None:
        status_label = self._status_labels[actuator_id]
        status_text = format_compact_status(status)
        status_label.setText(status_text)
        status_label.setStyleSheet(_status_style(status))

        state_label = self._state_labels[actuator_id]
        state_text = format_compact_state(state)
        state_label.setText(state_text)
        state_label.setStyleSheet(_state_style(state))

        position_label = self._position_labels[actuator_id]
        if position_mm is None:
            position_label.setText("—")
        else:
            position_um = position_mm * 1000.0
            position_label.setText(f"{position_um:.1f} µm")
        position_label.setStyleSheet(_position_style())
