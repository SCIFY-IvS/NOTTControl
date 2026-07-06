from PyQt5.QtWidgets import QMainWindow
from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication
import sys
from nottcontrol.camera.macie import macie_interface

class MacieControl(QMainWindow):
    def __init__(self):
        super(MacieControl, self).__init__()
        self.ui = loadUi('MacieControl.ui', self)
        self.connectSignalSlots()
        self._macie_interface = macie_interface.MacieInterface()
    
    def connectSignalSlots(self):
        self.ui.button_init.clicked.connect(self.init_camera)
        self.ui.button_powerOn.clicked.connect(self.power_on)
        self.ui.button_powerOff.clicked.connect(self.power_off)
        self.ui.button_take_background.clicked.connect(self.take_background)
        self.ui.button_live.clicked.connect(self.live_clicked)
        self.ui.button_acquire.clicked.connect(self.acquire)
        self.ui.button_halt.clicked.connect(self.halt)
    
    def init_camera(self):
        print("executing init camera")
        self._macie_interface.init_camera()
    
    def power_on(self):
        print("executing power on")
        self._macie_interface.power_on()

    def power_off(self):
        print("executing power off")
        self._macie_interface.power_off()
    
    def take_background(self):
        print("executing take background")
    
    def live_clicked(self):
        print("executing live_clicked")
    
    def acquire(self):
        print("executing acquire")
        self._macie_interface.acquire()
    
    def halt(self):
        print("executing halt")
    


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MacieControl()
    window.show()
    sys.exit(app.exec())