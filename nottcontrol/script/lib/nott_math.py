#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic math functions used by the NOTT control code

This module contains various math functions to...

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

# Import functions
import numpy as np

def compute_mean_sampling(vector):
    """ Compute mean sampling frequency of a given (time) vector """
    delta_ts = np.diff(vector)
    mean_delta_ts = np.mean(delta_ts)
    mean_fs = 1 / mean_delta_ts
    return mean_fs