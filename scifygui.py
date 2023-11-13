from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.uic import loadUi
from opcua import OPCUAConnection
from asyncua.sync import Client
import asyncio
from asyncua import ua
import time
from datetime import datetime
from redisclient import RedisClient
from camera.scify import MainWindow as camera_ui
from configparser import ConfigParser
from enum import Enum

# async def call_method_async(opcua_client, node_id, method_name, args):
#     method_node = opcua_client.get_node(node_id)
#     input_args = [ua.Variant(arg, ua.VariantType.Variant) for arg in args]
#     result = await method_node.call_method(method_name, *input_args)
#     return result

async def call_method_async(opcua_conn, node_id, method_name, *args):
    try:
        # get the node and method objects from the server
        node = await opcua_conn.get_node(node_id)
        method = await node.get_child([ua.QualifiedName(4, method_name)])

        # call the method on the server
        result = await method.call(*args)
        return result

    except Exception as e:
        print(f"Error calling RPC method: {e}")


class MainWindow(QMainWindow):
    def __init__(self, opcua_conn):
        super(MainWindow, self).__init__()
        # save the OPC UA connection
        self.opcua_conn = opcua_conn

        self.camera_window = None
        self.delayline_window = None

        config = ConfigParser()
        config.read('config.ini')
        url =  config['DEFAULT']['databaseurl']
        self.redis_client = RedisClient(url)

        # set up the main window
        self.ui = loadUi('main_window.ui', self)

        # print("self.opcua_conn in MainWindow", self.opcua_conn)
        # Show Delay line window
        self.ui.main_pb_delay_lines.clicked.connect(self.open_delay_lines)

        self.ui.pushButton_camera.clicked.connect(self.open_camera_interface)

        # Dl status on main window
        self.load_dl1_status()

        # update the temp values
        self.update_cryo_temps()

        self.t = QTimer()
        self.t.timeout.connect(self.refresh_status)
        self.t.start(10000)
    
    def open_camera_interface(self):
        try:
            if self.camera_window is None:
                self.camera_window = camera_ui()
                self.camera_window.show()
                self.camera_window.closing.connect(self.clear_camera_window)
            else:
                self.camera_window.activateWindow()

        except Exception as e:
            print(f"Error opening camera window: {e}")
    
    def clear_camera_window(self):
        self.camera_window = None

    def closeEvent(self, *args):
        self.t.stop()
        self.opcua_conn.disconnect()
        super().closeEvent(*args)

    def refresh_status(self):
        try:
            self.load_dl1_status()
            self.update_cryo_temps()

            now = datetime.utcnow()
            # fileName = r'C:\Users\fys-lab-ivs\Documents\Python Scripts\Log\Temperatures_' \
            #                 + now.strftime(r'%Y-%m-%d') + '.csv'

            # f = open(fileName, 'a')
            # f.write(f'{str(now)}, {self.temp1}, {self.temp2}, {self.temp3}, {self.temp4} \n')

            self.redis_client.add_temperature_1(now, self.temp1)
            self.redis_client.add_temperature_2(now, self.temp2)
            self.redis_client.add_temperature_3(now, self.temp3)
            self.redis_client.add_temperature_4(now, self.temp4)

            self.ui.label_error.clear()
        except Exception as e:
            print(e)
            self.ui.label_error.setText(str(e))



    def open_delay_lines(self):

        try:
            if self.delayline_window is None:
                self.delayline_window = DelayLinesWindow(self, self.opcua_conn, self.redis_client)
                self.delayline_window.closing.connect(self.clear_dl_window)
                self.delayline_window.show()
                print("Dl window is opening fine")
            else:
                self.delayline_window.activateWindow()
        except Exception as e:
            print(f"Error opening delay lines window: {e}")
    
    def clear_dl_window(self):
        self.delayline_window = None

    def load_dl1_status(self):

        self.ui.label_dl_status.setText(str(self.opcua_conn.read_node("ns=4;s=MAIN.DL_Servo_1.stat.sStatus")))
        self.ui.label_dl_state.setText(str(self.opcua_conn.read_node("ns=4;s=MAIN.DL_Servo_1.stat.sState")))

    def update_cryo_temps(self):
        nodes = ["ns=4;s=GVL_Cryo_Temperatures.Temp_1", 
            "ns=4;s=GVL_Cryo_Temperatures.Temp_2",
            "ns=4;s=GVL_Cryo_Temperatures.Temp_3",
            "ns=4;s=GVL_Cryo_Temperatures.Temp_4" ]

        values = self.opcua_conn.read_nodes(nodes)

        # update the value in the delay lines window
        self.temp1 = str(values[0])
        self.ui.main_label_temp1.setText(self.temp1)

        self.temp2 = str(values[1])
        self.ui.main_label_temp2.setText(self.temp2)

        self.temp3 = str(values[2])
        self.ui.main_label_temp3.setText(self.temp3)

        self.temp4 = str(values[3])
        self.ui.main_label_temp4.setText(self.temp4)

