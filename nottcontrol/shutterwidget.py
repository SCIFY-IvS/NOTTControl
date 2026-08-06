from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal
from PyQt5.uic import loadUi
from datetime import datetime

from nottcontrol.theme import style_shutter_widget

class ShutterWidget(QWidget):
    closing = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
    
    def setup(self, opcua_conn, redis_client, shutter):
        self.opcua_conn = opcua_conn
        self._shutter = shutter
        self.redis_client = redis_client
        self.timestamp = None

        self.ui = loadUi('shutter_widget.ui', self)
        style_shutter_widget(self)

        self.ui.pb_reset.clicked.connect(self.reset)
        self.ui.pb_init.clicked.connect(self.init)
        self.ui.pb_enable.clicked.connect(self.enable)
        self.ui.pb_disable.clicked.connect(self.disable)
        self.ui.pb_stop.clicked.connect(self.stop)

        self.ui.pb_open.clicked.connect(self.open)
        self.ui.pb_close.clicked.connect(self.close)

        self.ui.label_name.setText(self._shutter.name)

    def refresh_status(self):
        try:
            status, state, substate = self._shutter.getStatusInformation()
            hw_status = self._shutter.get_hardware_state()
            self.apply_status_values(status, state, substate, hw_status)
        except Exception as e:
            print(e)
            self.ui.label_error.setText(str(e))

    def apply_status_values(self, status, state, substate, hw_status):
        self.ui.label_status.setText(str(status))
        self.ui.label_state.setText(str(state))
        self.ui.label_subState.setText(str(substate))
        self.ui.label_opened.setText(str(hw_status))
    
    def load_position(self):
        try:
            current_pos_mm, _speed = self._shutter.getPositionAndSpeed()[:2]
            hw_status = self._shutter.hardware_state_from_position(current_pos_mm)
            self.apply_hardware_state(hw_status)
            self._log_shutter_position(float(current_pos_mm))
        except Exception as e:
            print(e)
            self.ui.label_error.setText(str(e))

    def apply_hardware_state(self, hw_status):
        self.ui.label_opened.setText(str(hw_status))

    def _log_shutter_position(self, position_mm: float) -> None:
        now = datetime.utcnow()
        if (
            self.timestamp is None
            or (now - self.timestamp).total_seconds() >= 1.0
            or abs(position_mm - getattr(self, "_last_redis_pos", position_mm)) >= 0.05
        ):
            self.redis_client.add_shutter_position(
                self._shutter.name, now, position_mm
            )
            self._last_redis_pos = position_mm
            self.timestamp = now

    def reset(self):
        try:
            res = self._shutter.reset()
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    def init(self):
        try:
            res = self._shutter.init()
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    def enable(self):
        try:
            res = self._shutter.enable()
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    def disable(self):
        try:
            res = self._shutter.disable()
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    def stop(self):
        try:
            res = self._shutter.stop()
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    def open(self):
        try:
            res = self._shutter.open()
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    def close(self):
        try:
            res = self._shutter.close()
        except Exception as e:
            print(f"Error calling RPC method: {e}")