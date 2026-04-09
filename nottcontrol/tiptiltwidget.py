from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal
from PyQt5.uic import loadUi
from datetime import datetime
from nottcontrol.script import config_alignment
import numpy as np

class TipTiltWidget(QWidget):
    IMAGE_PLANE = "Image Plane"
    PUPIL_PLANE = "Pupil Plane"

    def __init__(self, parent):
        QWidget.__init__(self, parent)
    
    def setup(self, opcua_conn, redis_client, beam_index, tt_interface):
        self._opcua_conn = opcua_conn
        self._redis_client = redis_client
        self._beam_index = beam_index
        self._tt_interface = tt_interface

        self.ui = loadUi('tip_tilt.ui', self)
        self.ui.label_beam.setText(f'Beam {self._beam_index}')

        self.setup_plane_combobox()
        
        #read default step size from config
        default_step = config_alignment["tip_tilt_control"]["step_default"]
        self.ui.le_stepsize.setText(str(default_step))
        self._default_speed = float(config_alignment["tip_tilt_control"]["speed"])

        self.ui.bt_moveleft.clicked.connect(self.move_left)
        self.ui.bt_moveup.clicked.connect(self.move_up)
        self.ui.bt_moveright.clicked.connect(self.move_right)
        self.ui.bt_movedown.clicked.connect(self.move_down)
    
    def setup_plane_combobox(self):
        self.ui.cb_plane.addItem(self.IMAGE_PLANE)
        self.ui.cb_plane.addItem(self.PUPIL_PLANE)
    
    def move_left(self):
        steps = np.array([0,-1,0,0]) * self.get_step_size()
        self.move(steps)
    
    def move_up(self):
        steps = np.array([1,0,0,0]) * self.get_step_size()
        self.move(steps)

    def move_right(self):
        steps = np.array([0,1,0,0]) * self.get_step_size()
        self.move(steps)

    def move_down(self):
        steps = np.array([-1,0,0,0]) * self.get_step_size()
        self.move(steps)
    
    def move(self, steps):
        speeds= np.array([1,1,1,1]) * self._default_speed
        beam_ID = self._beam_index
        movement_type = self.get_movement_type()

        self._tt_interface.individual_step(True, movement_type, steps, speeds, beam_ID, False)
    
    def get_movement_type(self):
        cb_item = self.ui.cb_plane.currentText()

        match cb_item:
            case self.IMAGE_PLANE:
                return 1
            case self.PUPIL_PLANE:
                return -1
            case _:
                raise Exception("There is a problem with the tip tilt combobox")
    
    def get_step_size(self):
        text_stepSize = self.ui.le_stepsize.text()
        return float(text_stepSize)
