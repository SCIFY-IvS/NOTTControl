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
)

TIP_TILT_BEAMS = tuple(
    (f"Beam {index}", f"ns=4;s=MAIN.nott_ics.TipTilt.NTPA{index + 1}")
    for index in range(4)
)


def tip_tilt_opc_nodes() -> tuple[list[str], list[str]]:
    """Return (node_ids, beam_keys) for a batched status/position read."""
    node_ids: list[str] = []
    beam_keys: list[str] = []
    for beam_key, prefix in TIP_TILT_BEAMS:
        node_ids.extend([
            f"{prefix}.stat.sStatus",
            f"{prefix}.stat.sState",
            f"{prefix}.stat.lrPosActual",
        ])
        beam_keys.append(beam_key)
    return node_ids, beam_keys


class TipTiltStatusPanel(QWidget):
    """Compact status table for the four tip/tilt beams."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        box = QGroupBox("Tip / tilt")
        grid = QGridLayout(box)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 2)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        headers = ("", "Status", "State", "Position")
        for col, text in enumerate(headers):
            header = QLabel(text)
            header.setStyleSheet(_header_style())
            if col > 0:
                header.setAlignment(Qt.AlignCenter)
            grid.addWidget(header, 0, col)

        self._status_labels: dict[str, QLabel] = {}
        self._state_labels: dict[str, QLabel] = {}
        self._position_labels: dict[str, QLabel] = {}

        for row, (beam_key, _) in enumerate(TIP_TILT_BEAMS, start=1):
            name_label = QLabel(beam_key)
            name_label.setStyleSheet(_name_style())

            status_label = QLabel("—")
            status_label.setAlignment(Qt.AlignCenter)
            status_label.setStyleSheet(_status_style(None))

            state_label = QLabel("—")
            state_label.setAlignment(Qt.AlignCenter)
            state_label.setStyleSheet(_state_style(None))

            position_label = QLabel("—")
            position_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            position_label.setStyleSheet(_position_style())

            grid.addWidget(name_label, row, 0)
            grid.addWidget(status_label, row, 1)
            grid.addWidget(state_label, row, 2)
            grid.addWidget(position_label, row, 3)

            self._status_labels[beam_key] = status_label
            self._state_labels[beam_key] = state_label
            self._position_labels[beam_key] = position_label

        outer.addWidget(box)

    def update_status(
        self,
        beam_key: str,
        status: str | None,
        state: str | None,
        position_mm: float | None,
    ) -> None:
        status_label = self._status_labels[beam_key]
        status_label.setText("—" if status is None else str(status))
        status_label.setStyleSheet(_status_style(status))

        state_label = self._state_labels[beam_key]
        state_label.setText("—" if state is None else str(state))
        state_label.setStyleSheet(_state_style(state))

        position_label = self._position_labels[beam_key]
        if position_mm is None:
            position_label.setText("—")
        else:
            position_um = position_mm * 1000.0
            position_label.setText(f"{position_um:.1f} µm")
        position_label.setStyleSheet(_position_style())
