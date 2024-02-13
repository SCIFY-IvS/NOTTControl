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

        self._motor1 = Motor(self.opcua_conn, "ns=4;s=MAIN.tiptilt_1", 'tiptilt_1')

        self.redis_client = redis_client

        self.ui = loadUi('tiptilt_window.ui', self)


        self.ui.motor_widget_1.setup(self.opcua_conn, self.redis_client, self._motor1)

        self._activeCommand = None

        self.timestamp = None
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
    
    def startCameraRecording(self):
        self.parent.camera_window.start_recording()
    
    def stopCameraRecording(self):
        self.parent.camera_window.stop_recording()

    def executeCommand(self, cmd):
        cmd.execute()

        if self._activeCommand is not None:
            raise Exception('Already an active command!')
        
        self._activeCommand = cmd
        self.ui.dl_command_status.setText(f'Executing command \'{self._activeCommand.text()}\' ...')

        self.ui.pb_homing.setEnabled(False)
        self.ui.pb_move_rel.setEnabled(False)
        self.ui.pb_move_abs.setEnabled(False)
        self.ui.pb_scan.setEnabled(False)
    
    def clearActiveCommand(self):
        self._activeCommand = None
        self.ui.dl_command_status.setText('Not executing command')

        self.ui.pb_homing.setEnabled(True)
        self.ui.pb_move_rel.setEnabled(True)
        self.ui.pb_move_abs.setEnabled(True)
        self.ui.pb_scan.setEnabled(True)

    def refresh_status(self):
        self.ui.motor_widget_1.refresh_status()
    
    def load_positions(self):
        self.ui.motor_widget_1.load_position()