from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.uic import loadUi
from opcua import OPCUAConnection
from configparser import ConfigParser
from components.shutter import Shutter

class ShutterWindow(QWidget):
    closing = pyqtSignal()

    def __init__(self, parent, opcua_conn, redis_client):
        super(ShutterWindow, self).__init__()

        self.parent = parent

        config = ConfigParser()
        config.read('config.ini')
        url =  config['DEFAULT']['opcuaaddress']

        # save the OPC UA connection
        self.opcua_conn = OPCUAConnection(url)
        self.opcua_conn.connect()

        self._shutter = Shutter(self.opcua_conn, "ns=4;s=MAIN.nott_ics.Shutters.NSH1", 'Shutter 1')

        self.redis_client = redis_client

        self.ui = loadUi('shutters.ui', self)

        self.ui.shutter_widget.setup(self.opcua_conn, self.redis_client, self._shutter)

        self.t_pos = QTimer()
        self.t_pos.timeout.connect(self.load_positions)
        self.t_pos.start(5)

        self.t = QTimer()
        self.t.timeout.connect(self.refresh_status)
        self.t.start(200)

    def closeEvent(self, *args):
        self.t.stop()
        self.t_pos.stop()
        self.opcua_conn.disconnect()
        self.closing.emit()
        super().closeEvent(*args)

    def refresh_status(self):
        self.ui.shutter_widget.refresh_status()
    
    def load_positions(self):
        self.ui.shutter_widget.load_position()