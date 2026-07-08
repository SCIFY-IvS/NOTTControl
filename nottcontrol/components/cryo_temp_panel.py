from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QSizePolicy, QVBoxLayout, QWidget

from nottcontrol.sensors import (
    format_pressure_value,
    format_equipment_status,
    format_pump_status,
    PUMP_SPEED_TAGS,
)
from nottcontrol.ui_scale import scaled, scaled_font_pt


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

PANEL_STYLE_DENSE = f"""
QGroupBox {{
    font: 700 10pt "Segoe UI";
    color: {TEAL};
    border: 1px solid {TEAL};
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 4px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 3px;
}}
"""

_TEMP_GROUP_ORDER = [
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


def _temp_value_style(temp_k: float | None, *, dense: bool = False) -> str:
    size = scaled_font_pt(10 if dense else 11)
    if temp_k is None:
        return f'font: {size}pt "Segoe UI"; color: rgb(140, 140, 140);'
    if temp_k < 10:
        color = "rgb(0, 102, 204)"
    elif temp_k < 50:
        color = "rgb(0, 140, 70)"
    elif temp_k < 100:
        color = "rgb(200, 120, 0)"
    else:
        color = "rgb(200, 50, 0)"
    return f'font: 700 {size}pt "Segoe UI"; color: {color};'


def _temp_panel_name_style(*, dense: bool = False) -> str:
    size = scaled_font_pt(9 if dense else 10)
    return f'font: {size}pt "Segoe UI"; color: rgb(40, 40, 40);'


def _pressure_value_style(value: float | None) -> str:
    if value is None:
        return f'font: {scaled_font_pt(11)}pt "Segoe UI"; color: rgb(140, 140, 140);'
    return f'font: 700 {scaled_font_pt(11)}pt "Segoe UI"; color: rgb(80, 70, 150);'


def _equipment_status_style(style_key: str) -> str:
    colors = {
        "running": "rgb(0, 140, 70)",
        "stopped": "rgb(180, 60, 60)",
        "unknown": "rgb(140, 140, 140)",
    }
    color = colors.get(style_key, colors["unknown"])
    return (
        f'font: 700 {scaled_font_pt(11)}pt "Segoe UI"; color: {color};'
        " background-color: rgb(245, 248, 249);"
        " border: 1px solid rgb(200, 210, 215); border-radius: 4px;"
        f" padding: {scaled(2)}px {scaled(8)}px;"
    )


class CryoTempPanel(QWidget):
    """Equipment readouts for the right-hand cryostat panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)

        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(8)
        outer.addLayout(self._layout)
        outer.addStretch(1)

        self._updated_label = QLabel("Updated: —")
        self._updated_label.setStyleSheet('font: 9pt "Segoe UI"; color: rgb(100, 100, 100);')
        self._updated_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

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
        self._layout.addWidget(self._updated_label)

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
            value_label.setMinimumWidth(scaled(96))
            value_label.setMinimumHeight(scaled(22))
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


class CryoEquipmentPanel(QWidget):
    """Pump and cryocooler status on the main dashboard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._equipment_value_labels: dict[str, QLabel] = {}
        self._updated_label = QLabel("Updated: —")
        self._updated_label.setStyleSheet('font: 9pt "Segoe UI"; color: rgb(100, 100, 100);')
        self._updated_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def setup(self, items: list[tuple[str, str]], *, show_updated: bool = True) -> None:
        if not items:
            return

        box = QGroupBox("Equipment")
        grid = QGridLayout(box)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        for row, (key, label) in enumerate(items):
            name_label = QLabel(label)
            name_label.setStyleSheet('font: 10pt "Segoe UI";')
            value_label = QLabel("Unknown")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setStyleSheet(_equipment_status_style("unknown"))
            grid.addWidget(name_label, row, 0)
            grid.addWidget(value_label, row, 1)
            self._equipment_value_labels[key] = value_label

        layout = self.layout()
        layout.addWidget(box)
        if show_updated:
            layout.addWidget(self._updated_label)

    def update_values(
        self,
        equipment_status_values: dict[str, object] | None,
        updated_at: datetime | None = None,
    ) -> None:
        if equipment_status_values is not None:
            for key, label in self._equipment_value_labels.items():
                text, style_key = format_equipment_status(
                    equipment_status_values.get(key)
                )
                label.setText(text)
                label.setStyleSheet(_equipment_status_style(style_key))

        if updated_at is not None:
            self._updated_label.setText(f"Updated: {updated_at.strftime('%H:%M:%S')} UTC")


class CryoPressurePanel(QWidget):
    """Vacuum, pressure, and equipment readouts below the cryostat temperatures."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._pressure_value_labels: dict[str, QLabel] = {}
        self._equipment_value_labels: dict[str, QLabel] = {}
        self._pump_speed_tags: dict[str, str] = {}

    def setup(
        self,
        tags: list[str],
        display_names: list[str],
        equipment_items: list[tuple[str, str]] | None = None,
    ) -> None:
        if not tags and not equipment_items:
            return

        box = QGroupBox("Vacuum & cryostat")
        grid = QGridLayout(box)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        row = 0
        pump_speed_tags = set(PUMP_SPEED_TAGS.values())
        for tag, name in zip(tags, display_names):
            if tag in pump_speed_tags:
                continue
            name_label = QLabel(name)
            name_label.setStyleSheet('font: 10pt "Segoe UI";')
            value_label = QLabel("—")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setMinimumWidth(scaled(96))
            value_label.setMinimumHeight(scaled(22))
            value_label.setStyleSheet(_pressure_value_style(None))
            grid.addWidget(name_label, row, 0)
            grid.addWidget(value_label, row, 1)
            self._pressure_value_labels[tag] = value_label
            row += 1

        for key, label in equipment_items or []:
            name_label = QLabel(label)
            name_label.setStyleSheet('font: 10pt "Segoe UI";')
            value_label = QLabel("Unknown")
            value_label.setMinimumWidth(scaled(84))
            value_label.setMinimumHeight(scaled(22))
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setStyleSheet(_equipment_status_style("unknown"))
            grid.addWidget(name_label, row, 0)
            grid.addWidget(value_label, row, 1)
            self._equipment_value_labels[key] = value_label
            if key in PUMP_SPEED_TAGS:
                self._pump_speed_tags[key] = PUMP_SPEED_TAGS[key]
            row += 1

        box.setMinimumHeight(scaled(28) + row * scaled(26))
        layout = self.layout()
        layout.addWidget(box)

    def update_values(
        self,
        pressure_tag_values: dict[str, float | None] | None = None,
        equipment_status: dict[str, object] | None = None,
    ) -> None:
        if pressure_tag_values is not None:
            for tag, label in self._pressure_value_labels.items():
                value = pressure_tag_values.get(tag)
                label.setText(format_pressure_value(tag, value))
                label.setStyleSheet(_pressure_value_style(value))

        if equipment_status is not None:
            for key, label in self._equipment_value_labels.items():
                if key in self._pump_speed_tags and pressure_tag_values is not None:
                    speed_tag = self._pump_speed_tags[key]
                    speed = pressure_tag_values.get(speed_tag)
                    text, style_key = format_pump_status(
                        equipment_status.get(key), speed
                    )
                else:
                    text, style_key = format_equipment_status(
                        equipment_status.get(key)
                    )
                label.setText(text)
                label.setStyleSheet(_equipment_status_style(style_key))


class CryoTemperaturePanel(QWidget):
    """Cryostat temperature readouts in a flat, non-scrollable grid."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        self._temp_value_labels: dict[str, QLabel] = {}
        self._dense = False

    def setup(
        self,
        tags: list[str],
        display_names: list[str],
        *,
        compact: bool = False,
        dense: bool = False,
    ) -> None:
        from nottcontrol.sensors import temperature_group

        self._dense = dense or compact
        self.setStyleSheet(PANEL_STYLE_DENSE if self._dense else PANEL_STYLE)

        if compact:
            label_for_tag = temperature_group
            columns = 2
        else:
            labels = dict(zip(tags, display_names))
            label_for_tag = labels.get
            columns = 4 if dense else 3

        self._setup_temp_grid(tags, label_for_tag, columns=columns, dense=self._dense)

    def _sort_tags_by_group(self, tags: list[str]) -> list[str]:
        from nottcontrol.sensors import temperature_group

        order_index = {name: index for index, name in enumerate(_TEMP_GROUP_ORDER)}
        return sorted(
            tags,
            key=lambda tag: (order_index.get(temperature_group(tag), 99), tag),
        )

    def _setup_temp_grid(
        self,
        tags: list[str],
        label_for_tag,
        *,
        columns: int,
        dense: bool,
    ) -> None:
        sorted_tags = self._sort_tags_by_group(tags)
        row_height = scaled(18 if dense else 20)
        value_width = scaled(68 if dense else 76)

        box = QGroupBox("Cryostat temperatures")
        grid = QGridLayout(box)
        grid.setContentsMargins(scaled(6), scaled(2), scaled(6), scaled(4))
        for column in range(columns * 2):
            grid.setColumnStretch(column, 2 if column % 2 == 0 else 1)
        grid.setHorizontalSpacing(scaled(10 if dense else 16))
        grid.setVerticalSpacing(scaled(1 if dense else 3))

        for index, tag in enumerate(sorted_tags):
            row = index // columns
            column_base = (index % columns) * 2
            name_label = QLabel(label_for_tag(tag))
            name_label.setMinimumHeight(row_height)
            name_label.setSizePolicy(
                QSizePolicy.MinimumExpanding, QSizePolicy.Fixed
            )
            name_label.setStyleSheet(_temp_panel_name_style(dense=dense))
            value_label = QLabel("—")
            value_label.setMinimumWidth(value_width)
            value_label.setMinimumHeight(row_height)
            value_label.setSizePolicy(
                QSizePolicy.MinimumExpanding, QSizePolicy.Fixed
            )
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setStyleSheet(_temp_value_style(None, dense=dense))
            grid.addWidget(name_label, row, column_base)
            grid.addWidget(value_label, row, column_base + 1)
            self._temp_value_labels[tag] = value_label

        self.layout().addWidget(box)

    def update_values(self, temp_tag_values: dict[str, float | None]) -> None:
        for tag, label in self._temp_value_labels.items():
            temp_k = temp_tag_values.get(tag)
            if temp_k is None:
                label.setText("—")
            else:
                label.setText(f"{temp_k:.1f} K")
            label.setStyleSheet(_temp_value_style(temp_k, dense=self._dense))
