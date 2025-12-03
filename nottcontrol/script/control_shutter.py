#Small example script showing control of the shutter from python

from nottcontrol.components.shutter import Shutter
from nottcontrol.opcua import OPCUAConnection
import time

opc = OPCUAConnection("opc.tcp://10.33.179.151:4840")
opc.connect()

shutter1 = Shutter(opc, "ns=4;s=MAIN.nott_ics.Shutters.NSH1", "NSH1", speed=10, open_pos=-64.0, close_pos=-36.0)

shutter1.getStatusInformation()
shutter1.getPositionAndSpeed()
 
shutter1.open()
time.sleep(5)
shutter1.close()


opc.disconnect()