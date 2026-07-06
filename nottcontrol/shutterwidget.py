from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal
from PyQt5.uic import loadUi
from datetime import datetime

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

            self.ui.label_status.setText(str(status))
            self.ui.label_state.setText(str(state))
            self.ui.label_subState.setText(str(substate))
            hwStatus = self.get_shutter_status()
            self.ui.label_opened.setText(str(hwStatus))
        except Exception as e:
            print(e)
            self.ui.label_error.setText(str(e))
    
    def load_position(self):
        try:
            hwStatus = self.get_shutter_status()

            shutter_pos = -1
            if hwStatus == "Open":
                shutter_pos = 1
            elif hwStatus == "Closed":
                shutter_pos = 0
            if shutter_pos < 0:
                return

            now = datetime.utcnow()
            if (
                self.timestamp is None
                or (now - self.timestamp).total_seconds() >= 1.0
                or shutter_pos != getattr(self, "_last_redis_pos", shutter_pos)
            ):
                self.redis_client.add_shutter_position(
                    self._shutter.name, now, shutter_pos
                )
                self._last_redis_pos = shutter_pos
                self.timestamp = now
        except Exception as e:
            print(e)
            self.ui.label_error.setText(str(e))
    
    def get_shutter_status(self):
        return self._shutter.get_hardware_state()

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