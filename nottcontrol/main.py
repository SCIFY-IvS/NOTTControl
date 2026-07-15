import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from nottcontrol.app_icon import apply_app_icon, ensure_windows_app_identity
from nottcontrol.ui_scale import configure_high_dpi, init_ui_scale
from nottcontrol.opcua import OPCUAConnection
from nottcontrol.scifygui import MainWindow
import os
import logging
from nottcontrol import config

def main():
    configure_high_dpi()
    ensure_windows_app_identity()

    #Change the running directory to this directory
    #If you run this file from another directory, this is required to find the config file
    os.chdir(os.path.dirname(__file__))

    # initialize the OPC UA connection
    url =  config['DEFAULT']['opcuaaddress']

    logger = logging.getLogger("asyncua")
    logger.setLevel(logging.WARNING)

    opcua_timeout_s = config.getfloat("SENSORS", "opcua_timeout_s", fallback=10.0)
    opcua_conn = OPCUAConnection(url, timeout=opcua_timeout_s)
    opcua_conn.connect()

    # set up the main window
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    init_ui_scale(app)
    apply_app_icon(app)
    main_window = MainWindow(opcua_conn)
    main_window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ("--create-shortcut", "--shortcut"):
        from nottcontrol.windows.create_desktop_shortcut import create_desktop_shortcut

        shortcut = create_desktop_shortcut()
        print(f"Created shortcut: {shortcut}")
        raise SystemExit(0)
    main()
