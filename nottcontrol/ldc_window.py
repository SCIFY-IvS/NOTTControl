from __future__ import annotations

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QGridLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from nottcontrol import config
from nottcontrol.app_icon import install_nott_logo_header
from nottcontrol.components.delayline import get_motor_args
from nottcontrol.components.device_polling import (
    motor_position_opc_nodes,
    motor_status_opc_nodes,
    split_motor_position_values,
    split_motor_status_values,
)
from nottcontrol.components.motor import Motor
from nottcontrol.motorwidget import MotorWidget

LDC_SUBSYSTEMS: tuple[tuple[str, str, str], ...] = (
    ("co2", "CO2 Chambers", "Position (µm)"),
    ("glass", "Glass Windows", "Position (µm)"),
    ("biref", "Birefringence Plates", "Angle (°)"),
)


def create_ldc_motors(opcua_conn, prefix: str) -> list[Motor]:
    indices = config.getarray("ldc", f"{prefix}_idx_available", dtype=int)
    motors: list[Motor] = []
    for index in indices:
        args = get_motor_args(prefix, index)
        motors.append(
            Motor(
                opcua_conn,
                args["opcua_prefix"],
                args["name"],
                args["speed"],
            )
        )
    return motors


class LdcWindow(QMainWindow):
    closing = pyqtSignal()

    def __init__(self, parent, opcua_conn, redis_client):
        super().__init__(parent)
        self.parent = parent
        self.opcua_conn = opcua_conn
        self.redis_client = redis_client
        self._subsystem_widgets: list[dict[str, object]] = []

        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        self._tabs = QTabWidget()
        for prefix, title, units in LDC_SUBSYSTEMS:
            self._tabs.addTab(
                self._build_subsystem_tab(prefix, units),
                title,
            )
        outer.addWidget(self._tabs)

        self.setCentralWidget(content)
        install_nott_logo_header(self, title="LDC Control")
        self.setMinimumSize(1180, 720)

        position_save_interval_ms = config.getint(
            "SENSORS", "position_save_interval_ms", fallback=1000
        )
        self.t_pos = QTimer()
        self.t_pos.timeout.connect(self.load_positions)
        self.t_pos.start(position_save_interval_ms)

        self.t = QTimer()
        self.t.timeout.connect(self.refresh_status)
        self.t.start(500)

    def _build_subsystem_tab(self, prefix: str, units: str) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        hint = QLabel(f"Longitudinal dispersion corrector — {units}")
        hint.setStyleSheet('font: 9pt "Segoe UI"; color: rgb(100, 100, 100);')
        layout.addWidget(hint)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        motors = create_ldc_motors(self.opcua_conn, prefix)
        widgets: list[MotorWidget] = []
        for slot, motor in enumerate(motors):
            widget = MotorWidget(grid_host)
            widget.setMinimumHeight(220)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            widget.setup(self.opcua_conn, self.redis_client, motor)
            row, column = divmod(slot, 2)
            grid.addWidget(widget, row, column)
            widgets.append(widget)

        layout.addWidget(grid_host, stretch=1)
        self._subsystem_widgets.append(
            {
                "prefix": prefix,
                "motors": motors,
                "widgets": widgets,
            }
        )
        return tab

    def closeEvent(self, *args):
        self.t.stop()
        self.t_pos.stop()
        self.closing.emit()
        super().closeEvent(*args)

    def refresh_status(self) -> None:
        for subsystem in self._subsystem_widgets:
            motors = subsystem["motors"]
            widgets = subsystem["widgets"]
            if not motors:
                continue
            prefixes = [motor._prefix for motor in motors]
            try:
                values = self.opcua_conn.read_nodes(
                    motor_status_opc_nodes(prefixes)
                )
                for widget, row in zip(
                    widgets,
                    split_motor_status_values(values, len(widgets)),
                ):
                    widget.apply_status_values(*row)
            except Exception as exc:
                print(f"LDC status ({subsystem['prefix']}): {exc}")

    def load_positions(self) -> None:
        for subsystem in self._subsystem_widgets:
            motors = subsystem["motors"]
            widgets = subsystem["widgets"]
            if not motors:
                continue
            prefixes = [motor._prefix for motor in motors]
            try:
                values = self.opcua_conn.read_nodes(
                    motor_position_opc_nodes(prefixes)
                )
                for widget, row in zip(
                    widgets,
                    split_motor_position_values(values, len(widgets)),
                ):
                    widget.apply_position_values(*row)
            except Exception as exc:
                print(f"LDC positions ({subsystem['prefix']}): {exc}")
