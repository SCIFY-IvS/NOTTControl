#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Module to interact with fringe data

This module contains various functions to interact with fringe data

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
from scipy.signal import hilbert

# Fixed parameters. This should go in a config file
# Spectrogon Saphire L narrow
wav = 3.8
bw  = 0.180  
# Spectrogon Saphsire L band
#wav = 3.7
#bw  = 0.6  

def fringes(dl_pos, ampl, g_delay, p_delay):
    return ampl*np.sinc(2*(dl_pos-g_delay)*bw/wav**2)*np.cos(2*np.pi/wav*2*(dl_pos-p_delay))   # See Lawson 2001, Eq 2.7. Factor 2 because delay line postion is twice the OPD

def fringes_env(dl_pos, ampl, g_delay):
    return abs(ampl*np.sinc(2*(dl_pos-g_delay)*bw/wav**2)) # See Lawson 2001, Eq 2.7. Factor 2 because delay line postion is twice the OPD

def enveloppe(dl_pos, flx_coh):
    # Define the bins
    dl_min  = np.min(dl_pos)
    dl_max  = np.max(dl_pos)
    n_bin   = np.floor((dl_max-dl_min)/wav)
    n_bin   = n_bin.astype(int)
    print('ENVELOPE - Number of bins :', n_bin)

    # Extract max per bin
    pos_env = np.array(range(n_bin))
    flx_env = np.array(range(n_bin))
    for i in range(n_bin):
        pos_min    = dl_min + i*wav
        lim_min    = np.argmin(np.abs(dl_pos - pos_min))
        lim_max    = np.argmin(np.abs(dl_pos - (pos_min+wav)))      
        flx_env[i] = np.max(flx_coh[lim_min:lim_max])
        idx_pos    = lim_min + np.argmin(np.abs(flx_coh[lim_min:lim_max] - flx_env[i]))  
        pos_env[i] = dl_pos[idx_pos]
         
    return (pos_env, flx_env)  

def envelop_detector(signal):
    signal -= signal.mean()
    analytic_signal = hilbert(signal)
    flx_env = np.abs(analytic_signal)
    
    return flx_env