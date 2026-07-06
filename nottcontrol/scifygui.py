from PyQt5.QtWidgets import QMainWindow, QWidget, QInputDialog, QMessageBox
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.uic import loadUi
from nottcontrol.opcua import OPCUAConnection
from asyncua import ua
from datetime import datetime
from nottcontrol.redisclient import RedisClient
from nottcontrol.camera.infratec.scify import MainWindow as camera_ui
from nottcontrol import config, sensor_config_path
from nottcontrol.sensors import load_sensor_config, coerce_sensor_value
from nottcontrol.components.motor import Motor
from nottcontrol.shutters_window import ShutterWindow
from nottcontrol.tiptilt_window import TipTiltWindow
from nottcontrol.tip_tilt_control import TipTiltControl
import json

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
        self.shutter_window = None
        self.tiptilt_window = None

        url =  config['DEFAULT']['databaseurl']
        self.redis_client = RedisClient(url)

        # set up the main window
        self.ui = loadUi('main_window.ui', self)

        # print("self.opcua_conn in MainWindow", self.opcua_conn)
        # Show Delay line window
        self.ui.main_pb_delay_lines.clicked.connect(self.open_delay_lines)
        self.ui.pushButton_shutters.clicked.connect(self.open_shutter_window)
        self.ui.pushButton_tiptilt.clicked.connect(self.open_tiptilt_window)

        self.ui.pushButton_camera.clicked.connect(self.open_camera_interface)

        self.dl_temp_opc_nodes = [
            node.strip()
            for node in config["SENSORS"]["dl_temp_opc_nodes"].split(",")
            if node.strip()
        ]

        # Dl status on main window
        self.load_dl1_status()

        # update the temp values
        self.update_cryo_temps()

        self.t = QTimer()
        self.t.timeout.connect(self.refresh_status)
        self.t.start(10000)

        self.sensor_opc_nodes, self.sensor_redis_keys = load_sensor_config(sensor_config_path)

        opcuaddress_cry =  config['DEFAULT']['opcuaaddress_cry']
        opcua_timeout_s = config.getfloat("SENSORS", "opcua_timeout_s", fallback=30.0)

        self.opcua_conn_cry = OPCUAConnection(opcuaddress_cry, timeout=opcua_timeout_s)
        self.opcua_conn_cry.connect() 

        self.t2 = QTimer()
        self.t2.timeout.connect(self.read_and_store_sensor_values)
        sensor_save_interval_ms = config.getint("SENSORS", "sensor_save_interval_ms")
        self.t2.start(sensor_save_interval_ms)

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
        self.t2.stop()
        self.opcua_conn_cry.disconnect()
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

            if not self.ui.label_error.text().startswith("Sensors:"):
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

    def open_shutter_window(self):
        try:
            if self.shutter_window is None:
                self.shutter_window = ShutterWindow(self, self.opcua_conn, self.redis_client)
                self.shutter_window.closing.connect(self.clear_shutter_window)
                self.shutter_window.show()
                print("Shutter window is opening fine")
            else:
                self.shutter_window.activateWindow()
        except Exception as e:
            print(f"Error opening shutter window: {e}")

    def open_tiptilt_window(self):
        try:
            if self.tiptilt_window is None:
                self.tiptilt_window = TipTiltControl(self, self.opcua_conn, self.redis_client)
                self.tiptilt_window.closing.connect(self.clear_tiptilt_window)
                self.tiptilt_window.show()
                print("Tiptilt window is opening fine")
            else:
                self.tiptilt_window.activateWindow()
        except Exception as e:
            print(f"Error opening tiptilt window: {e}")
    
    def clear_shutter_window(self):
        self.shutter_window = None
    
    def clear_dl_window(self):
        self.delayline_window = None

    def clear_tiptilt_window(self):
        self.tiptilt_window = None

    def load_dl1_status(self):
        status, state = self.opcua_conn.read_nodes([
            "ns=4;s=MAIN.nott_ics.Delay_Lines.NDL1.stat.sStatus",
            "ns=4;s=MAIN.nott_ics.Delay_Lines.NDL1.stat.sState",
        ])
        self.ui.label_dl_status.setText(str(status))
        self.ui.label_dl_state.setText(str(state))
    
    def read_and_store_sensor_values(self):
        try:
            sensor_values = self.opcua_conn_cry.read_nodes(self.sensor_opc_nodes)
            now = datetime.utcnow()
            saved_count, skipped_keys = self.redis_client.save_sensor_values(
                now, self.sensor_redis_keys, sensor_values
            )
            if skipped_keys:
                self.ui.label_error.setText(
                    f"Sensors: saved {saved_count}, skipped {len(skipped_keys)} invalid"
                )
        except Exception as e:
            print(f"Sensor read/save failed: {e}")
            self.ui.label_error.setText(f"Sensors: {e}")
            try:
                self.opcua_conn_cry.reconnect()
            except Exception as reconnect_error:
                print(f"OPC UA cryo reconnect failed: {reconnect_error}")


    def update_cryo_temps(self):
        if not self.dl_temp_opc_nodes:
            return

        values = self.opcua_conn.read_nodes(self.dl_temp_opc_nodes)

        self.temp1 = coerce_sensor_value(values[0])
        self.ui.main_label_temp1.setText("" if self.temp1 is None else f"{self.temp1:.2f}")

        self.temp2 = coerce_sensor_value(values[1])
        self.ui.main_label_temp2.setText("" if self.temp2 is None else f"{self.temp2:.2f}")

        self.temp3 = coerce_sensor_value(values[2])
        self.ui.main_label_temp3.setText("" if self.temp3 is None else f"{self.temp3:.2f}")

        self.temp4 = coerce_sensor_value(values[3])
        self.ui.main_label_temp4.setText("" if self.temp4 is None else f"{self.temp4:.2f}")

