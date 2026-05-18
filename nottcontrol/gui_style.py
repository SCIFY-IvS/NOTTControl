"""Shared Qt appearance for NOTT instrument control (Fusion + QSS)."""
from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

_BG = "#e9eef1"
_SURFACE = "#ffffff"
_SURFACE_ALT = "#f4f8f9"
_TEXT = "#1a2528"
_TEXT_MUTED = "#5c7380"
_ACCENT = "#2a7f8a"
_ACCENT_HOVER = "#36919d"
_ACCENT_PRESS = "#1f6973"
_BORDER_SOFT = "#d9e4e7"
_BORDER = "#b8c9ce"
_ERROR = "#c62828"
_WARN = "#b45309"
_STATUS_OK = "#2e7d32"

APP_STYLESHEET = f"""
QMainWindow {{
    background-color: {_BG};
}}
QWidget {{
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", Arial, sans-serif;
    font-size: 13px;
    color: {_TEXT};
}}
QLabel {{
    font-size: 13px;
}}
QMenuBar {{
    background-color: {_SURFACE};
    border-bottom: 1px solid {_BORDER_SOFT};
    padding: 4px 8px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {_SURFACE_ALT};
}}
QMenu {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER};
    padding: 6px 4px;
    border-radius: 6px;
}}
QMenu::item {{
    padding: 8px 24px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: #d6ecf0;
}}
QStatusBar {{
    background-color: {_SURFACE};
    border-top: 1px solid {_BORDER_SOFT};
    color: {_TEXT_MUTED};
    font-size: 12px;
    padding: 4px 8px;
}}
QPushButton {{
    background-color: {_ACCENT};
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 24px;
}}
QPushButton:hover {{
    background-color: {_ACCENT_HOVER};
}}
QPushButton:pressed {{
    background-color: {_ACCENT_PRESS};
}}
QPushButton:disabled {{
    background-color: #9db8bd;
    color: #eef3f5;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 20px;
    selection-background-color: #b8dce2;
}}
QCheckBox {{
    spacing: 8px;
}}
QGroupBox {{
    font-weight: 600;
    font-size: 13px;
    border: 1px solid {_BORDER_SOFT};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 14px;
    padding-bottom: 8px;
    background-color: {_SURFACE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}
QToolTip {{
    background-color: {_SURFACE};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    padding: 8px 10px;
    border-radius: 6px;
}}
QScrollBar:vertical {{
    width: 12px;
    background: {_BG};
    border-radius: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #a8bcc2;
    min-height: 28px;
    border-radius: 6px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: #899fa6;
}}
QScrollBar:horizontal {{
    height: 12px;
    background: {_BG};
    border-radius: 6px;
}}
QScrollBar::handle:horizontal {{
    background: #a8bcc2;
    min-width: 28px;
    border-radius: 6px;
    margin: 2px;
}}

/* Main dashboard */
QLabel#label_2 {{
    color: {_TEXT};
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.4px;
}}
QLabel#subtitleLabel {{
    color: {_TEXT_MUTED};
    font-size: 13px;
    font-weight: 500;
}}
QFrame#navPanel {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER_SOFT};
    border-radius: 12px;
}}
QLabel#navHeader {{
    color: {_TEXT_MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QFrame#dlTelemetryCard {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER_SOFT};
    border-radius: 10px;
}}
QLabel#metricCaption {{
    color: {_TEXT_MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.35px;
}}
QLabel#main_label_temp1, QLabel#main_label_temp2,
QLabel#main_label_temp3, QLabel#main_label_temp4 {{
    background-color: {_SURFACE_ALT};
    border: 1px solid {_BORDER_SOFT};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;
    font-weight: 600;
    min-width: 76px;
}}
QLabel#label_dl_status {{
    font-size: 13px;
    font-weight: 700;
    color: #1565c0;
}}
QLabel#label_dl_state {{
    font-size: 13px;
    font-weight: 700;
    color: {_STATUS_OK};
}}
QLabel#label_light_source, QLabel#label_shutters_status, QLabel#label_filter_wheel_status {{
    font-size: 13px;
    font-weight: 700;
    color: {_WARN};
}}
QLabel#label_error {{
    color: {_ERROR};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#label_10, QLabel#label_11, QLabel#label_12, QLabel#label_13 {{
    color: {_ACCENT};
    font-weight: 700;
}}

/* Delay-line motor cards */
QWidget#motorPanel {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER_SOFT};
    border-radius: 10px;
}}
QWidget#motorPanel QPushButton#pb_engineering_menu {{
    background-color: {_SURFACE_ALT};
    color: {_ACCENT};
    border: 1px solid {_ACCENT};
    font-weight: 600;
}}
QWidget#motorPanel QPushButton#pb_engineering_menu:hover {{
    background-color: #e4f4f6;
}}
QWidget#motorPanel QPushButton#pb_move_abs,
QWidget#motorPanel QPushButton#pb_move_rel {{
    background-color: {_ACCENT};
    color: #ffffff;
    padding: 8px 12px;
    font-size: 12px;
    border-radius: 6px;
}}
QWidget#motorPanel QPushButton#pb_move_abs:hover,
QWidget#motorPanel QPushButton#pb_move_rel:hover {{
    background-color: {_ACCENT_HOVER};
}}
QWidget#motorPanel QPushButton#pb_moverel_pos,
QWidget#motorPanel QPushButton#pb_moverel_neg {{
    background-color: {_SURFACE_ALT};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    min-width: 40px;
    max-width: 44px;
    padding: 4px;
    font-size: 16px;
    font-weight: 700;
    border-radius: 6px;
}}
QWidget#motorPanel QPushButton#pb_moverel_pos:hover,
QWidget#motorPanel QPushButton#pb_moverel_neg:hover {{
    background-color: #dfeaee;
}}
"""


