from datetime import datetime

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from nottcontrol import sensor_config_path
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
    temperature_group,
)


class CryostatWindow(QMainWindow):
    closing = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Cryostat monitor")
        self.resize(1040, 900)

        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.equipment_panel = CryoEquipmentPanel()
        self.equipment_panel.setup(
            [(item.key, item.label) for item in parent.cryo_status_items]
        )
        self.equipment_panel.setMaximumWidth(320)
        top_row.addWidget(self.equipment_panel, stretch=0)

        self.temp_panel = CryoTemperaturePanel()
        self.temp_panel.setup(parent.temp_tags, parent.temp_display_names)
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
        if not self.parent.sensor_opc_nodes:
            return
        try:
            values = self.parent.opcua_conn_cry.read_nodes(self.parent.sensor_opc_nodes)
            values_by_node = dict(zip(self.parent.sensor_opc_nodes, values))
            temp_values = [values_by_node[node] for node in self.parent.temp_opc_nodes]
            pressure_values = [
                values_by_node[node] for node in self.parent.pressure_opc_nodes
            ]
            equipment_status = self.parent._read_cryo_equipment_status()
            self.sync_from_values(
                self.parent.temp_tags,
                temp_values,
                self.parent.pressure_tags,
                pressure_values,
                equipment_status,
                datetime.utcnow(),
            )
            self.history_panel.refresh()
        except Exception as e:
            print(f"Cryostat window refresh failed: {e}")

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
