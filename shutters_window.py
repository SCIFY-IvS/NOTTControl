from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.uic import loadUi
from opcua import OPCUAConnection
from asyncua.sync import Client
import asyncio
from asyncua import ua
import time
from datetime import datetime
from redisclient import RedisClient
from configparser import ConfigParser
from enum import Enum
from components.shutter import Shutter
from shutterwidget import ShutterWidget

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

        self._shutter = Shutter(self.opcua_conn, "ns=4;s=MAIN.shutter_1", 'Shutter 1')

        self.redis_client = redis_client

        self.ui = loadUi('shutters.ui', self)

        self.ui.shutter_widget.setup(self.opcua_conn, self.redis_client, self._shutter)

        self.timestamp = None

        self.t = QTimer()
        self.t.timeout.connect(self.refresh_status)
        self.t.start(500)

    def closeEvent(self, *args):
        self.t.stop()
        self.opcua_conn.disconnect()
        self.closing.emit()
        super().closeEvent(*args)

    def refresh_status(self):
        self.ui.shutter_widget.refresh_status()