from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.uic import loadUi
from opcua import OPCUAConnection
from configparser import ConfigParser
from components.shutter import Shutter

class ShutterWindow(QMainWindow):
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

        self.ui.actionClose_all.triggered.connect(self.close_all)
        self.ui.actionOpen_all.triggered.connect(self.open_all)

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
        self.ui.shutter_widget_1.refresh_status()
        self.ui.shutter_widget_2.refresh_status()
        self.ui.shutter_widget_3.refresh_status()
        self.ui.shutter_widget_4.refresh_status()
    
    def load_positions(self):
        self.ui.shutter_widget_1.load_position()
        self.ui.shutter_widget_2.load_position()
        self.ui.shutter_widget_3.load_position()
        self.ui.shutter_widget_4.load_position()
    
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