"""Shared NOTT instrument GUI theme (teal branding, platform fonts)."""

from __future__ import annotations

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QMainWindow, QVBoxLayout, QWidget

TEAL = "rgb(50, 129, 140)"
TEAL_HOVER = "rgb(42, 110, 120)"
TEAL_LIGHT = "rgb(72, 164, 176)"
BG = "rgb(245, 248, 249)"
BG_WHITE = "rgb(255, 255, 255)"
TEXT = "rgb(50, 50, 50)"
TEXT_MUTED = "rgb(100, 100, 100)"
BORDER = "rgb(210, 220, 222)"
DISABLED = "rgb(180, 190, 192)"
DANGER = "rgb(180, 60, 50)"
DANGER_HOVER = "rgb(150, 45, 38)"

# Segoe/Consolas are often missing on Linux; FreeType+XCB can SIGSEGV on bad fallbacks.
if sys.platform.startswith("linux"):
    FONT = '"DejaVu Sans", "Noto Sans", "Liberation Sans", sans-serif'
    MONO_FONT = '"DejaVu Sans Mono", "Noto Sans Mono", "Liberation Mono", monospace'
    APP_FONT_FAMILY = "DejaVu Sans"
    APP_MONO_FAMILY = "DejaVu Sans Mono"
elif sys.platform == "darwin":
    FONT = '"Helvetica Neue", "Segoe UI", sans-serif'
    MONO_FONT = '"Menlo", "Consolas", monospace'
    APP_FONT_FAMILY = "Helvetica Neue"
    APP_MONO_FAMILY = "Menlo"
else:
    FONT = '"Segoe UI"'
    MONO_FONT = '"Consolas", monospace'
    APP_FONT_FAMILY = "Segoe UI"
    APP_MONO_FAMILY = "Consolas"


def linux_safe_stylesheet(css: str) -> str:
    """Avoid stylesheet fonts on Linux: point sizes → FreeType transform SIGSEGV."""
    if not sys.platform.startswith("linux") or not css:
        return css
    import re

    # Drop font: rules so widgets use the pixel-size QApplication font only.
    css = re.sub(r"font(?:-family|-size|-weight)?\s*:[^;{}]+;?", "", css, flags=re.I)
    css = css.replace("Segoe UI", APP_FONT_FAMILY)
    css = css.replace("Consolas", APP_MONO_FAMILY)
    return css

PANEL_STYLE = f"""
QGroupBox {{
    font: 700 10pt {FONT};
    color: {TEAL};
    border: 1px solid {TEAL};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    background: {BG_WHITE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}
"""

PANEL_GROUP_STYLE = PANEL_STYLE

PANEL_STYLE_DENSE = f"""
QGroupBox {{
    font: 700 10pt {FONT};
    color: {TEAL};
    border: 1px solid {TEAL};
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 4px;
    background: {BG_WHITE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 3px;
}}
"""

PANEL_BUTTON_STYLE = f"""
QPushButton {{
    font: 10pt {FONT};
    color: white;
    background: {TEAL};
    border: none;
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 28px;
}}
QPushButton:hover {{
    background: {TEAL_HOVER};
}}
QPushButton:disabled {{
    background: {DISABLED};
    color: rgb(240, 240, 240);
}}
"""

PANEL_BUTTON_SECONDARY_STYLE = f"""
QPushButton {{
    font: 10pt {FONT};
    color: {TEAL};
    background: {BG_WHITE};
    border: 1px solid {TEAL};
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 28px;
}}
QPushButton:hover {{
    background: rgb(232, 244, 246);
}}
QPushButton:disabled {{
    color: {DISABLED};
    border-color: {DISABLED};
    background: rgb(248, 248, 248);
}}
"""

PANEL_BUTTON_DANGER_STYLE = f"""
QPushButton {{
    font: 10pt {FONT};
    color: white;
    background: {DANGER};
    border: none;
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 28px;
}}
QPushButton:hover {{
    background: {DANGER_HOVER};
}}
QPushButton:disabled {{
    background: {DISABLED};
    color: rgb(240, 240, 240);
}}
"""