class FringeScanStatus(Enum):
    NOT_SCANNING = 'Not scanning'
    MOVE_TO_START = 'Moving to start position'
    SCANNING = 'Scanning'

class DelayLinesWindow(QWidget):
    closing = pyqtSignal()

    def __init__(self, parent, opcua_conn, redis_client):
        super(DelayLinesWindow, self).__init__()

        self.parent = parent
        self._scan_status = FringeScanStatus.NOT_SCANNING

        config = ConfigParser()
        config.read('config.ini')
        url =  config['DEFAULT']['opcuaaddress']

        # save the OPC UA connection
        self.opcua_conn = OPCUAConnection(url)
        self.opcua_conn.connect()

        self.redis_client = redis_client

        # set up the delay lines window
        self.ui = loadUi('delay_lines.ui', self)
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


        # update the initial value in the window
        self.update_value()

        self.timestamp = None
        self.t_pos = QTimer()
        self.t_pos.timeout.connect(self.load_position)
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

    def refresh_status(self):
        self.dl1_status()
    
    def load_position(self):
        if self.timestamp is not None:
            previous_timestamp = self.timestamp
        else:
            previous_timestamp = None
        
        current_pos, current_speed, timestamp = self.opcua_conn.read_nodes(["ns=4;s=MAIN.DL_Servo_1.stat.lrPosActual", "ns=4;s=MAIN.DL_Servo_1.stat.lrVelActual", "ns=4;s=MAIN.sTime"])

        if (previous_timestamp is not None) and previous_timestamp == timestamp:
            print('Duplicate timestamp!')
            print(self.timestamp)
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
            self.ui.dl_dl1_status.setText(str(self.opcua_conn.read_node("ns=4;s=MAIN.DL_Servo_1.stat.sStatus")))
            self.ui.dl_dl1_state.setText(str(self.opcua_conn.read_node("ns=4;s=MAIN.DL_Servo_1.stat.sState")))

            self.ui.dl_dl1_substate.setText(str(self.timestamp))
            
            self.ui.dl_dl1_current_position.setText(f'{self.current_pos:.1f}')

            target_pos = self.opcua_conn.read_node("ns=4;s=MAIN.DL_Servo_1.ctrl.lrPosition")
            target_pos = target_pos * 1000
            self.ui.dl_dl1_target_position.setText(f'{target_pos:.1f}')

            self.ui.dl_dl1_current_speed.setText(f'{self.current_speed:.1f}')

            self.ui.label_error.clear()

            match self._scan_status:
                case FringeScanStatus.MOVE_TO_START:
                    status = self.ui.dl_dl1_status.text()
                    state = self.ui.dl_dl1_state.text()
                    if(status == 'STANDING' and state == 'OPERATIONAL'):
                        self.parent.camera_window.start_recording()
                        self.t_pos.setInterval(10)
                        self.__move_abs_motor(self.scan_fringes_end_pos(), self.scan_fringes_speed())
                        self._scan_status = FringeScanStatus.SCANNING
                        print ('SCANNING')
                case FringeScanStatus.SCANNING:
                    status = self.ui.dl_dl1_status.text()
                    state = self.ui.dl_dl1_state.text()
                    if(status == 'STANDING' and state == 'OPERATIONAL'):
                        #TODO
                        self._scan_status = FringeScanStatus.NOT_SCANNING
                        self.parent.camera_window.stop_recording()
                        self.t_pos.setInterval(450)
                        print ('SCANNING COMPLETE')

        except Exception as e:
            print(e)
            self.ui.label_error.setText(str(e))
            

    def update_value(self):
        # update the value in the delay lines window
        value = self.opcua_conn.read_node("ns=4;s=GVL_Cryo_Temperatures.Temp_1")
        # self.ui.value_label.setText(str(value))

    def write_to_server(self):
        # write the value to the server
        value = self.ui.value_input.text()
        # self.opcua_conn.write_node("ns=4;s=GVL_Cryo_Temperatures.Temp_1", value)
        # self.update_value()

    # Reset motor
    def reset_motor(self):
        try:
            res = self.opcua_conn.execute_rpc('ns=4;s=MAIN.DL_Servo_1', "4:RPC_Reset", [])
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    # Homming
    def homing(self):
        try:
            self.reset_motor()
            time.sleep(5.0)
            self.init_motor()
            time.sleep(10)
            if not self.opcua_conn.read_node("ns=4;s=MAIN.DL_Servo_1.stat.bInitialised"):
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

            self.__move_abs_motor(self.scan_fringes_start_pos(),self.scan_fringes_speed())
            self._scan_status = FringeScanStatus.MOVE_TO_START

            # Open camera window
            self.parent.open_camera_interface()
            self.parent.camera_window.connect_camera()
            # Connect camera

            # parent = self.opcua_conn.client.get_node('ns=4;s=MAIN.DL_Servo_1')
            # method = parent.get_child("4:RPC_MoveVel")
            # arguments = [speed]
            # res = parent.call_method(method, *arguments)

            # if self.opcua_conn.read_node("ns=4;s=MAIN.DL_Servo_1.stat.lrPosActual") >= pos:
            #     self.ui.dl_dl1_scanning.setText("Scanning Complete")
            #     # Triggering camera to STOP taking images
            #     #self.trigger_camera_to_take_images(False)
            #     self.stop_motor()

            # elif self.opcua_conn.read_node("ns=4;s=MAIN.DL_Servo_1.stat.lrPosActual") <pos:
            #     self.ui.dl_dl1_scanning.setText("Scanning")
        


        except Exception as e:
            print(f"Error calling RPC method: {e}")

    # Initialize motor
    def init_motor(self):
        try:
            res = self.opcua_conn.execute_rpc('ns=4;s=MAIN.DL_Servo_1', "4:RPC_Init", [])
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    # Enable motor
    def enable_motor(self):
        try:
            res = self.opcua_conn.execute_rpc('ns=4;s=MAIN.DL_Servo_1', "4:RPC_Enable", [])
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    # Disable motor
    def disable_motor(self):
        try:
            res = self.opcua_conn.execute_rpc('ns=4;s=MAIN.DL_Servo_1', "4:RPC_Disable", [])
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    # Stop motor
    def stop_motor(self):
        try:
            res = self.opcua_conn.execute_rpc('ns=4;s=MAIN.DL_Servo_1', "4:RPC_Stop", [])
            parent = self.opcua_conn.client.get_node('ns=4;s=MAIN.DL_Servo_1')
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
            res = self.opcua_conn.execute_rpc("ns=4;s=MAIN.DL_Servo_1", "4:RPC_MoveAbs", [pos,speed])
            print("abs_pos = ",res)
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

            res = self.opcua_conn.execute_rpc('ns=4;s=MAIN.DL_Servo_1', "4:RPC_MoveRel", [rel_pos, speed])
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    # Move velocity
    def move_velocity_motor(self, vel):
        try:
            self.opcua_conn.execute_rpc('ns=4;s=MAIN.DL_Servo_1', "4:RPC_MoveVel", [vel])
        except Exception as e:
            print(f"Error calling RPC method: {e}")

    def trigger_camera_to_take_images(self, bTrig):

        # Triggering camera to start taking images
        # CameraOut1_node = self.opcua_conn.read_node("ns = 4;s = GVL_DL_Scanning_Homming.bTrigCameraImages")
        CameraOut1_node_dv = ua.DataValue(ua.Variant(bTrig, ua.VariantType.Boolean))
        # CameraOut1_node.set_value(CameraOut1_node_dv)
        self.opcua_conn.write_node("ns = 4;s = GVL_DL_Scanning_Homming.bTrigCameraImages", CameraOut1_node_dv)


# if __name__=='__main__':
#     app = QApplication(sys.argv)

    # Connect to OPC-UA server
    # url = "opc.tcp://10.33.178.141:4840"
    # client = Client(url)
    # client.connect()
    #
    # # Read a variable
    # var_node = client.get_node("ns=4;s=GVL_Cryo_Temperatures.Temp_1")
    # print("Original value:", var_node.get_value())
    #
    # # Write a new value to the variable
    #
    # # new_value = 10.0
    # # var_node.set_value(60.3)
    # # var_node.set_attribute(client.A
    # # .AttributeIds.Value, ua.DataValue(True))
    # # print("New value:", var_node.get_value())
    #
    # # Disconnect from OPC-UA server
    # client.disconnect()

    # window_1 = Window()
    # window_1.show()
    #
    #
    #
    # try:
    #     sys.exit(app.exec())
    # except:
    #     print("Exiting")
