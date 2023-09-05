import sys
from PyQt5.QtWidgets import QApplication
from opcua import OPCUAConnection
from scifygui import MainWindow

def main():
    # initialize the OPC UA connection
    opcua_conn = OPCUAConnection()
    opcua_conn.connect()

    # set up the main window
    app = QApplication(sys.argv)
    main_window = MainWindow(opcua_conn)
    main_window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()


