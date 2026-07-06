from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QGridLayout, QGroupBox, QLabel, QScrollArea, QVBoxLayout, QWidget

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


def _temp_panel_name_style() -> str:
    return 'font: 10pt "Segoe UI"; color: rgb(40, 40, 40);'


def _temp_panel_header_style() -> str:
    return f'font: 700 11pt "Segoe UI"; color: {TEAL};'


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
    """Vacuum, pressure, and equipment readouts below the delay-lines panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._pressure_value_labels: dict[str, QLabel] = {}
        self._equipment_value_labels: dict[str, QLabel] = {}

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
        for tag, name in zip(tags, display_names):
            name_label = QLabel(name)
            name_label.setStyleSheet('font: 10pt "Segoe UI";')
            value_label = QLabel("—")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setStyleSheet(_pressure_value_style(None))
            grid.addWidget(name_label, row, 0)
            grid.addWidget(value_label, row, 1)
            self._pressure_value_labels[tag] = value_label
            row += 1

        for key, label in equipment_items or []:
            name_label = QLabel(label)
            name_label.setStyleSheet('font: 10pt "Segoe UI";')
            value_label = QLabel("Unknown")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setStyleSheet(_equipment_status_style("unknown"))
            grid.addWidget(name_label, row, 0)
            grid.addWidget(value_label, row, 1)
            self._equipment_value_labels[key] = value_label
            row += 1

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
                text, style_key = format_equipment_status(equipment_status.get(key))
                label.setText(text)
                label.setStyleSheet(_equipment_status_style(style_key))


class CryoTemperaturePanel(QWidget):
    """Grouped cryostat temperature readouts in a single panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._temp_value_labels: dict[str, QLabel] = {}

    def setup(
        self,
        tags: list[str],
        display_names: list[str],
        *,
        compact: bool = False,
    ) -> None:
        if compact:
            self._setup_compact(tags)
        else:
            self._setup_grouped(tags, display_names)

    def _setup_compact(self, tags: list[str]) -> None:
        from nottcontrol.sensors import temperature_group

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
        order_index = {name: index for index, name in enumerate(group_order)}
        sorted_tags = sorted(
            tags,
            key=lambda tag: (order_index.get(temperature_group(tag), 99), tag),
        )

        box = QGroupBox("Cryostat temperatures")
        grid = QGridLayout(box)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 1)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(4)

        for index, tag in enumerate(sorted_tags):
            row = index // 2
            column_base = 0 if index % 2 == 0 else 2
            name_label = QLabel(temperature_group(tag))
            name_label.setMinimumHeight(20)
            name_label.setStyleSheet(_temp_panel_name_style())
            value_label = QLabel("—")
            value_label.setMinimumWidth(72)
            value_label.setMinimumHeight(20)
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setStyleSheet(_temp_value_style(None))
            grid.addWidget(name_label, row, column_base)
            grid.addWidget(value_label, row, column_base + 1)
            self._temp_value_labels[tag] = value_label

        self.layout().addWidget(box)

    def _setup_grouped(self, tags: list[str], display_names: list[str]) -> None:
        from nottcontrol.sensors import temperature_group

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

        box = QGroupBox("Cryostat temperatures")
        grid = QGridLayout(box)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 1)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)

        row = 0
        for group_name in group_order:
            items = grouped.get(group_name)
            if not items:
                continue

            header = QLabel(group_name)
            header.setMinimumHeight(22)
            header.setStyleSheet(_temp_panel_header_style())
            grid.addWidget(header, row, 0, 1, 4)
            row += 1

            sorted_items = sorted(items, key=lambda item: item[1])
            half = (len(sorted_items) + 1) // 2
            for index, (tag, name) in enumerate(sorted_items):
                column_base = 0 if index < half else 2
                item_row = row + (index if index < half else index - half)
                name_label = QLabel(name)
                name_label.setMinimumHeight(22)
                name_label.setStyleSheet(_temp_panel_name_style())
                value_label = QLabel("—")
                value_label.setMinimumWidth(72)
                value_label.setMinimumHeight(22)
                value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                value_label.setStyleSheet(_temp_value_style(None))
                grid.addWidget(name_label, item_row, column_base)
                grid.addWidget(value_label, item_row, column_base + 1)
                self._temp_value_labels[tag] = value_label

            row += half

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(box)

        self.layout().addWidget(scroll)

    def update_values(self, temp_tag_values: dict[str, float | None]) -> None:
        for tag, label in self._temp_value_labels.items():
            temp_k = temp_tag_values.get(tag)
            if temp_k is None:
                label.setText("—")
            else:
                label.setText(f"{temp_k:.1f} K")
            label.setStyleSheet(_temp_value_style(temp_k))
