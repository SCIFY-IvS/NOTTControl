from PyQt5.QtWidgets import QGridLayout, QMainWindow, QSizePolicy
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.uic import loadUi
from nottcontrol import config
from nottcontrol.app_icon import install_nott_logo_header

from nottcontrol.components.filterwheel.SMD_driver_ethernet import SMD_driver_ethernet

class FilterWheelWindow(QMainWindow):
    closing = pyqtSignal()

    pos_spectrograph = "Spectrograph"
    pos_open = "Open"
    pos_closed = "Closed"

    def __init__(self, parent, redis_client):
            super(FilterWheelWindow, self).__init__()

            self.parent = parent

            self.ui = loadUi('filterwheel.ui', self)
            install_nott_logo_header(self, title="Shutter Control")

            ip = config["FILTERWHEEL"]["ip"]
            port = int(config["FILTERWHEEL"]["port"])

            self.driver = SMD_driver_ethernet(ip, port)

            self.ui.cb_pos.addItems([self.pos_spectrograph, self.pos_open, self.pos_closed])
            self.ui.btn_move.clicked.connect(self.move)
            self.ui.btn_home.clicked.connect(self.home)

            self.t = QTimer()
            self.t.timeout.connect(self.refresh)
            self.t.start(1000)

    def refresh(self):
        try:
            position = self.driver.get_position()
            self.ui.lbl_position = str(position)

            if self.driver.is_error_active():
                 self.ui.label_error.setText(f"Filterwheel reports error: {self.driver.estatus}")
            else:
                self.ui.label_error.clear()
        except Exception as e:
            print(e)
            self.ui.label_error.setText(str(e))

    def move(self):
        try:
            pos = str(self.ui.cb_pos.currentText())

            match pos:
                case self.pos_spectrograph:
                       self.driver.move_to_spectrograph_pos()
                case self.pos_open:
                       self.driver.move_to_open_pos()
                case self.pos_closed:
                       self.driver.move_to_closed_pos()
        except Exception as e:
            print(e)
            #TODO
    
    def home(self):
        try:
             self.driver.run_homing_procedure()
        except Exception as e:
            print(e)
            #TODO
    
    def closeEvent(self, *args):
        self.t.stop()
        self.closing.emit()
        super().closeEvent(*args)