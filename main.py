import sys
from PyQt5.QtWidgets import QApplication
from opcua import OPCUAConnection
from configparser import ConfigParser
from scifygui import MainWindow

def main():
    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()

    # set up the main window
    app = QApplication(sys.argv)
    main_window = MainWindow(opcua_conn)
    main_window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()


