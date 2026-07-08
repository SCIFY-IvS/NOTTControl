from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.uic import loadUi
from nottcontrol import config
from nottcontrol.components.shutter import Shutter
from nottcontrol.components.device_polling import (
    shutter_status_opc_nodes,
    split_shutter_status_values,
)

class ShutterWindow(QMainWindow):
    closing = pyqtSignal()

    def __init__(self, parent, opcua_conn, redis_client):
        super(ShutterWindow, self).__init__()

        self.parent = parent

        self.opcua_conn = opcua_conn

        self._shutter1 = Shutter(self.opcua_conn, "ns=4;s=MAIN.nott_ics.Shutters.NSH1", 'Shutter 1')
        self._shutter2 = Shutter(self.opcua_conn, "ns=4;s=MAIN.nott_ics.Shutters.NSH2", 'Shutter 2')
        self._shutter3 = Shutter(self.opcua_conn, "ns=4;s=MAIN.nott_ics.Shutters.NSH3", 'Shutter 3')
        self._shutter4 = Shutter(self.opcua_conn, "ns=4;s=MAIN.nott_ics.Shutters.NSH4", 'Shutter 4')

        self.redis_client = redis_client

        self.ui = loadUi('shutters.ui', self)

        self.ui.shutter_widget_1.setup(self.opcua_conn, self.redis_client, self._shutter1)
        self.ui.shutter_widget_2.setup(self.opcua_conn, self.redis_client, self._shutter2)
        self.ui.shutter_widget_3.setup(self.opcua_conn, self.redis_client, self._shutter3)
        self.ui.shutter_widget_4.setup(self.opcua_conn, self.redis_client, self._shutter4)

        self._shutter_widgets = [
            (self._shutter1, self.ui.shutter_widget_1),
            (self._shutter2, self.ui.shutter_widget_2),
            (self._shutter3, self.ui.shutter_widget_3),
            (self._shutter4, self.ui.shutter_widget_4),
        ]
        self._shutter_prefixes = [
            shutter._prefix for shutter, _ in self._shutter_widgets
        ]

        self.ui.actionClose_all.triggered.connect(self.close_all)
        self.ui.actionOpen_all.triggered.connect(self.open_all)

        self.t_pos = QTimer()
        self.t_pos.timeout.connect(self.load_positions)
        position_save_interval_ms = config.getint(
            "SENSORS", "position_save_interval_ms", fallback=1000
        )
        self.t_pos.start(position_save_interval_ms)

        self.t = QTimer()
        self.t.timeout.connect(self.refresh_status)
        self.t.start(200)

    def closeEvent(self, *args):
        self.t.stop()
        self.t_pos.stop()
        self.closing.emit()
        super().closeEvent(*args)

    def refresh_status(self):
        try:
            values = self.opcua_conn.read_nodes(
                shutter_status_opc_nodes(self._shutter_prefixes)
            )
            for (shutter, widget), row in zip(
                self._shutter_widgets,
                split_shutter_status_values(values, len(self._shutter_widgets)),
            ):
                status, state, substate, position = row
                hw_status = shutter.hardware_state_from_position(position)
                widget.apply_status_values(status, state, substate, hw_status)
        except Exception as e:
            print(e)
    
    def load_positions(self):
        try:
            values = self.opcua_conn.read_nodes(
                shutter_status_opc_nodes(self._shutter_prefixes)
            )
            for (shutter, widget), row in zip(
                self._shutter_widgets,
                split_shutter_status_values(values, len(self._shutter_widgets)),
            ):
                hw_status = shutter.hardware_state_from_position(row[3])
                widget.apply_hardware_state(hw_status)
        except Exception as e:
            print(e)
    
    def close_all(self):
        try:
            self._shutter1.close()
            self._shutter2.close()
            self._shutter3.close()
            self._shutter4.close()
        except Exception as e:
            print(f"Error calling RPC method: {e}")
    
    def open_all(self):
        try:
            self._shutter1.open()
            self._shutter2.open()
            self._shutter3.open()
            self._shutter4.open()
        except Exception as e:
            print(f"Error calling RPC method: {e}")