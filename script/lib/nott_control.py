#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Module with function to control the main NOTT subsystems 

This module contains various NOTT control functions.

Example:

To do:
* 
*

Modification history:
* Version 1.0.0: Denis Defrere (KU Leuven) -- denis.defrere@kuleuven.be

"""
__author__ = "Denis Defrere"
__copyright__ = "Copyright 2024, The SCIFY Project"
__credits__ = ["Kwinten Missiaen","Muhammad Salman","Marc-Antoine Martinod"]
__license__ = "GPL"
__version__ = "1.0.0"
__maintainer__ = "Denis Defrere"
__email__ = "denis.defrere@kuleuven.be"
__status__ = "Production"


import sys
import time
from configparser import ConfigParser
import logging

# Add the path to sys.path
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/')
from opcua import OPCUAConnection
from components.motor import Motor
from components.shutter import Shutter

# Silent messages from opcua every time a command is sent
logger = logging.getLogger("asyncua")
logger.setLevel(logging.WARNING)

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
def move_abs_dl(pos, speed, opcua_motor, pos_offset):
    """ 
    Send an absolute position to a delay line 

    pos_offset: in mm
    """

    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()

    # parent = opcua_conn.client.get_node('ns=4;s=MAIN.DL_Servo_'+dl_id)
    parent = opcua_conn.client.get_node('ns=4;s=MAIN.'+opcua_motor)
    method = parent.get_child("4:RPC_MoveAbs")

    curr_pos = read_current_pos(opcua_motor)

    if pos - curr_pos > 0:
        pos = pos + pos_offset # in mm
    else:
        pos = pos - pos_offset # in mm

    arguments = [pos, speed]
    parent.call_method(method, *arguments)

    #dl = Motor(opcua_conn, 'ns=4;s=MAIN.Delay_Lines.NDL'+dl_id, 'DL_'+dl_id)
    #dl.command_move_absolute(pos, speed)
    
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

# Read current position
def read_current_pos(opcua_motor):
    """ Read current position. Return it in mm """
    
    # Initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()

    # Read positoin
    target_pos = opcua_conn.read_node('ns=4;s=MAIN.'+opcua_motor+'.stat.lrPosActual')
    opcua_conn.disconnect()

    return target_pos


#### SHUTTERS FUNCTIONS ####
############################

# Move rel motor
def shutter_close(shutter_id):
    """ Function to close a shutter """

    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()
    shutter = Shutter(opcua_conn, 'ns=4;s=MAIN.nott_ics.Shutters.NSH'+shutter_id, 'Shutter '+shutter_id)
    shutter.close()

    # Disconnect
    opcua_conn.disconnect()
    return 'done'

def shutter_open(shutter_id):
    """ Function to open a shutter """

    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()
    shutter = Shutter(opcua_conn, 'ns=4;s=MAIN.nott_ics.Shutters.NSH'+shutter_id, 'Shutter '+shutter_id)
    shutter.open()
    
    # Disconnect
    opcua_conn.disconnect()
    return 'done'

def all_shutters_close(n_aper):
    for i in range(n_aper):
        shutter_close(str(i+1))
        
def all_shutters_open(n_aper):
    for i in range(n_aper):
        shutter_open(str(i+1))

# if __name__ == '__main__':
#     opcua_motor = 'nott_ics.Delay_Lines.NDL4'
#     speed = 0.02
#     pos = 6.
#     pos_offset = 0.24 / 1000.
#     rel_pos = 0.5
#     move_abs_dl(pos, speed, opcua_motor, pos_offset)
#     # move_rel_dl(rel_pos, speed, opcua_motor)

    