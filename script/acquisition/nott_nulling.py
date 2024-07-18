#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Module to perform the NOTT beam and fringe acquisition 

This module is the general NOTT acqusition module.

Example:

To do:
* Optimize tip/tilt
* Record data

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
from nott_acquisition import cophase, get_darks, get_flats
from nott_control import move_rel_dl, move_abs_dl, read_current_pos, shutter_close, shutter_open
from nott_database import get_data
from nott_maintenance import startup, shutdown
from nott_fringes import fringes, fringes_env, envelop_detector

# We assume here that the calibration light is turn on
# Running parameters
delay = 1 # Average time

# NOTT startup
startup()

# Record darks
get_darks(delay)

# Record flats
get_flats(delay)

# Optimize tip/tilt
# TO DO

# Cophase (group delay and phase delay)
cophase()

# Take data
# record()

# NOTT shutdown
shutdown()
