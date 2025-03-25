import sys
import subprocess
import asyncio
from configparser import ConfigParser
from PyQt5.QtWidgets import QMainWindow, QWidget
from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon, QPixmap

class VisibleCamerasGUI(QMainWindow):
    def __init__(self):
        super(VisibleCamerasGUI, self).__init__()
        self.ui = loadUi('visible_cameras.ui', self)

        config = ConfigParser()
        config.read('visible_cameras.ini')

        self.ip1 = config['CAMERA1']['ip']
        self.ip2 = config['CAMERA2']['ip']

        self.ui.lbl_IP1.setText(self.ip1)
        self.ui.lbl_IP2.setText(self.ip2)

        asyncio.run(self.update_images())
    
    async def update_images(self):
        proc = await asyncio.create_subprocess_exec(
            "./Arena/Cpp_Save_Png_Mod", self.ip1, "/home/labo/images/image1.png",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        # result = subprocess.run(["./Arena/Cpp_Save_Png_Mod", self.ip1, "/home/labo/images/image1.png"])
        # result.check_returncode()

        stdout, stderr = await proc.communicate()
        proc.returncode

        pixmap = QPixmap("/home/labo/images/image1.png")

        self.ui.lbl_image1.setPixmap(pixmap)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = VisibleCamerasGUI()
    main_window.show()
    sys.exit(app.exec_())