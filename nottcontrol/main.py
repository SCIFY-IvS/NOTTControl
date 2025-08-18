import sys
from PyQt5.QtWidgets import QApplication
from nottcontrol.opcua import OPCUAConnection
from nottcontrol.scifygui import MainWindow
import os
import logging
from nottcontrol import config

def main():
    #Change the running directory to this directory
    #If you run this file from another directory, this is required to find the config file
    os.chdir(os.path.dirname(__file__))

    # initialize the OPC UA connection
    url =  config['DEFAULT']['opcuaaddress']

    logger = logging.getLogger("asyncua")
    logger.setLevel(logging.WARNING)

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()

    # set up the main window
    app = QApplication(sys.argv)
    main_window = MainWindow(opcua_conn)
    main_window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()


