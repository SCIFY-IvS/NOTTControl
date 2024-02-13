from components.motor import Motor
from opcua import OPCUAConnection
from commands.scan_fringes_command import ScanFringesCommand

from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.uic import loadUi

from datetime import datetime
import time

class MotorWidget(QWidget):
    closing = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
    
    def setup(self, opcua_conn, redis_client, motor):
        self.opcua_conn = opcua_conn
        self._motor = motor
        self.redis_client = redis_client
        self.timestamp = None

        self.ui = loadUi('motorwidget.ui', self)
        # Dl statuses
        #self.dl1_status()

        self.ui.dl1_pb_homming.clicked.connect(lambda: self.homing())
        self.ui.dl_dl1_pb_scan.clicked.connect(lambda: self.scan_fringes())

        self.ui.dl1_pb_reset.clicked.connect(lambda: self.reset_motor())
        self.ui.dl1_pb_init.clicked.connect(lambda: self.init_motor())
        self.ui.dl1_pb_enable.clicked.connect(lambda: self.enable_motor())
        self.ui.dl1_pb_disable.clicked.connect(lambda: self.disable_motor())
        self.ui.dl1_pb_stop.clicked.connect(lambda: self.stop_motor())
        self.ui.dl1_pb_move_rel.clicked.connect(lambda: self.move_rel_motor())
        self.ui.dl1_pb_move_abs.clicked.connect(lambda: self.move_abs_motor())

        self.ui.label_name.setText(self._motor.name)

        self._activeCommand = None

    def executeCommand(self, cmd):
        cmd.execute()

        if self._activeCommand is not None:
            raise Exception('Already an active command!')
        
        self._activeCommand = cmd
        self.ui.dl_command_status.setText(f'Executing command \'{self._activeCommand.text()}\' ...')

        self.ui.dl1_pb_homming.setEnabled(False)
        self.ui.dl1_pb_move_rel.setEnabled(False)
        self.ui.dl1_pb_move_abs.setEnabled(False)
        self.ui.dl_dl1_pb_scan.setEnabled(False)
    
    def clearActiveCommand(self):
        self._activeCommand = None
        self.ui.dl_command_status.setText('Not executing command')

        self.ui.dl1_pb_homming.setEnabled(True)
        self.ui.dl1_pb_move_rel.setEnabled(True)
        self.ui.dl1_pb_move_abs.setEnabled(True)
        self.ui.dl_dl1_pb_scan.setEnabled(True)

    def refresh_status(self):
        self.dl1_status()
    
    def load_position(self):
        if self.timestamp is not None:
            previous_timestamp = self.timestamp
        else:
            previous_timestamp = None
        
        current_pos, current_speed, timestamp = self._motor.getPositionAndSpeed()

        if (previous_timestamp is not None) and previous_timestamp == timestamp:
            #print('Duplicate timestamp!')
            #print(self.timestamp)
            return
        
        # Convert mm -> micron
        self.current_pos = current_pos * 1000
        self.current_speed = current_speed * 1000
        self.timestamp = timestamp

        timestamp_d = datetime.utcnow()
        # datetime.strptime(self.timestamp, '%Y-%m-%d-%H:%M:%S.%f')  ! Does not record in DB like this (TO BE FIXED)
        self.redis_client.add_dl_position_1(timestamp_d, self.current_pos)


    def dl1_status(self):
        try:
            status, state, substate = self._motor.getStatusInformation()
            self.ui.dl_dl1_status.setText(str(status))
            self.ui.dl_dl1_state.setText(str(state))
            self.ui.dl_dl1_substate.setText(str(substate))
            
            self.ui.dl_dl1_current_position.setText(f'{self.current_pos:.1f}')

            target_pos = self._motor.getTargetPosition()
            target_pos = target_pos * 1000
            self.ui.dl_dl1_target_position.setText(f'{target_pos:.1f}')

            self.ui.dl_dl1_current_speed.setText(f'{self.current_speed:.1f}')

            self.ui.label_error.clear()

            if self._activeCommand is not None and self._activeCommand.check_progress():
                self.clearActiveCommand()

        except Exception as e:
            print(e)
            self.ui.label_error.setText(str(e))

    # Reset motor
    def reset_motor(self):
        try:
            res = self._motor.reset()
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    # Homming
    def homing(self):
        try:
            self.reset_motor()
            time.sleep(5.0)
            self.init_motor()
            time.sleep(10)
            if not self._motor.getInitialized():
                self.ui.dl_command_status.setText("Homing")
            else:
                self.ui.dl_command_status.setText("Home")
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    def scan_fringes_start_pos(self):
        return float(self.ui.lineEdit_scan_from.text()) / 1000
    def scan_fringes_end_pos(self):
        return float(self.ui.lineEdit_scan_to.text()) / 1000
    def scan_fringes_speed(self):
        return 0.1

    # Scan Fringes
    def scan_fringes(self):
        try:
            pos = 10.0  #the required position
            speed = 0.1 # mm/s

            # Homing motor first
            #self.reset_motor()
            #time.sleep(5.0)
            #self.init_motor()
            #time.sleep(10)

            # Triggering camera to START taking images

            #self.trigger_camera_to_take_images(True)

            start_pos = self.scan_fringes_start_pos()
            end_pos = self.scan_fringes_end_pos()
            speed = self.scan_fringes_speed()

            scanFringes = ScanFringesCommand(self._motor, start_pos, end_pos, speed, self.parent.camera_window)
            self.executeCommand(scanFringes)

        except Exception as e:
            print(f"an error happened: {e}")

    # Initialize motor
    def init_motor(self):
        try:
            res = self._motor.init()
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    # Enable motor
    def enable_motor(self):
        try:
            res = self._motor.enable()
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    # Disable motor
    def disable_motor(self):
        try:
            res = self._motor.disable()
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    # Stop motor
    def stop_motor(self):
        try:
            res = self._motor.stop()
        except Exception as e:
            print(f"Error calling RPC method: {e}")


    # Move absolute motor
    def move_abs_motor(self):
        try:
            pos = self.ui.dl1_textEdit_pos.text()
            #Convert to mm
            pos = float(pos) / 1000
            speed = 0.1

            self.__move_abs_motor(pos, speed)
        except Exception as e:
            print(f"Error calling RPC method: {e}")
    

    def __move_abs_motor(self, pos, speed):
        try:
            cmd = self._motor.command_move_absolute(pos, speed)
            self.executeCommand(cmd)
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    # Move rel motor
    def move_rel_motor(self):
        try:
            rel_pos = self.ui.dl1_textEdit_rel_pos.text()
            # Convert to mm
            rel_pos = float(rel_pos) / 1000
            print("rel_pos = ",rel_pos)
            speed = 0.05

            cmd = self._motor.command_move_relative(rel_pos, speed)
            self.executeCommand(cmd)
        except Exception as e:
            print(f"Error calling RPC method: {e}")