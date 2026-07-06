import numpy as np
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.uic import loadUi

from nottcontrol import config
from nottcontrol.components.pypiezo import piezointerface
from nottcontrol.piezowidget import PiezoWidget


class PiezosWindow(QMainWindow):
    closing = pyqtSignal()

    def __init__(self, parent):
        super(PiezosWindow, self).__init__()
        self.parent = parent

        try:
            self._piezo_interf = piezointerface()
        except Exception as e:
            print(f"Could not open piezo interface: {e}")
            self._piezo_interf = piezointerface.__new__(piezointerface)
            self._piezo_interf.ser = None
            self._piezo_interf.n = 4
            self._piezo_interf.values = np.zeros(4)
            self._piezo_interf.listening = False

        self.ui = loadUi("piezos.ui", self)

        port = config["PIEZO"].get("port", "/dev/ttyACM0")
        if self._piezo_interf.ser is None:
            self.ui.label_connection.setText(
                f"Piezo serial port not connected ({port})"
            )
        else:
            self.ui.label_connection.setText(f"Connected on {port}")

        self.ui.piezo_widget_1.setup(self._piezo_interf, 0, "Piezo 1")
        self.ui.piezo_widget_2.setup(self._piezo_interf, 1, "Piezo 2")
        self.ui.piezo_widget_3.setup(self._piezo_interf, 2, "Piezo 3")
        self.ui.piezo_widget_4.setup(self._piezo_interf, 3, "Piezo 4")

        self.t = QTimer()
        self.t.timeout.connect(self.refresh_positions)
        self.t.start(500)
        self.refresh_positions()

    def closeEvent(self, *args):
        self.t.stop()
        if getattr(self._piezo_interf, "ser", None) is not None:
            try:
                self._piezo_interf.reset_server()
                self._piezo_interf.listening = False
                self._piezo_interf.ser.close()
            except Exception as e:
                print(f"Error closing piezo interface: {e}")
        self.closing.emit()
        super().closeEvent(*args)

    def refresh_positions(self):
        for widget in (
            self.ui.piezo_widget_1,
            self.ui.piezo_widget_2,
            self.ui.piezo_widget_3,
            self.ui.piezo_widget_4,
        ):
            widget.refresh_position()
