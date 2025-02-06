from PyQt5.QtWidgets import QMainWindow, QWidget
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.uic import loadUi
from opcua import OPCUAConnection
from asyncua import ua
from datetime import datetime
from redisclient import RedisClient
from camera.scify import MainWindow as camera_ui
from configparser import ConfigParser
from components.motor import Motor
from shutters_window import ShutterWindow

class TipTiltWindow(QWidget):
    closing = pyqtSignal()

    def __init__(self, parent, opcua_conn, redis_client):
        super(TipTiltWindow, self).__init__()

        self.parent = parent

        config = ConfigParser()
        config.read('config.ini')
        url =  config['DEFAULT']['opcuaaddress']

        # save the OPC UA connection
        self.opcua_conn = OPCUAConnection(url)
        self.opcua_conn.connect()

        self._motor_ntpa1 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTPA1", "NTPA1")
        self._motor_ntta1 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTTA1", "NTTA1")
        self._motor_ntpa2 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTPA2", "NTPA2")
        self._motor_ntta2 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTTA2", "NTTA2")
        self._motor_ntpa3 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTPA3", "NTPA3")
        self._motor_ntta3 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTTA3", "NTTA3")
        self._motor_ntpa4 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTPA4", "NTPA4")
        self._motor_ntta4 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTTA4", "NTTA4")

        self._motor_ntpb1 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTPB1", "NTPB1")
        self._motor_nttb1 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTTB1", "NTTB1")
        self._motor_ntpb2 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTPB2", "NTPB2")
        self._motor_nttb2 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTTB2", "NTTB2")
        self._motor_ntpb3 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTPB3", "NTPB3")
        self._motor_nttb3 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTTB3", "NTTB3")
        self._motor_ntpb4 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTPB4", "NTPB4")
        self._motor_nttb4 = Motor(opcua_conn, "ns=4;s=MAIN.nott_ics.TipTilt.NTTB4", "NTTB4")

        self.redis_client = redis_client

        self.ui = loadUi('tiptilt_window.ui', self)

        self.ui.motor_widget_NTPA1.setup(self.opcua_conn, self.redis_client, self._motor_ntpa1)
        self.ui.motor_widget_NTTA1.setup(self.opcua_conn, self.redis_client, self._motor_ntta1)
        self.ui.motor_widget_NTPA2.setup(self.opcua_conn, self.redis_client, self._motor_ntpa2)
        self.ui.motor_widget_NTTA2.setup(self.opcua_conn, self.redis_client, self._motor_ntta2)
        self.ui.motor_widget_NTPA3.setup(self.opcua_conn, self.redis_client, self._motor_ntpa3)
        self.ui.motor_widget_NTTA3.setup(self.opcua_conn, self.redis_client, self._motor_ntta3)
        self.ui.motor_widget_NTPA4.setup(self.opcua_conn, self.redis_client, self._motor_ntpa4)
        self.ui.motor_widget_NTTA4.setup(self.opcua_conn, self.redis_client, self._motor_ntta4)

        self.ui.motor_widget_NTPB1.setup(self.opcua_conn, self.redis_client, self._motor_ntpb1)
        self.ui.motor_widget_NTTB1.setup(self.opcua_conn, self.redis_client, self._motor_nttb1)
        self.ui.motor_widget_NTPB2.setup(self.opcua_conn, self.redis_client, self._motor_ntpb2)
        self.ui.motor_widget_NTTB2.setup(self.opcua_conn, self.redis_client, self._motor_nttb2)
        self.ui.motor_widget_NTPB3.setup(self.opcua_conn, self.redis_client, self._motor_ntpb3)
        self.ui.motor_widget_NTTB3.setup(self.opcua_conn, self.redis_client, self._motor_nttb3)
        self.ui.motor_widget_NTPB4.setup(self.opcua_conn, self.redis_client, self._motor_ntpb4)
        self.ui.motor_widget_NTTB4.setup(self.opcua_conn, self.redis_client, self._motor_nttb4)

        self._motor_widget_list = {self.ui.motor_widget_NTPA1, self.ui.motor_widget_NTTA1, self.ui.motor_widget_NTPA2, self.ui.motor_widget_NTTA2,
                                   self.ui.motor_widget_NTPA3, self.ui.motor_widget_NTTA3, self.ui.motor_widget_NTPA4, self.ui.motor_widget_NTTA4,
                                   self.ui.motor_widget_NTPB1, self.ui.motor_widget_NTTB1, self.ui.motor_widget_NTPB2, self.ui.motor_widget_NTTB2,
                                   self.ui.motor_widget_NTPB3, self.ui.motor_widget_NTTB3, self.ui.motor_widget_NTPB4, self.ui.motor_widget_NTTB4}

        self._activeCommand = None

        self.t_pos = QTimer()
        self.t_pos.timeout.connect(self.load_positions)
        self.t_pos.start(10)

        self.t = QTimer()
        self.t.timeout.connect(self.refresh_status)
        self.t.start(500)

    def closeEvent(self, *args):
        self.t.stop()
        self.t_pos.stop()
        self.opcua_conn.disconnect()
        self.closing.emit()
        super().closeEvent(*args)

    def refresh_status(self):
        for motor_widget in self._motor_widget_list:
            motor_widget.refresh_status()
    
    def load_positions(self):
        for motor_widget in self._motor_widget_list:
            motor_widget.load_position()