class DelayLinesWindow(QMainWindow):
    closing = pyqtSignal()

    def __init__(self, parent, opcua_conn, redis_client):
        super(DelayLinesWindow, self).__init__()

        self.parent = parent

        self.opcua_conn = opcua_conn

        default_speed = config.getint('DL', 'default_speed')

        self._motor1 = Motor(self.opcua_conn, "ns=4;s=MAIN.nott_ics.Delay_Lines.NDL1", 'DL_1', default_speed)
        self._motor2 = Motor(self.opcua_conn, "ns=4;s=MAIN.nott_ics.Delay_Lines.NDL2", 'DL_2', default_speed)
        self._motor3 = Motor(self.opcua_conn, "ns=4;s=MAIN.nott_ics.Delay_Lines.NDL3", 'DL_3', default_speed)
        self._motor4 = Motor(self.opcua_conn, "ns=4;s=MAIN.nott_ics.Delay_Lines.NDL4", 'DL_4', default_speed)

        self.redis_client = redis_client

        # set up the delay lines window
        self.ui = loadUi('delay_lines.ui', self)
        # Dl statuses
        #self.dl1_status()

        self.ui.motor_widget_1.setup(self.opcua_conn, self.redis_client, self._motor1)
        self.ui.motor_widget_2.setup(self.opcua_conn, self.redis_client, self._motor2)
        self.ui.motor_widget_3.setup(self.opcua_conn, self.redis_client, self._motor3)
        self.ui.motor_widget_4.setup(self.opcua_conn, self.redis_client, self._motor4)

        self._activeCommand = None

        self.ui.actionSave_Current_Positions.triggered.connect(self.save_dl_positions)
        self.ui.actionRecall_Positions.triggered.connect(self.recall_dl_positions)
        
        self.saved_configurations = self.redis_client.load_DL_pos()

        self.timestamp = None
        position_save_interval_ms = config.getint(
            "SENSORS", "position_save_interval_ms", fallback=1000
        )
        self.t_pos = QTimer()
        self.t_pos.timeout.connect(self.load_positions)
        self.t_pos.start(position_save_interval_ms)

        self.t = QTimer()
        self.t.timeout.connect(self.refresh_status)
        self.t.start(500)

    def closeEvent(self, *args):
        self.t.stop()
        self.t_pos.stop()
        self.closing.emit()
        super().closeEvent(*args)

    def save_dl_positions(self):
        pos1 = self._motor1.getPositionAndSpeed()[0]
        pos2 = self._motor2.getPositionAndSpeed()[0]
        pos3 = self._motor3.getPositionAndSpeed()[0]
        pos4 = self._motor4.getPositionAndSpeed()[0]

        name, dlgResult = QInputDialog.getText(self, "Please provide a name for the DL configuration", "Name")
        if dlgResult:
            print(name)
        else:
            print("cancel")
            return

        self.saved_configurations[name] = [pos1, pos2, pos3, pos4]

        self.redis_client.save_DL_pos(self.saved_configurations)
    
    def recall_dl_positions(self):
        print('Recall DL positions')

        name, dlgResult = QInputDialog.getText(self, "Please provide the name of the saved configuration", "Name")
        if dlgResult:
            print(name)
        else:
            print("cancel")
            return
        
        if not name in self.saved_configurations:
            print("Configuration not found!")
            msgBox = QMessageBox(self)
            msgBox.setText("Configuration not found!")
            msgBox.exec()
            return
        
        configuration = self.saved_configurations[name]
        print(f'Loading DL positions: pos1: {configuration[0]}; pos2: {configuration[1]}; pos3: {configuration[2]}; pos4; {configuration[3]}')

        self._motor1.command_move_absolute(configuration[0]).execute()
        self._motor2.command_move_absolute(configuration[1]).execute()
        self._motor3.command_move_absolute(configuration[2]).execute()
        self._motor4.command_move_absolute(configuration[3]).execute()

    
    def startCameraRecording(self):
        self.parent.camera_window.start_recording()
    
    def stopCameraRecording(self):
        self.parent.camera_window.stop_recording()

    def refresh_status(self):
        self.ui.motor_widget_1.refresh_status()
        self.ui.motor_widget_2.refresh_status()
        self.ui.motor_widget_3.refresh_status()
        self.ui.motor_widget_4.refresh_status()
    
    def load_positions(self):
        self.ui.motor_widget_1.load_position()
        self.ui.motor_widget_2.load_position()
        self.ui.motor_widget_3.load_position()
        self.ui.motor_widget_4.load_position()