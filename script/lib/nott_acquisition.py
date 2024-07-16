#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Module with various acquisitoin functions

This module contains various NOTT data acquisitoin functions.

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

# Import libraries
import sys

# Add the path to sys.path
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/lib/')
from nott_control import shutter_close, shutter_open

# Function to get darks
def get_darks(delay):
    # Close all shutters and take dark measurements
    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    # Start recording, get data, and average
    darks = get_data('roi1_max', 'roi2_max', 'roi3_max', 'roi4_max',  delay)

    # Open all shutters and take flux measurements
    shutter_open('1')
    shutter_open('2')
    shutter_open('3')
    shutter_open('4')