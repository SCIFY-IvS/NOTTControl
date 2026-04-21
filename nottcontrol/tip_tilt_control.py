from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.uic import loadUi
from nottcontrol.opcua import OPCUAConnection
from nottcontrol import config
from nottcontrol.components.shutter import Shutter
from nottcontrol.script.lib.nott_TTM_alignment import alignment

class TipTiltControl(QMainWindow):
    closing = pyqtSignal()

    def __init__(self, parent, opcua_conn, redis_client):
        super(TipTiltControl, self).__init__()

        self.parent = parent

        url =  config['DEFAULT']['opcuaaddress']

        # save the OPC UA connection
        self.opcua_conn = OPCUAConnection(url)
        self.opcua_conn.connect()

        self.redis_client = redis_client

        self.ui = loadUi('tip_tilt_control.ui', self)

        tt_interface = alignment()

        self.ui.tip_tilt_1.setup(self.opcua_conn, self.redis_client, 0, tt_interface)
        self.ui.tip_tilt_2.setup(self.opcua_conn, self.redis_client, 1, tt_interface)
        self.ui.tip_tilt_3.setup(self.opcua_conn, self.redis_client, 2, tt_interface)
        self.ui.tip_tilt_4.setup(self.opcua_conn, self.redis_client, 3, tt_interface)

    def closeEvent(self, *args):
        self.opcua_conn.disconnect()
        self.closing.emit()
        super().closeEvent(*args)