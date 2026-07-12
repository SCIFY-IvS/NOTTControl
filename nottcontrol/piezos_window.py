import numpy as np
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.uic import loadUi

from nottcontrol import config
from nottcontrol.components.pypiezo import piezointerface
from nottcontrol.app_icon import install_nott_logo_header
from nottcontrol.theme import PANEL_LABEL_STYLE


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
        install_nott_logo_header(self, title="Piezo Control")
        self.ui.label_connection.setStyleSheet(PANEL_LABEL_STYLE)

        port = config["PIEZO"].get("port", "/dev/ttyACM0")
        if self._piezo_interf.ser is None:
            self.ui.label_connection.setText(
                f"Piezo serial port not connected ({port})"
            )
        else:
            self.ui.label_connection.setText(f"Connected on {port}")

        for index, widget in enumerate(
            (
                self.ui.piezo_widget_1,
                self.ui.piezo_widget_2,
                self.ui.piezo_widget_3,
                self.ui.piezo_widget_4,
            )
        ):
            widget.setup(self._piezo_interf, index, f"Piezo {index + 1}", port)

        self.t = QTimer()
        self.t.timeout.connect(self.refresh_positions)
        self.t.start(500)
        self.refresh_positions()

    def closeEvent(self, *args):
        self.t.stop()
        for widget in (
            self.ui.piezo_widget_1,
            self.ui.piezo_widget_2,
            self.ui.piezo_widget_3,
            self.ui.piezo_widget_4,
        ):
            worker = getattr(widget, "_scan_worker", None)
            if worker is not None and worker.isRunning():
                worker.wait(2000)
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
