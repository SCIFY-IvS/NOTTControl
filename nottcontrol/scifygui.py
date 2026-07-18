from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QInputDialog, QMessageBox, QLabel
from PyQt5.QtCore import QTimer, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.uic import loadUi
from pathlib import Path
from nottcontrol.app_icon import install_nott_logo_header, load_app_icon, make_nott_logo_title_header
from nottcontrol.opcua import OPCUAConnection
from nottcontrol.theme import apply_main_window_styles
from asyncua import ua
from datetime import datetime
from nottcontrol.redisclient import RedisClient
from nottcontrol.camera.infratec.scify import MainWindow as camera_ui, camera_status_snapshot
from nottcontrol.components.camera_status_panel import CameraStatusPanel
from nottcontrol import config, sensor_config_path, cryo_status_config_path
from nottcontrol.sensors import (
    load_sensor_config,
    load_temperature_sensors,
    load_pressure_sensors,
    load_cryo_status_config,
    coerce_sensor_value,
    filter_temperature_sensors,
    is_vote_temperature_tag,
)
from nottcontrol.components.cryo_temp_panel import (
    CryoPressurePanel,
    CryoTemperaturePanel,
)
from nottcontrol.ui_scale import cryo_temp_panel_height, scaled
from nottcontrol.components.delay_lines_panel import (
    DelayLinesStatusPanel,
    delay_line_opc_nodes,
)
from nottcontrol.components.tip_tilt_panel import (
    TipTiltStatusPanel,
    tip_tilt_opc_nodes,
)
from nottcontrol.components.shutters_panel import (
    ShuttersStatusPanel,
    shutter_opc_nodes,
)
from nottcontrol.components.motor import Motor
from nottcontrol.components.device_polling import (
    motor_position_opc_nodes,
    motor_status_opc_nodes,
    split_motor_position_values,
    split_motor_status_values,
)
from nottcontrol.shutters_window import ShutterWindow
from nottcontrol.tiptilt_window import TipTiltWindow
from nottcontrol.piezos_window import PiezosWindow
from nottcontrol.cryostat_window import CryostatWindow
from nottcontrol.ldc_window import LdcWindow
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


HEADLINE_TEMP_TAGS = (
    "t_detector_vote",
    "t_base_plate_vote",
    "t_shield_vote",
    "t_photonic_chip_vote",
)

DASHBOARD_GAP = 12
LEFT_PANEL_X = 230
LEFT_PANEL_W = 420
RIGHT_PANEL_X = 660
RIGHT_PANEL_W = 370
DASHBOARD_TOP_Y = 295
TT_PANEL_TOP_Y = 118
DL_PANEL_H = 165
PRESSURE_PANEL_H = 200
TT_PANEL_H = 285
SHUTTER_PANEL_H = 165
TEMP_PANEL_H = 96
CAMERA_PANEL_H = 115
NAV_BUTTONS_TOP_Y = 118


