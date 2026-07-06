from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

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

DELAY_LINE_PREFIXES = (
    ("DL 1", "ns=4;s=MAIN.nott_ics.Delay_Lines.NDL1"),
    ("DL 2", "ns=4;s=MAIN.nott_ics.Delay_Lines.NDL2"),
    ("DL 3", "ns=4;s=MAIN.nott_ics.Delay_Lines.NDL3"),
    ("DL 4", "ns=4;s=MAIN.nott_ics.Delay_Lines.NDL4"),
)


def delay_line_opc_nodes() -> tuple[list[str], list[str]]:
    """Return (node_ids, dl_keys) for a batched status/position read."""
    node_ids: list[str] = []
    dl_keys: list[str] = []
    for dl_key, prefix in DELAY_LINE_PREFIXES:
        node_ids.extend([
            f"{prefix}.stat.sStatus",
            f"{prefix}.stat.sState",
            f"{prefix}.stat.lrPosActual",
        ])
        dl_keys.append(dl_key)
    return node_ids, dl_keys


def _header_style() -> str:
    return f'font: 700 10pt "Segoe UI"; color: {TEAL};'


def _name_style() -> str:
    return 'font: 700 10pt "Segoe UI"; color: rgb(60, 60, 60);'


def _text_style() -> str:
    return 'font: 10pt "Segoe UI"; color: rgb(40, 40, 40);'


def _status_style(status: str | None) -> str:
    if status is None:
        return 'font: 700 10pt "Segoe UI"; color: rgb(140, 140, 140);'
    upper = str(status).upper()
    if "OK" in upper or "ENABLED" in upper or "READY" in upper:
        color = "rgb(0, 140, 70)"
    elif "ERR" in upper or "FAULT" in upper or "DISABLE" in upper:
        color = "rgb(200, 50, 0)"
    else:
        color = "rgb(0, 102, 204)"
    return f'font: 700 10pt "Segoe UI"; color: {color};'


def _state_style(state: str | None) -> str:
    if state is None:
        return 'font: 700 10pt "Segoe UI"; color: rgb(140, 140, 140);'
    upper = str(state).upper()
    if "STAND" in upper or "IDLE" in upper or "STOP" in upper:
        color = "rgb(0, 140, 70)"
    elif "MOV" in upper or "RUN" in upper:
        color = "rgb(200, 120, 0)"
    elif "ERR" in upper or "FAULT" in upper:
        color = "rgb(200, 50, 0)"
    else:
        color = "rgb(50, 129, 140)"
    return f'font: 700 10pt "Segoe UI"; color: {color};'


def _position_style() -> str:
    return 'font: 10pt "Segoe UI"; color: rgb(80, 70, 150);'


def format_compact_status(status: str | None) -> str:
    if status is None:
        return "—"
    upper = str(status).strip().upper()
    if "STAND" in upper:
        return "STAND"
    if upper in {"OK", "ENABLED", "READY"}:
        return upper.title() if upper != "OK" else "OK"
    if "ERR" in upper or "FAULT" in upper:
        return "ERROR"
    if "DISABLE" in upper:
        return "OFF"
    text = str(status).strip()
    return text if len(text) <= 8 else text[:7] + "…"


def format_compact_state(state: str | None) -> str:
    if state is None:
        return "—"
    upper = str(state).strip().upper()
    if "OPERAT" in upper:
        return "OPER"
    if "NOT OP" in upper or "NOT_OP" in upper:
        return "NOT OP"
    if "STAND" in upper or "IDLE" in upper:
        return "IDLE"
    if "MOV" in upper or "RUN" in upper:
        return "MOVE"
    if "ERR" in upper or "FAULT" in upper:
        return "ERROR"
    text = str(state).strip()
    return text if len(text) <= 8 else text[:7] + "…"


class DelayLinesStatusPanel(QWidget):
    """Compact status table for all four delay lines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        box = QGroupBox("Delay lines")
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

        for row, (dl_key, _) in enumerate(DELAY_LINE_PREFIXES, start=1):
            name_label = QLabel(dl_key)
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

            self._status_labels[dl_key] = status_label
            self._state_labels[dl_key] = state_label
            self._position_labels[dl_key] = position_label

        outer.addWidget(box)

    def update_status(
        self,
        dl_key: str,
        status: str | None,
        state: str | None,
        position_mm: float | None,
    ) -> None:
        status_label = self._status_labels[dl_key]
        status_label.setText("—" if status is None else str(status))
        status_label.setStyleSheet(_status_style(status))

        state_label = self._state_labels[dl_key]
        state_label.setText("—" if state is None else str(state))
        state_label.setStyleSheet(_state_style(state))

        position_label = self._position_labels[dl_key]
        if position_mm is None:
            position_label.setText("—")
        else:
            position_um = position_mm * 1000.0
            position_label.setText(f"{position_um:.1f} µm")
        position_label.setStyleSheet(_position_style())
