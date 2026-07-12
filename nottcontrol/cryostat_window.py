from datetime import datetime

from PyQt5.QtCore import QTimer, pyqtSignal, Qt
from PyQt5.QtWidgets import QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from nottcontrol import sensor_config_path
from nottcontrol.app_icon import apply_window_icon, make_nott_logo_title_header
from nottcontrol.theme import apply_instrument_window_style
from nottcontrol.components.cryo_redis_charts import CryoHistoryPanel, SeriesConfig
from nottcontrol.components.cryo_temp_panel import (
    CryoEquipmentPanel,
    CryoTemperaturePanel,
)
from nottcontrol.sensors import (
    coerce_sensor_value,
    filter_temperature_sensors,
    is_vote_temperature_tag,
    load_pressure_sensors,
    load_temperature_sensors,
    pressure_display_name,
    pressure_unit,
    temperature_group,
)


class CryostatWindow(QMainWindow):
    closing = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Cryostat monitor")
        self.resize(1040, 900)
        apply_window_icon(self)
        apply_instrument_window_style(self)

        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(
            make_nott_logo_title_header("Cryostat monitor"),
            alignment=Qt.AlignLeft,
        )

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.equipment_panel = CryoEquipmentPanel()
        self.equipment_panel.setup(
            [(item.key, item.label) for item in parent.cryo_status_items]
        )
        self.equipment_panel.setMaximumWidth(320)
        top_row.addWidget(self.equipment_panel, stretch=0)

        self.temp_panel = CryoTemperaturePanel()
        self.temp_panel.setup(
            parent.temp_tags, parent.temp_display_names, dense=True
        )
        top_row.addWidget(self.temp_panel, stretch=1)
        layout.addLayout(top_row, stretch=0)

        self.history_panel = CryoHistoryPanel()
        layout.addWidget(self.history_panel, stretch=1)

        (
            _temp_opc_nodes,
            temp_redis_keys,
            _temp_display_names,
            temp_tags,
        ) = load_temperature_sensors(sensor_config_path)
        (
            _plot_temp_opc_nodes,
            plot_temp_redis_keys,
            _plot_temp_display_names,
            plot_temp_tags,
        ) = filter_temperature_sensors(
            _temp_opc_nodes,
            temp_redis_keys,
            _temp_display_names,
            temp_tags,
            tag_filter=is_vote_temperature_tag,
        )
        (
            _pressure_opc_nodes,
            pressure_redis_keys,
            _pressure_display_names,
            pressure_tags,
            _pressure_units,
        ) = load_pressure_sensors(sensor_config_path)

        temp_series = [
            SeriesConfig(redis_key, temperature_group(tag))
            for redis_key, tag in zip(plot_temp_redis_keys, plot_temp_tags)
        ]
        pressure_series = [
            SeriesConfig(redis_key, pressure_display_name(tag))
            for redis_key, tag in zip(pressure_redis_keys, pressure_tags)
            if pressure_unit(tag) in ("mbar", "hPa")
        ]
        self.history_panel.configure(
            parent.redis_client,
            temp_series,
            pressure_series,
        )

        self.t = QTimer()
        self.t.timeout.connect(self.refresh)
        self.t.start(5000)

        self.t_history = QTimer()
        self.t_history.timeout.connect(self.history_panel.refresh)
        self.t_history.start(15000)
        self.refresh()

    def closeEvent(self, *args):
        self.t.stop()
        self.t_history.stop()
        self.closing.emit()
        super().closeEvent(*args)

    def refresh(self) -> None:
        cache = self.parent.get_cryo_cache()
        if cache.get("updated_at") is None:
            return
        self.sync_from_values(
            self.parent.temp_tags,
            cache["temp_values"],
            self.parent.pressure_tags,
            cache["pressure_values"],
            cache["equipment_status"],
            cache["updated_at"],
        )

    def sync_from_values(
        self,
        temp_tags: list[str],
        temp_values: list,
        pressure_tags: list[str],
        pressure_values: list,
        equipment_status: dict[str, object] | None,
        updated_at: datetime | None = None,
    ) -> None:
        temp_tag_values = {
            tag: coerce_sensor_value(value) for tag, value in zip(temp_tags, temp_values)
        }
        self.equipment_panel.update_values(equipment_status, updated_at)
        self.temp_panel.update_values(temp_tag_values)
