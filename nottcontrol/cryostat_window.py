from datetime import datetime

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QScrollArea, QVBoxLayout, QWidget

from nottcontrol.components.cryo_temp_panel import (
    CryoEquipmentPanel,
    CryoPressurePanel,
    CryoTemperaturePanel,
)
from nottcontrol.sensors import coerce_sensor_value


class CryostatWindow(QMainWindow):
    closing = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Cryostat monitor")
        self.resize(920, 780)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        scroll.setWidget(container)
        self.setCentralWidget(scroll)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.equipment_panel = CryoEquipmentPanel()
        self.equipment_panel.setup(
            [(item.key, item.label) for item in parent.cryo_status_items]
        )
        layout.addWidget(self.equipment_panel)

        self.pressure_panel = CryoPressurePanel()
        self.pressure_panel.setup(parent.pressure_tags, parent.pressure_display_names)
        layout.addWidget(self.pressure_panel)

        self.temp_panel = CryoTemperaturePanel()
        self.temp_panel.setup(parent.temp_tags, parent.temp_display_names)
        layout.addWidget(self.temp_panel)

        self.t = QTimer()
        self.t.timeout.connect(self.refresh)
        self.t.start(5000)
        self.refresh()

    def closeEvent(self, *args):
        self.t.stop()
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
        pressure_tag_values = {
            tag: coerce_sensor_value(value)
            for tag, value in zip(pressure_tags, pressure_values)
        }
        self.equipment_panel.update_values(equipment_status, updated_at)
        self.pressure_panel.update_values(pressure_tag_values)
        self.temp_panel.update_values(temp_tag_values)