# Horizontal padding on QLineEdit via QSS mis-maps the caret/click position on
# macOS (and some Linux themes). Use style_line_edit_field() for side margins.
PANEL_FIELD_STYLE = (
    f'font: 9pt {FONT}; color: {TEXT};'
    " QComboBox, QSpinBox {"
    " padding: 2px 6px; min-height: 24px;"
    f" background: {BG_WHITE}; border: 1px solid {BORDER}; border-radius: 4px; }}"
    " QLineEdit {"
    " padding-top: 2px; padding-bottom: 2px; padding-left: 0px; padding-right: 0px;"
    " min-height: 24px;"
    f" background: {BG_WHITE}; border: 1px solid {BORDER}; border-radius: 4px; }}"
)

_LINE_EDIT_TEXT_MARGINS = (6, 0, 6, 0)


def style_line_edit_field(field: QLineEdit, stylesheet: str | None = None) -> None:
    """Apply panel field style without breaking QLineEdit caret hit-testing."""
    field.setStyleSheet(stylesheet if stylesheet is not None else PANEL_FIELD_STYLE)
    left, top, right, bottom = _LINE_EDIT_TEXT_MARGINS
    field.setTextMargins(left, top, right, bottom)

PANEL_LABEL_STYLE = f'font: 9pt {FONT}; color: {TEXT};'
PANEL_LABEL_BOLD_STYLE = f'font: 700 10pt {FONT}; color: {TEXT};'
WIDGET_NAME_STYLE = f'font: 700 14pt {FONT}; color: {TEAL}; background: transparent;'
NOTT_HEADER_TITLE_STYLE = f'font: 18pt {FONT}; font-weight: 700; color: {TEAL}; background: transparent;'
ERROR_LABEL_STYLE = f'font: 10pt {FONT}; color: rgb(200, 50, 0); background: transparent;'
VALUE_READOUT_STYLE = (
    f"font: 700 11pt {FONT}; color: {TEXT};"
    f" background: {BG}; border: 1px solid {TEAL}; border-radius: 4px; padding: 2px 6px;"
)

WINDOW_STYLE = f"""
QMainWindow {{
    background: {BG};
}}
QMenuBar {{
    background: {BG_WHITE};
    border-bottom: 1px solid {BORDER};
}}
QMenu {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
}}
"""

FORM_STYLE = f"QWidget {{ background: {BG}; }}"

H2RG_WINDOW_STYLE = f"""
QMainWindow, QWidget#h2rg_root {{
    background: {BG};
}}
"""

CARD_STYLE = f"""
QWidget#shutter_card, QWidget#motor_card, QWidget#piezo_card {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
"""

CHECKBOX_STYLE = f'font: 9pt {FONT}; color: {TEXT}; spacing: 6px;'

IMAGE_FRAME_STYLE = f"""
QFrame#frame_camera {{
    background: rgb(26, 26, 46);
    border: 1px solid {TEAL};
    border-radius: 6px;
}}
"""

NAV_BUTTON_STYLE = f"""
QPushButton {{
    font: 700 14pt {FONT};
    color: white;
    background: {TEAL};
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
}}
QPushButton:hover {{
    background: {TEAL_HOVER};
}}
QPushButton:disabled {{
    background: {DISABLED};
    color: rgb(240, 240, 240);
}}
"""

# Strip stylesheet font rules on Linux (pixel QApplication font is applied in sanitize).
if sys.platform.startswith("linux"):
    for _style_name, _style_value in list(globals().items()):
        if (
            isinstance(_style_value, str)
            and _style_name.isupper()
            and "STYLE" in _style_name
        ):
            globals()[_style_name] = linux_safe_stylesheet(_style_value)


def sanitize_widget_fonts(root: QWidget) -> None:
    """Rewrite font names/units in stylesheets; force pixel fonts on text widgets."""
    if not sys.platform.startswith("linux"):
        return

    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QApplication, QCheckBox, QComboBox, QGroupBox

    app = QApplication.instance()
    base = QFont(APP_FONT_FAMILY)
    base.setPixelSize(13)
    if app is not None:
        base = QFont(app.font())
        if base.pixelSize() <= 0:
            base.setPixelSize(13)

    widgets = [root]
    widgets.extend(root.findChildren(QWidget))
    for widget in widgets:
        ss = widget.styleSheet()
        if ss:
            updated = linux_safe_stylesheet(ss)
            if updated != ss:
                widget.setStyleSheet(updated)
        if isinstance(
            widget, (QLineEdit, QLabel, QPushButton, QCheckBox, QComboBox, QGroupBox)
        ):
            # Stylesheet font: still wins if present; pixel app font covers the rest.
            widget.setFont(base)


