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
import time
import numpy as np

from nottcontrol.script.lib.nott_control import shutter_close, shutter_open
from nottcontrol.script.lib.nott_database import get_data

# Function to cophase the instrument
def cophase(delay):
    # Find fringes on the first nuller
    find_fringes('2')

    # Find fringes on the second nuller
    find_fringes('3')
    
    # Find fringe on the cross combiner

    return avg

# Function to get darks
def get_darks(delay):
    # Close all shutters and take dark measurements
    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    # Start recording, get data, and average
    time.sleep(delay)
    darks = get_data('roi1_max', 'roi2_max', 'roi3_max', 'roi4_max',  delay)  # Return a list

    # Save to file

    # Compute average
    avg = np.mean(darks[0], axis=0), np.mean(darks[1], axis=0), np.mean(darks[2], axis=0), np.mean(darks[3], axis=0)
    print('Average dark values for the 4 ROIs:', round(avg[0], 2), round(avg[1], 2), round(avg[2], 2), round(avg[3], 2))

    # Open all shutters and take flux measurements
    shutter_open('1')
    shutter_open('2')
    shutter_open('3')
    shutter_open('4')    

    return avg

# Function to get flats
def get_flats(delay):
    # Open all shutters and take flux measurements
    shutter_open('1')
    shutter_open('2')
    shutter_open('3')
    shutter_open('4')

    # Start recording, get data, and average
    time.sleep(delay)
    flats = get_data('roi1_max', 'roi2_max', 'roi3_max', 'roi4_max',  delay)

    # Save to file

    # Compute average
    avg = np.mean(flats[0], axis=0), np.mean(flats[1], axis=0), np.mean(flats[2], axis=0), np.mean(flats[3], axis=0)
    print('Average flat values for the 4 ROIs:', round(avg[0], 2), round(avg[1], 2), round(avg[2], 2), round(avg[3], 2))

    return avg

