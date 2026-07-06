from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from nottcontrol.components.cryo_temp_panel import TEAL, PANEL_STYLE, _temp_value_style
from nottcontrol.sensors import temperature_group


class CryoTemperatureBar(QWidget):
    """Fixed bottom strip of cryostat temperature group boxes (no scrolling)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 4)
        outer.setSpacing(4)

        title = QLabel("Cryostat temperatures")
        title.setStyleSheet(f'font: 700 12pt "Segoe UI"; color: {TEAL};')
        outer.addWidget(title)

        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(6)
        outer.addLayout(self._grid)

        self._temp_value_labels: dict[str, QLabel] = {}

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
        active_groups = [name for name in group_order if grouped.get(name)]

        columns = 5
        for index, group_name in enumerate(active_groups):
            items = grouped[group_name]
            row = index // columns
            col = index % columns

            box = QGroupBox(group_name)
            box.setStyleSheet(
                'QGroupBox { font: 700 9pt "Segoe UI"; margin-top: 8px; padding-top: 6px; }'
            )
            grid = QGridLayout(box)
            grid.setContentsMargins(6, 4, 6, 4)
            grid.setHorizontalSpacing(6)
            grid.setVerticalSpacing(2)
            grid.setColumnStretch(0, 1)

            for item_row, (tag, name) in enumerate(
                sorted(items, key=lambda item: item[1])
            ):
                name_label = QLabel(name)
                name_label.setStyleSheet('font: 8pt "Segoe UI";')
                value_label = QLabel("—")
                value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                value_label.setStyleSheet(_temp_value_style(None))
                grid.addWidget(name_label, item_row, 0)
                grid.addWidget(value_label, item_row, 1)
                self._temp_value_labels[tag] = value_label

            self._grid.addWidget(box, row, col)

    def update_values(self, temp_tag_values: dict[str, float | None]) -> None:
        for tag, label in self._temp_value_labels.items():
            temp_k = temp_tag_values.get(tag)
            if temp_k is None:
                label.setText("—")
            else:
                label.setText(f"{temp_k:.1f} K")
            label.setStyleSheet(_temp_value_style(temp_k))