def apply_instrument_window_style(widget: QWidget) -> None:
    if isinstance(widget, QMainWindow):
        widget.setStyleSheet(linux_safe_stylesheet(WINDOW_STYLE))
    else:
        widget.setStyleSheet(linux_safe_stylesheet(FORM_STYLE))
    sanitize_widget_fonts(widget)


def _label(widget: QWidget, name: str) -> QLabel | None:
    return widget.findChild(QLabel, name)


def style_buttons(widget: QWidget, style: str, *names: str) -> None:
    for name in names:
        button = widget.findChild(QPushButton, name)
        if button is not None:
            button.setStyleSheet(style)


def style_line_edits(widget: QWidget, *names: str) -> None:
    for name in names:
        field = widget.findChild(QLineEdit, name)
        if field is not None:
            style_line_edit_field(field)


def style_motor_widget(widget: QWidget) -> None:
    widget.setObjectName("motor_card")
    widget.setStyleSheet(CARD_STYLE)
    name = _label(widget, "label_name")
    if name is not None:
        name.setStyleSheet(WIDGET_NAME_STYLE)
    for label_name in (
        "label_4",
        "label_5",
        "label_6",
        "label_7",
        "label_8",
        "label_9",
        "label_10",
        "label_11",
    ):
        label = _label(widget, label_name)
        if label is not None:
            label.setStyleSheet(PANEL_LABEL_BOLD_STYLE)
    for label_name in (
        "label_status",
        "label_state",
        "label_substate",
        "label_current_position",
        "label_target_position",
        "label_current_speed",
        "dl_command_status",
    ):
        label = _label(widget, label_name)
        if label is not None:
            label.setStyleSheet(PANEL_LABEL_STYLE)
    error = _label(widget, "label_error")
    if error is not None:
        error.setStyleSheet(ERROR_LABEL_STYLE)
    style_buttons(
        widget,
        PANEL_BUTTON_STYLE,
        "pb_move_abs",
        "pb_move_rel",
    )
    style_buttons(
        widget,
        PANEL_BUTTON_SECONDARY_STYLE,
        "pb_moverel_pos",
        "pb_moverel_neg",
        "pb_engineering_menu",
    )
    style_line_edits(widget, "lineEdit_pos", "lineEdit_relpos")


def layout_shutter_widget(widget: QWidget) -> None:
    """Replace absolute geometry with a structured layout."""
    widget.setObjectName("shutter_card")

    layout_host = widget.findChild(QWidget, "layoutWidget")
    if layout_host is not None:
        layout_host.hide()

    buttons = [
        widget.findChild(QPushButton, name)
        for name in ("pb_reset", "pb_init", "pb_enable", "pb_disable", "pb_stop")
    ]
    buttons = [btn for btn in buttons if btn is not None]

    name = _label(widget, "label_name")
    headers = (
        (_label(widget, "label_6"), _label(widget, "label_status")),
        (_label(widget, "label_7"), _label(widget, "label_state")),
        (_label(widget, "label_8"), _label(widget, "label_subState")),
    )
    position_header = _label(widget, "label_9")
    position_value = _label(widget, "label_opened")
    pb_open = widget.findChild(QPushButton, "pb_open")
    pb_close = widget.findChild(QPushButton, "pb_close")
    error = _label(widget, "label_error")

    if widget.layout() is not None:
        return

    outer = QVBoxLayout(widget)
    outer.setContentsMargins(12, 10, 12, 10)
    outer.setSpacing(8)

    if name is not None:
        outer.addWidget(name)

    if buttons:
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        for button in buttons:
            button.setMinimumHeight(28)
            button.setSizePolicy(
                button.sizePolicy().horizontalPolicy(),
                button.sizePolicy().verticalPolicy(),
            )
            btn_row.addWidget(button)
        outer.addLayout(btn_row)

    status_grid = QGridLayout()
    status_grid.setHorizontalSpacing(16)
    status_grid.setVerticalSpacing(4)
    for column, (header, value) in enumerate(headers):
        if header is None or value is None:
            continue
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        value.setMinimumHeight(28)
        status_grid.addWidget(header, 0, column)
        status_grid.addWidget(value, 1, column)
    outer.addLayout(status_grid)

    control_row = QHBoxLayout()
    control_row.setSpacing(8)
    if position_header is not None:
        position_header.setText("Position")
        control_row.addWidget(position_header)
    if position_value is not None:
        position_value.setMinimumWidth(96)
        position_value.setAlignment(Qt.AlignCenter)
        control_row.addWidget(position_value)
    control_row.addStretch()
    if pb_open is not None:
        pb_open.setMinimumWidth(88)
        pb_open.setMinimumHeight(32)
        control_row.addWidget(pb_open)
    if pb_close is not None:
        pb_close.setMinimumWidth(88)
        pb_close.setMinimumHeight(32)
        control_row.addWidget(pb_close)
    outer.addLayout(control_row)

    if error is not None:
        outer.addWidget(error)


