""" Module with function to control the main NOTT subsystems """

import time
from configparser import ConfigParser
from opcua import OPCUAConnection

#### DELAY LINES FUNCTIONS ####
###############################

# Move rel motor
def move_rel_dl(rel_pos, speed, opcua_motor):
    """ Send a relative motion to a delay line """

    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()
    
    # parent = opcua_conn.client.get_node('ns=4;s=MAIN.DL_Servo_1')
    parent = opcua_conn.client.get_node('ns=4;s=MAIN.'+opcua_motor)
    method = parent.get_child("4:RPC_MoveRel")
    arguments = [rel_pos, speed]
    parent.call_method(method, *arguments)
    
    # Wait for the DL to be ready
    on_destination = False
    while not on_destination:
        time.sleep(0.01)
        # status, state = opcua_conn.read_nodes(['ns=4;s=MAIN.DL_Servo_1.stat.sStatus', 'ns=4;s=MAIN.DL_Servo_1.stat.sState'])
        status, state = opcua_conn.read_nodes(['ns=4;s=MAIN.'+opcua_motor+'.stat.sStatus', 'ns=4;s=MAIN.'+opcua_motor+'.stat.sState'])

        on_destination = status == 'STANDING' and state == 'OPERATIONAL'

    # Disconnect
    opcua_conn.disconnect()
    return 'done'

# Move abs motor
def move_abs_dl(pos, speed, opcua_motor):
    """ Send an absolute position to a delay line """

    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()
    
    # parent = opcua_conn.client.get_node('ns=4;s=MAIN.DL_Servo_'+dl_id)
    parent = opcua_conn.client.get_node('ns=4;s=MAIN.'+opcua_motor)
    method = parent.get_child("4:RPC_MoveAbs")
    arguments = [pos, speed]
    parent.call_method(method, *arguments)
    
    # Wait for the DL to be ready
    on_destination = False
    while not on_destination:
        time.sleep(0.01)
        # status, state = opcua_conn.read_nodes(["ns=4;s=MAIN.DL_Servo_1.stat.sStatus", "ns=4;s=MAIN.DL_Servo_1.stat.sState"])
        status, state = opcua_conn.read_nodes(['ns=4;s=MAIN.'+opcua_motor+'.stat.sStatus', 'ns=4;s=MAIN.'+opcua_motor+'.stat.sState'])

        on_destination = status == 'STANDING' and state == 'OPERATIONAL'

    # Disconnect
    opcua_conn.disconnect()      
    return 'done'

# Move abs motor
def read_current_pos(opcua_motor):
    """ Read current position """
    
    # Initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()

    # Read positoin
    target_pos = opcua_conn.read_node('ns=4;s=MAIN.'+opcua_motor+'.stat.lrPosActual')
    target_pos = target_pos * 1000
    opcua_conn.disconnect()

    return target_pos


#### SHUTTERS FUNCTIONS ####
############################

# Move rel motor
def shutter_close(opcua_motor):
    """ Close shutter """

    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()

    shutter = opcua_conn.client.get_node("ns=4;s=MAIN.nott_ics.Shutters.NSH1")
    #shutter.close()

    #the following commands are available:
    #shutter.reset()
    #shutter.init()
    #shutter.enable()
    #shutter.disable()
    #shutter.stop()
    #shutter.open()
    #shutter.close()
    
    # Disconnect
    opcua_conn.disconnect()
    return 'done'