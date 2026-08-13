from __future__ import annotations

from datetime import datetime, timezone
import time

from PyQt5.QtWidgets import QWidget, QMenu
from PyQt5.QtCore import pyqtSignal
from PyQt5.uic import loadUi

from nottcontrol.commands.async_command import is_axis_move_finished
from nottcontrol.commands.scan_fringes_command import ScanFringesCommand
from nottcontrol.theme import style_motor_widget

class MotorWidget(QWidget):
    closing = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
    
    def setup(self, opcua_conn, redis_client, motor):
        self.opcua_conn = opcua_conn
        self._motor = motor
        self.redis_client = redis_client
        self.timestamp = None
        self.current_pos = 0.0
        self.current_speed = 0.0

        self.ui = loadUi('motorwidget.ui', self)
        style_motor_widget(self)

        self.engineering_menu = QMenu()
        reset = self.engineering_menu.addAction("Reset")
        reset.triggered.connect(self.reset_motor)
        init = self.engineering_menu.addAction("Init")
        init.triggered.connect(self.init_motor)
        enable = self.engineering_menu.addAction("Enable")
        enable.triggered.connect(self.enable_motor)
        disable = self.engineering_menu.addAction("Disable")
        disable.triggered.connect(self.disable_motor)
        stop = self.engineering_menu.addAction("Stop")
        stop.triggered.connect(self.stop_motor)

        self.ui.pb_engineering_menu.clicked.connect(self.expand_engineering_menu)

        self.ui.pb_moverel_pos.clicked.connect(self.move_rel_motor_pos)
        self.ui.pb_moverel_neg.clicked.connect(self.move_rel_motor_neg)
        self.ui.pb_move_abs.clicked.connect(self.move_abs_motor)

        self.ui.label_name.setText(self._motor.name)

        self._activeCommand = None
        self.load_position()
    
    def expand_engineering_menu(self):
        localPos = self.ui.pb_engineering_menu.pos()
        globalPos = self.ui.pb_engineering_menu.mapToGlobal(localPos)

        self.engineering_menu.exec(globalPos)

    def executeCommand(self, cmd):
        if self._activeCommand is not None:
            # If a previous move ended in timeout/error (or OPC is unavailable),
            # allow a new move instead of leaving Absolute/Relative stuck disabled.
            try:
                previous_done = self._activeCommand.check_progress()
            except Exception:
                previous_done = True
            if not previous_done:
                raise Exception('Already an active command!')
            self.clearActiveCommand()

        cmd.execute()
        self._activeCommand = cmd
        self.ui.dl_command_status.setText(f'Executing command \'{self._activeCommand.text()}\' ...')

        self.ui.pb_move_rel.setEnabled(False)
        self.ui.pb_move_abs.setEnabled(False)
    
    def clearActiveCommand(self, status_text: str | None = None):
        self._activeCommand = None
        self.ui.dl_command_status.setText(status_text or 'Not executing command')

        self.ui.pb_move_rel.setEnabled(True)
        self.ui.pb_move_abs.setEnabled(True)

    def refresh_status(self):
        try:
            status, state, substate = self._motor.getStatusInformation()
            target_pos = self._motor.getTargetPosition()
            self.apply_status_values(status, state, substate, target_pos)
        except Exception as e:
            print(e)
            self.ui.label_error.setText(str(e))
            # OPC/read timeout while a move is pending: re-enable Absolute/Relative.
            if self._activeCommand is not None:
                self.clearActiveCommand(
                    f"Command interrupted ({e}); Absolute/Relative re-enabled"
                )

    def apply_status_values(self, status, state, substate, target_pos_mm):
        try:
            self.ui.label_status.setText(str(status))
            self.ui.label_state.setText(str(state))
            self.ui.label_substate.setText(str(substate))
            self.ui.label_current_position.setText(f'{self.current_pos:.1f}')
            self.ui.label_target_position.setText(f'{target_pos_mm * 1000:.1f}')
            self.ui.label_current_speed.setText(f'{self.current_speed:.1f}')
            self.ui.label_error.clear()

            if self._activeCommand is not None and is_axis_move_finished(status, state):
                # Prefer values already read for this refresh (avoids an extra OPC call
                # and keeps UI responsive after timeout/error states).
                status_u = str(status or "").upper()
                state_u = str(state or "").upper()
                failed = any(
                    token in status_u or token in state_u
                    for token in ("ERR", "FAULT", "TIMEOUT", "TIME OUT", "TIME-OUT")
                )
                cmd_name = self._activeCommand.text()
                if failed:
                    self.clearActiveCommand(
                        f"Command '{cmd_name}' ended "
                        f"({status} / {state}); Absolute/Relative re-enabled"
                    )
                else:
                    self.clearActiveCommand()
        except Exception as e:
            print(e)
            self.ui.label_error.setText(str(e))
            if self._activeCommand is not None:
                self.clearActiveCommand(
                    f"Command interrupted ({e}); Absolute/Relative re-enabled"
                )
    
    def load_position(self):
        try:
            current_pos, current_speed, timestamp = self._motor.getPositionAndSpeed()
            self.apply_position_values(current_pos, current_speed, timestamp)
        except Exception as e:
            print(e)
            self.ui.label_error.setText(str(e))

    def apply_position_values(self, current_pos_mm, current_speed_mm_s, timestamp):
        try:
            self.current_pos = current_pos_mm * 1000
            self.current_speed = current_speed_mm_s * 1000

            now = datetime.utcnow()
            if (
                self.timestamp is None
                or (now - self.timestamp).total_seconds() >= 1.0
                or abs(self.current_pos - getattr(self, "_last_redis_pos", self.current_pos)) >= 0.1
            ):
                self.redis_client.add_dl_position(self._motor.name, now, self.current_pos)
                self._last_redis_pos = self.current_pos
                self.timestamp = now
        except Exception as e:
            print(e)
            self.ui.label_error.setText(str(e))

    # Reset motor
    def reset_motor(self):
        try:
            res = self._motor.reset()
            self.clearActiveCommand()
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
            pos = self.ui.lineEdit_pos.text()
            #Convert to mm
            pos = float(pos) / 1000

            self.__move_abs_motor(pos)
        except Exception as e:
            print(f"Error calling RPC method: {e}")
    

    def __move_abs_motor(self, pos):
        try:
            cmd = self._motor.command_move_absolute(pos)
            self.executeCommand(cmd)
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    # Move rel motor
    def move_rel_motor(self, rel_pos):
        try:
            print("rel_pos = ",rel_pos)

            cmd = self._motor.command_move_relative(rel_pos)
            self.executeCommand(cmd)
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    def move_rel_motor_pos(self):
        rel_pos = self.ui.lineEdit_relpos.text()
        # Convert to mm
        rel_pos = float(rel_pos) / 1000
        self.move_rel_motor(rel_pos)

    def move_rel_motor_neg(self):
        rel_pos = self.ui.lineEdit_relpos.text()
        # Convert to mm
        rel_pos = float(rel_pos) / 1000
        self.move_rel_motor(-rel_pos)