def apply_application_style(app: QApplication) -> None:
    """Apply Fusion style and NOTT stylesheet application-wide."""
    app.setStyle("Fusion")
    font = app.font()
    if font.pointSize() <= 0:
        font.setPointSize(10)
    elif font.pointSize() < 10:
        font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(APP_STYLESHEET)


def polish_secondary_main_window(win: QMainWindow, subtitle: Optional[str], min_size: QSize) -> None:
    """Subtitle under title label and comfortable minimum size for subsystem windows."""
    win.setMinimumSize(min_size.width(), max(win.minimumHeight(), min_size.height()))
    cw = win.centralWidget()
    if cw is None or not subtitle or cw.findChild(QLabel, "subtitleLabel"):
        return
    sub = QLabel(subtitle, cw)
    sub.setObjectName("subtitleLabel")
    title = cw.findChild(QLabel, "label_2")
    if title is not None:
        g = title.geometry()
        sub.setGeometry(g.x(), g.y() + g.height(), max(g.width(), 360), 24)
        sub.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
    else:
        sub.setGeometry(24, 72, 560, 24)


def _nav_buttons(ui):
    yield ui.pushButton_light_source
    yield ui.main_pb_delay_lines
    yield ui.pushButton_tiptilt
    yield ui.pushButton_filter_wheel
    yield ui.pushButton_shutters
    yield ui.pushButton_cryostat
    yield ui.pushButton_camera


def apply_main_window_dashboard(main_window: QMainWindow) -> None:
    """Nav card, subtitle, and NDL1 telemetry strip on the main dashboard."""
    ui = getattr(main_window, "ui", None)
    cw = main_window.centralWidget()
    if ui is None or cw is None:
        return

    main_window.resize(max(main_window.width(), 1024), max(main_window.height(), 786))
    main_window.setMinimumSize(960, 720)

    if not cw.findChild(QLabel, "subtitleLabel"):
        sub = QLabel("High-level control • NOTT ICS", cw)
        sub.setObjectName("subtitleLabel")
        title = cw.findChild(QLabel, "label_2")
        if title:
            tg = title.geometry()
            sub.setGeometry(tg.x(), tg.y() + tg.height() - 2, tg.width(), 26)
            sub.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        else:
            sub.setGeometry(310, 88, 400, 26)

    if cw.findChild(QFrame, "navPanel") is None:
        nav = QFrame(cw)
        nav.setObjectName("navPanel")
        nav.setGeometry(16, 224, 232, 420)
        lay = QVBoxLayout(nav)
        lay.setContentsMargins(14, 14, 14, 16)
        lay.setSpacing(10)
        hdr = QLabel("MODULES")
        hdr.setObjectName("navHeader")
        lay.addWidget(hdr)
        for btn in _nav_buttons(ui):
            btn.setParent(nav)
            btn.setMinimumHeight(46)
            lay.addWidget(btn)
        lay.addStretch()
        nav.show()

    st = cw.findChild(QLabel, "label_dl_status")
    stt = cw.findChild(QLabel, "label_dl_state")
    if st is not None and stt is not None and cw.findChild(QFrame, "dlTelemetryCard") is None:
        card = QFrame(cw)
        card.setObjectName("dlTelemetryCard")
        card.setGeometry(268, 296, 450, 90)
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 10, 14, 12)
        v.setSpacing(8)
        cap = QLabel("DELAY LINE NDL1")
        cap.setObjectName("metricCaption")
        v.addWidget(cap)
        row = QWidget(card)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)
        lx_s = QLabel("Status")
        lx_s.setStyleSheet(f"color: {_TEXT_MUTED}; font-weight: 600;")
        lx_p = QLabel("PLC state")
        lx_p.setStyleSheet(f"color: {_TEXT_MUTED}; font-weight: 600;")
        st.setParent(row)
        stt.setParent(row)
        h.addWidget(lx_s)
        h.addWidget(st, stretch=2)
        h.addSpacing(8)
        h.addWidget(lx_p)
        h.addWidget(stt, stretch=2)
        v.addWidget(row)
        card.show()

    nav = cw.findChild(QFrame, "navPanel")
    if nav is not None:
        nav.raise_()

    cw.setContentsMargins(8, 4, 8, 8)


def polish_delay_lines_window(window: QMainWindow) -> None:
    polish_secondary_main_window(
        window,
        subtitle="Fine positioning for four motorized delay lines",
        min_size=QSize(1360, 680),
    )
    cw = window.centralWidget()
    if cw is None:
        return
    t = cw.findChild(QLabel, "label_2")
    if t is not None and not t.toolTip():
        t.setToolTip("OPC UA readout and motor commands")
