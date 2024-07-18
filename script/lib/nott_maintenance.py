#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Module with various startup and shutdown functions for NOTT

This module contains various startup and shutdown functions for NOTT

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
from configparser import ConfigParser

# Add the path to sys.path
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/')
from nott_control import shutter_close, shutter_open

#### DELAY LINES FUNCTIONS ####
###############################

# Move rel motor
def startup():
    """ Open all shutters """
    
    # Close all shutters 
    shutter_open('1')
    shutter_open('2')
    shutter_open('3')
    shutter_open('4')

# Move rel motor
def shutdown():
    """ Turn off shutters """
    
    # Close all shutters 
    shutter_close('1')
    shutter_close('2')
     
     
    shutter_close('3')
    shutter_close('4')