class MainWindow(QMainWindow):
    def __init__(self, opcua_conn):
        super(MainWindow, self).__init__()
        # save the OPC UA connection
        self.opcua_conn = opcua_conn

        self.camera_window = None
        self.h2rg_window = None
        self._h2rg_opening = False
        self.delayline_window = None
        self.shutter_window = None
        self.tiptilt_window = None
        self.piezos_window = None
        self.cryostat_window = None
        self.ldc_window = None

        url =  config['DEFAULT']['databaseurl']
        self.redis_client = RedisClient(url)
        self._redis_warned = False

        # set up the main window
        self.ui = loadUi('main_window.ui', self)
        self.setWindowTitle("NOTT instrument control")
        apply_main_window_styles(self)
        self._load_header_logos()
        self._layout_nav_buttons()

        # print("self.opcua_conn in MainWindow", self.opcua_conn)
        # Show Delay line window
        self.ui.main_pb_delay_lines.clicked.connect(self.open_delay_lines)
        self.ui.pushButton_shutters.clicked.connect(self.open_shutter_window)
        self.ui.pushButton_tiptilt.clicked.connect(self.open_tiptilt_window)
        self.ui.pushButton_piezos.clicked.connect(self.open_piezos_window)
        self.ui.pushButton_cryostat.clicked.connect(self.open_cryostat_window)
        self.ui.pushButton_ldc.clicked.connect(self.open_ldc_window)

        self.ui.pushButton_camera.clicked.connect(self.open_camera_interface)
        self.ui.pushButton_h2rg.clicked.connect(self.open_h2rg_interface)

        self.dl_status_opc_nodes, self.dl_status_keys = delay_line_opc_nodes()
        self.dl_status_panel = DelayLinesStatusPanel(self.ui.centralwidget)
        self.ui.label_dl_status.hide()
        self.ui.label_dl_state.hide()

        self.tt_status_opc_nodes, self.tt_status_keys = tip_tilt_opc_nodes()
        self.tt_status_panel = TipTiltStatusPanel(self.ui.centralwidget)

        self.shutter_status_opc_nodes, self.shutter_status_keys = shutter_opc_nodes()
        self.shutter_status_panel = ShuttersStatusPanel(self.ui.centralwidget)

        self.camera_status_panel = CameraStatusPanel(self.ui.centralwidget)

        self.sensor_opc_nodes, self.sensor_redis_keys = load_sensor_config(sensor_config_path)
        (
            self.temp_opc_nodes,
            _temp_redis_keys,
            self.temp_display_names,
            self.temp_tags,
        ) = load_temperature_sensors(sensor_config_path)
        (
            self.dashboard_temp_opc_nodes,
            _dashboard_temp_redis_keys,
            self.dashboard_temp_display_names,
            self.dashboard_temp_tags,
        ) = filter_temperature_sensors(
            self.temp_opc_nodes,
            _temp_redis_keys,
            self.temp_display_names,
            self.temp_tags,
            tag_filter=is_vote_temperature_tag,
        )
        (
            self.pressure_opc_nodes,
            _pressure_redis_keys,
            self.pressure_display_names,
            self.pressure_tags,
            _pressure_units,
        ) = load_pressure_sensors(sensor_config_path)
        self.cryo_status_items = load_cryo_status_config(cryo_status_config_path)

        opcuaddress_cry = config["DEFAULT"]["opcuaaddress_cry"]
        opcua_timeout_s = config.getfloat("SENSORS", "opcua_timeout_s", fallback=30.0)
        self.opcua_conn_cry = OPCUAConnection(opcuaddress_cry, timeout=opcua_timeout_s)
        self.opcua_conn_cry.connect()

        equipment_items = [(item.key, item.label) for item in self.cryo_status_items]

        self.pressure_panel = CryoPressurePanel(self.ui.centralwidget)
        self.pressure_panel.setup(
            self.pressure_tags,
            self.pressure_display_names,
            equipment_items,
        )

        self.cryo_temp_panel = CryoTemperaturePanel(self.ui.centralwidget)
        self.cryo_temp_panel.setup(
            self.dashboard_temp_tags,
            self.dashboard_temp_display_names,
            compact=True,
        )
        self._layout_dashboard_panels()

        for widget in (
            self.ui.label_light_source,
            self.ui.label_shutters_status,
            self.ui.label_filter_wheel_status,
            self.ui.main_label_temp1,
            self.ui.main_label_temp2,
            self.ui.main_label_temp3,
            self.ui.main_label_temp4,
            self.ui.label_10,
            self.ui.label_11,
            self.ui.label_12,
            self.ui.label_13,
        ):
            widget.hide()

        self.temp1 = self.temp2 = self.temp3 = self.temp4 = None
        self._cryo_cache: dict = {}

        self.ui.label_error.hide()

        self._layout_title()

        # Dl status on main window
        self.load_dl_status()
        self.load_tt_status()
        self.load_shutter_status()
        self.load_camera_status()
        self._poll_cryo_opc()
        self._apply_cryo_cache_to_display()

        self.t = QTimer()
        self.t.timeout.connect(self.refresh_status)
        self.t.start(10000)

        self.t2 = QTimer()
        self.t2.timeout.connect(self.read_and_store_sensor_values)
        sensor_save_interval_ms = config.getint("SENSORS", "sensor_save_interval_ms")
        self.t2.start(sensor_save_interval_ms)

    def _panel_height(self, panel, base_height: int) -> int:
        panel.adjustSize()
        hint = max(panel.sizeHint().height(), panel.minimumSizeHint().height())
        return max(scaled(base_height), hint)

    def _layout_dashboard_panels(self) -> None:
        """Place dashboard status panels in two columns without overlap."""
        gap = scaled(DASHBOARD_GAP)
        left_x = scaled(LEFT_PANEL_X)
        left_w = scaled(LEFT_PANEL_W)
        right_x = scaled(RIGHT_PANEL_X)
        right_w = scaled(RIGHT_PANEL_W)

        y_left = scaled(TT_PANEL_TOP_Y)
        camera_h = self._panel_height(self.camera_status_panel, CAMERA_PANEL_H)
        self.camera_status_panel.setGeometry(left_x, y_left, left_w, camera_h)
        y_left += camera_h + gap

        dl_h = self._panel_height(self.dl_status_panel, DL_PANEL_H)
        self.dl_status_panel.setGeometry(left_x, y_left, left_w, dl_h)
        y_left += dl_h + gap

        tt_h = self._panel_height(self.tt_status_panel, TT_PANEL_H)
        self.tt_status_panel.setGeometry(left_x, y_left, left_w, tt_h)
        left_bottom = y_left + tt_h

        y_right = scaled(TT_PANEL_TOP_Y)
        shutter_h = self._panel_height(self.shutter_status_panel, SHUTTER_PANEL_H)
        self.shutter_status_panel.setGeometry(right_x, y_right, right_w, shutter_h)
        y_right += shutter_h + gap

        temp_base_h = cryo_temp_panel_height(
            len(self.dashboard_temp_tags), columns=2, dense=True
        )
        temp_h = self._panel_height(self.cryo_temp_panel, temp_base_h)
        self.cryo_temp_panel.setGeometry(right_x, y_right, right_w, temp_h)
        y_right += temp_h + gap

        pressure_h = self._panel_height(self.pressure_panel, PRESSURE_PANEL_H)
        self.pressure_panel.setGeometry(right_x, y_right, right_w, pressure_h)
        right_bottom = y_right + pressure_h

        dashboard_bottom = max(left_bottom, right_bottom)
        self.resize(max(self.width(), scaled(1040)), dashboard_bottom + scaled(60))

    def _layout_nav_buttons(self) -> None:
        button_height = 50
        button_gap = 5
        y = scaled(NAV_BUTTONS_TOP_Y)
        nav_buttons = (
            self.ui.pushButton_camera,
            self.ui.pushButton_h2rg,
            self.ui.pushButton_cryostat,
            self.ui.main_pb_delay_lines,
            self.ui.pushButton_filter_wheel,
            self.ui.pushButton_ldc,
            self.ui.pushButton_light_source,
            self.ui.pushButton_piezos,
            self.ui.pushButton_shutters,
            self.ui.pushButton_tiptilt,
        )
        for button in sorted(nav_buttons, key=lambda btn: btn.text().lower()):
            button.setGeometry(20, y, 200, button_height)
            y += button_height + button_gap

    def _set_logo_label(self, label: QLabel, logo_path: Path, width: int, height: int) -> None:
        label.setStyleSheet("background: transparent;")
        label.setAttribute(Qt.WA_TranslucentBackground, True)
        label.setAlignment(Qt.AlignCenter)
        if not logo_path.exists():
            return
        pixmap = QPixmap(str(logo_path))
        if pixmap.isNull():
            return
        label.setPixmap(
            pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        label.setText("")

    def _load_header_logos(self) -> None:
        assets_dir = Path(__file__).resolve().parent

        app_icon = load_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self.ui.label.hide()
        self.ui.label_2.hide()

        self._header_title = make_nott_logo_title_header("Instrument Control")
        self._header_title.setParent(self.ui.centralwidget)

        self._asgard_logo_label = QLabel(self.ui.centralwidget)
        self._set_logo_label(self._asgard_logo_label, assets_dir / "ASGARD.png", 96, 96)
        self._layout_header_title()
        self._layout_asgard_logo()

    def _layout_asgard_logo(self) -> None:
        if not hasattr(self, "_asgard_logo_label"):
            return
        logo_size = 96
        margin = 12
        self._asgard_logo_label.setGeometry(
            max(margin, self.width() - logo_size - margin),
            12,
            logo_size,
            logo_size,
        )

    def _layout_header_title(self) -> None:
        if not hasattr(self, "_header_title"):
            return
        margin_x = 10
        margin_y = 12
        header_height = 56
        self._header_title.setGeometry(
            margin_x,
            margin_y,
            min(480, max(320, self.width() - 140)),
            header_height,
        )
        self._header_title.raise_()

    def _layout_title(self) -> None:
        self._layout_header_title()

    def open_camera_interface(self):
        try:
            if self.camera_window is None:
                self.camera_window = camera_ui()
                self.camera_window.show()
                self.camera_window.closing.connect(self.clear_camera_window)
            else:
                self.camera_window.activateWindow()
            self.load_camera_status()

        except Exception as e:
            print(f"Error opening camera window: {e}")
    
    def clear_camera_window(self):
        self.camera_window = None
        self.load_camera_status()

    def open_h2rg_interface(self):
        if self.h2rg_window is not None:
            self.h2rg_window.activateWindow()
            return
        if self._h2rg_opening:
            return

        self._h2rg_opening = True
        self.ui.pushButton_h2rg.setEnabled(False)
        self.ui.pushButton_h2rg.setText("Opening…")
        QApplication.processEvents()
        QTimer.singleShot(0, self._h2rg_open_step_import)

    def _h2rg_open_step_import(self) -> None:
        QApplication.processEvents()
        try:
            import importlib

            importlib.import_module("nottcontrol.camera.macie.h2rg_gui")
        except Exception as exc:
            self._on_h2rg_open_failed(str(exc))
            return
        QTimer.singleShot(0, self._h2rg_open_step_create)

    def _h2rg_open_step_create(self) -> None:
        QApplication.processEvents()
        try:
            from nottcontrol.camera.macie.h2rg_gui import H2rgMainWindow

            self.h2rg_window = H2rgMainWindow()
            self.h2rg_window.closing.connect(self.clear_h2rg_window)
        except Exception as exc:
            self._on_h2rg_open_failed(str(exc))
        else:
            self._reset_h2rg_open_button()

    def _on_h2rg_open_failed(self, message: str) -> None:
        print(f"Error opening H2RG window: {message}")
        QMessageBox.warning(self, "Camera cold", message)
        self._reset_h2rg_open_button()

    def _reset_h2rg_open_button(self) -> None:
        self._h2rg_opening = False
        self.ui.pushButton_h2rg.setEnabled(True)
        self.ui.pushButton_h2rg.setText("Camera cold")

    def clear_h2rg_window(self):
        self.h2rg_window = None

    def load_camera_status(self):
        try:
            status = camera_status_snapshot(self.camera_window)
            self.camera_status_panel.update_status(
                connected=bool(status.get("connected")),
                recording=bool(status.get("recording")),
                files_today=status.get("files_today"),
                frame_size=str(status.get("frame_size", "—")),
                utc_day=status.get("utc_day"),
            )
        except Exception as e:
            print(f"Camera status: {e}")

    def resizeEvent(self, event):
        self._layout_title()
        self._layout_asgard_logo()
        super().resizeEvent(event)

    def closeEvent(self, *args):
        if self.camera_window is not None:
            self.camera_window.close()
        if self.h2rg_window is not None:
            self.h2rg_window.close()
        self.t.stop()
        self.opcua_conn.disconnect()
        self.t2.stop()
        self.opcua_conn_cry.disconnect()
        super().closeEvent(*args)

    def refresh_status(self):
        try:
            self.load_dl_status()
            self.load_tt_status()
            self.load_shutter_status()
            self.load_camera_status()
            if self._poll_cryo_opc():
                self._apply_cryo_cache_to_display()
        except Exception as e:
            print(e)



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
                self.tiptilt_window = TipTiltWindow(self, self.opcua_conn, self.redis_client)
                self.tiptilt_window.closing.connect(self.clear_tiptilt_window)
                self.tiptilt_window.show()
                print("Tiptilt window is opening fine")
            else:
                self.tiptilt_window.activateWindow()
        except Exception as e:
            print(f"Error opening tiptilt window: {e}")

    def open_piezos_window(self):
        try:
            if self.piezos_window is None:
                self.piezos_window = PiezosWindow(self)
                self.piezos_window.closing.connect(self.clear_piezos_window)
                self.piezos_window.show()
            else:
                self.piezos_window.activateWindow()
        except Exception as e:
            print(f"Error opening piezos window: {e}")

    def _warn_redis_unavailable(self, context: str) -> None:
        if self._redis_warned:
            return
        self._redis_warned = True
        error = self.redis_client.last_error or "connection refused"
        print(
            f"{context}: Redis unavailable at {self.redis_client.url} ({error}). "
            "Live cryo data still works; history logging is disabled until Redis is up."
        )

    def open_cryostat_window(self):
        try:
            if self.cryostat_window is None:
                self.cryostat_window = CryostatWindow(self)
                self.cryostat_window.closing.connect(self.clear_cryostat_window)
                self.cryostat_window.show()
                self._sync_cryostat_window_from_cache()
                if not self.redis_client.is_available(force=True):
                    self._warn_redis_unavailable("Cryostat history")
            else:
                self.cryostat_window.activateWindow()
        except Exception as e:
            print(f"Error opening cryostat window: {e}")
    
    def clear_shutter_window(self):
        self.shutter_window = None
    
    def clear_dl_window(self):
        self.delayline_window = None

    def clear_tiptilt_window(self):
        self.tiptilt_window = None

    def clear_piezos_window(self):
        self.piezos_window = None

    def clear_cryostat_window(self):
        self.cryostat_window = None

    def open_ldc_window(self):
        try:
            if self.ldc_window is None:
                self.ldc_window = LdcWindow(self, self.opcua_conn, self.redis_client)
                self.ldc_window.closing.connect(self.clear_ldc_window)
                self.ldc_window.show()
            else:
                self.ldc_window.activateWindow()
        except Exception as e:
            print(f"Error opening LDC window: {e}")

    def clear_ldc_window(self):
        self.ldc_window = None

    def load_dl_status(self):
        values = self.opcua_conn.read_nodes(self.dl_status_opc_nodes)
        for index, dl_key in enumerate(self.dl_status_keys):
            status = values[index * 3]
            state = values[index * 3 + 1]
            position_mm = coerce_sensor_value(values[index * 3 + 2])
            self.dl_status_panel.update_status(dl_key, status, state, position_mm)

    def load_tt_status(self):
        values = self.opcua_conn.read_nodes(self.tt_status_opc_nodes)
        for index, actuator_id in enumerate(self.tt_status_keys):
            status = values[index * 3]
            state = values[index * 3 + 1]
            position_mm = coerce_sensor_value(values[index * 3 + 2])
            self.tt_status_panel.update_status(
                actuator_id, status, state, position_mm
            )

    def load_shutter_status(self):
        values = self.opcua_conn.read_nodes(self.shutter_status_opc_nodes)
        for index, shutter_key in enumerate(self.shutter_status_keys):
            status = values[index * 3]
            state = values[index * 3 + 1]
            position_mm = coerce_sensor_value(values[index * 3 + 2])
            self.shutter_status_panel.update_status(
                shutter_key, status, state, position_mm
            )
    
    def read_and_store_sensor_values(self):
        try:
            if not self._poll_cryo_opc():
                return
            cache = self._cryo_cache
            saved_at = cache.get("updated_at")
            if saved_at is None:
                return
            if not self.redis_client.is_available():
                self._warn_redis_unavailable("Sensors")
                self._apply_cryo_cache_to_display()
                return
            saved_count, skipped_keys = self.redis_client.save_sensor_values(
                saved_at, self.sensor_redis_keys, cache["sensor_values"]
            )
            self._store_asic_hs_temp(saved_at)
            self._apply_cryo_cache_to_display()
            if skipped_keys:
                print(
                    f"Sensors: saved {saved_count}, skipped {len(skipped_keys)} invalid"
                )
        except Exception as e:
            print(f"Sensors: {e}")
            try:
                self.opcua_conn_cry.reconnect()
            except Exception as reconnect_error:
                print(f"OPC UA cryo reconnect failed: {reconnect_error}")

    def _store_asic_hs_temp(self, saved_at) -> None:
        """Poll SIDECAR on-chip HS_TEMP and write Kelvin to Redis when enabled."""
        if not config.getboolean("MACIE", "asic_temp_to_redis", fallback=True):
            return
        if not self.redis_client.is_available():
            return
        try:
            from nottcontrol.camera.macie.macie_interface import query_asic_hs_temp
            from nottcontrol.camera.macie.zmq_server_manager import (
                is_zmq_port_open,
                select_macie_zmq_address,
            )

            address = select_macie_zmq_address(timeout_s=0.2)
            if not is_zmq_port_open(address, timeout_s=0.2):
                return
            temp_k = query_asic_hs_temp(address, timeout_ms=5_000)
            if temp_k is None:
                return
            key = config.get("MACIE", "asic_temp_redis_key", fallback="asic_hs_temp_k")
            self.redis_client.add_asic_hs_temp(saved_at, temp_k, key=key)
        except Exception as exc:
            # ASIC may be powered off or busy; do not fail the cryo sensor loop.
            if not getattr(self, "_asic_temp_warned", False):
                self._asic_temp_warned = True
                print(f"ASIC HS_TEMP: {exc}")

    def _poll_cryo_opc(self) -> bool:
        if not self.sensor_opc_nodes:
            return False
        try:
            sensor_values = self.opcua_conn_cry.read_nodes(self.sensor_opc_nodes)
            values_by_node = dict(zip(self.sensor_opc_nodes, sensor_values))
            self._cryo_cache = {
                "sensor_values": sensor_values,
                "temp_values": [values_by_node[node] for node in self.temp_opc_nodes],
                "pressure_values": [
                    values_by_node[node] for node in self.pressure_opc_nodes
                ],
                "equipment_status": self._read_cryo_equipment_status(),
                "updated_at": datetime.utcnow(),
            }
            return True
        except Exception as e:
            print(f"Cryo poll failed: {e}")
            try:
                self.opcua_conn_cry.reconnect()
            except Exception as reconnect_error:
                print(f"OPC UA cryo reconnect failed: {reconnect_error}")
            return False

    def get_cryo_cache(self) -> dict:
        return self._cryo_cache

    def _apply_cryo_cache_to_display(self) -> None:
        cache = self._cryo_cache
        if cache.get("updated_at") is None:
            return
        self.update_cryo_display_from_values(
            self.temp_tags,
            cache["temp_values"],
            self.pressure_tags,
            cache["pressure_values"],
            cache["equipment_status"],
            cache["updated_at"],
        )

    def _sync_cryostat_window_from_cache(self) -> None:
        if self.cryostat_window is None:
            return
        cache = self._cryo_cache
        if cache.get("updated_at") is None:
            return
        self.cryostat_window.sync_from_values(
            self.temp_tags,
            cache["temp_values"],
            self.pressure_tags,
            cache["pressure_values"],
            cache["equipment_status"],
            cache["updated_at"],
        )


    def _read_cryo_equipment_status(self) -> dict[str, object]:
        if not self.cryo_status_items:
            return {}
        try:
            opc_ids = [item.opc_id for item in self.cryo_status_items]
            values = self.opcua_conn_cry.read_nodes(opc_ids)
            return {
                item.key: value for item, value in zip(self.cryo_status_items, values)
            }
        except Exception as e:
            print(f"Equipment status read failed: {e}")
            return {item.key: None for item in self.cryo_status_items}

    def update_cryo_display_from_values(
        self,
        temp_tags: list[str],
        temp_values: list,
        pressure_tags: list[str] | None = None,
        pressure_values: list | None = None,
        equipment_status: dict[str, object] | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        temp_tag_values = {
            tag: coerce_sensor_value(value) for tag, value in zip(temp_tags, temp_values)
        }
        pressure_tag_values = None
        if pressure_tags is not None and pressure_values is not None:
            pressure_tag_values = {
                tag: coerce_sensor_value(value)
                for tag, value in zip(pressure_tags, pressure_values)
            }
        self.pressure_panel.update_values(pressure_tag_values, equipment_status)
        self.cryo_temp_panel.update_values(temp_tag_values)
        if self.cryostat_window is not None and pressure_tags is not None and pressure_values is not None:
            self.cryostat_window.sync_from_values(
                temp_tags,
                temp_values,
                pressure_tags,
                pressure_values,
                equipment_status,
                updated_at,
            )

        self.temp1 = temp_tag_values.get(HEADLINE_TEMP_TAGS[0])
        self.temp2 = temp_tag_values.get(HEADLINE_TEMP_TAGS[1])
        self.temp3 = temp_tag_values.get(HEADLINE_TEMP_TAGS[2])
        self.temp4 = temp_tag_values.get(HEADLINE_TEMP_TAGS[3])

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
        install_nott_logo_header(self, title="Delay Lines")
        # Dl statuses
        #self.dl1_status()

        self.ui.motor_widget_1.setup(self.opcua_conn, self.redis_client, self._motor1)
        self.ui.motor_widget_2.setup(self.opcua_conn, self.redis_client, self._motor2)
        self.ui.motor_widget_3.setup(self.opcua_conn, self.redis_client, self._motor3)
        self.ui.motor_widget_4.setup(self.opcua_conn, self.redis_client, self._motor4)

        self._motor_widgets = [
            (self._motor1, self.ui.motor_widget_1),
            (self._motor2, self.ui.motor_widget_2),
            (self._motor3, self.ui.motor_widget_3),
            (self._motor4, self.ui.motor_widget_4),
        ]
        self._motor_prefixes = [motor._prefix for motor, _ in self._motor_widgets]

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
        try:
            values = self.opcua_conn.read_nodes(
                motor_status_opc_nodes(self._motor_prefixes)
            )
            for (_, widget), row in zip(
                self._motor_widgets, split_motor_status_values(values, len(self._motor_widgets))
            ):
                widget.apply_status_values(*row)
        except Exception as e:
            print(e)
            # OPC timeout / read failure: re-enable Absolute/Relative on all DL widgets.
            for _, widget in self._motor_widgets:
                if widget._activeCommand is not None:
                    widget.clearActiveCommand(
                        f"Status refresh failed ({e}); Absolute/Relative re-enabled"
                    )
    
    def load_positions(self):
        try:
            values = self.opcua_conn.read_nodes(
                motor_position_opc_nodes(self._motor_prefixes)
            )
            for (_, widget), row in zip(
                self._motor_widgets,
                split_motor_position_values(values, len(self._motor_widgets)),
            ):
                widget.apply_position_values(*row)
        except Exception as e:
            print(e)