def style_shutter_widget(widget: QWidget) -> None:
    layout_shutter_widget(widget)
    widget.setStyleSheet(CARD_STYLE)
    name = _label(widget, "label_name")
    if name is not None:
        name.setStyleSheet(WIDGET_NAME_STYLE)
    for label_name in ("label_6", "label_7", "label_8", "label_9"):
        label = _label(widget, label_name)
        if label is not None:
            label.setStyleSheet(PANEL_LABEL_BOLD_STYLE)
    for label_name in ("label_status", "label_state", "label_subState", "label_opened"):
        label = _label(widget, label_name)
        if label is not None:
            label.setStyleSheet(VALUE_READOUT_STYLE)
    error = _label(widget, "label_error")
    if error is not None:
        error.setStyleSheet(ERROR_LABEL_STYLE)
    style_buttons(
        widget,
        PANEL_BUTTON_SECONDARY_STYLE,
        "pb_reset",
        "pb_init",
        "pb_enable",
    )
    style_buttons(
        widget,
        PANEL_BUTTON_DANGER_STYLE,
        "pb_disable",
        "pb_stop",
    )
    style_buttons(widget, PANEL_BUTTON_STYLE, "pb_open", "pb_close")


def style_piezo_widget(widget: QWidget) -> None:
    widget.setObjectName("piezo_card")
    widget.setStyleSheet(CARD_STYLE)
    name = _label(widget, "label_name")
    if name is not None:
        name.setStyleSheet(WIDGET_NAME_STYLE)
    for label_name in (
        "label_position_title",
        "label_abs_title",
        "label_rel_title",
        "label_scan_title",
    ):
        label = _label(widget, label_name)
        if label is not None:
            label.setStyleSheet(PANEL_LABEL_STYLE)
    position = _label(widget, "label_current_position")
    if position is not None:
        position.setStyleSheet(VALUE_READOUT_STYLE)
    error = _label(widget, "label_error")
    if error is not None:
        error.setStyleSheet(ERROR_LABEL_STYLE)
    style_buttons(
        widget,
        PANEL_BUTTON_STYLE,
        "pb_move_abs",
        "pb_scan",
    )
    style_buttons(
        widget,
        PANEL_BUTTON_SECONDARY_STYLE,
        "pb_move_rel_pos",
        "pb_move_rel_neg",
    )
    style_line_edits(
        widget,
        "lineEdit_abs_pos",
        "lineEdit_rel_pos",
        "lineEdit_scan_amplitude",
    )


def apply_main_window_styles(main_window: QWidget) -> None:
    main_window.setStyleSheet(linux_safe_stylesheet(WINDOW_STYLE))
    for name in (
        "pushButton_piezos",
        "pushButton_filter_wheel",
        "pushButton_ldc",
        "pushButton_cryostat",
        "pushButton_shutters",
        "pushButton_light_source",
        "pushButton_camera",
        "pushButton_h2rg",
        "pushButton_tiptilt",
        "main_pb_delay_lines",
    ):
        button = main_window.findChild(QPushButton, name)
        if button is not None:
            button.setStyleSheet(linux_safe_stylesheet(NAV_BUTTON_STYLE))
    sanitize_widget_fonts(main_window)
