#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Basic functions to interact with the NOTT database

This module contains various functions to interact with the database

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
import redis
import numpy as np
from nott_time import unix_time_ms
from datetime import datetime, timedelta
from scipy.interpolate import interp1d
import time
from configparser import ConfigParser

# #  Function to read field values from the REDIS database and corresponding delay line position for the last 'delay' ms
# def get_field(field1, field2, field3, field4, delay, dl_name):
#     """ Read field values and corresponding delay line position """

#     # Define time interval
#     end   = datetime.utcnow() # - timedelta(seconds=0.9) # There is a 0.9 sec delay with redis
#     start = end - timedelta(seconds=delay) 
    
#     # Read data
#     r = redis.from_url('redis://10.33.178.176:6379')

#     # Extract data
#     ts = r.ts()

#      # Get ROI values
#     result1 = ts.range(field1, unix_time_ms(start), unix_time_ms(end))
#     result2 = ts.range(field2, unix_time_ms(start), unix_time_ms(end))
#     result3 = ts.range(field3, unix_time_ms(start), unix_time_ms(end))
#     result4 = ts.range(field4, unix_time_ms(start), unix_time_ms(end))
#     output1 = [(x[1]) for x in result1]
#     output2 = [(x[1]) for x in result2]
#     output3 = [(x[1]) for x in result3]
#     output4 = [(x[1]) for x in result4]
    
#     # Get DL position
#     # temp   = ts.range('dl_pos_1', unix_time_ms(start), unix_time_ms(end))
#     temp   = ts.range(dl_name, unix_time_ms(start), unix_time_ms(end))
#     x_time = [(x[0] / 1000) for x in temp]
#     x_pos0 = [(x[1]) for x in temp]
    
#     # Interpolate DL position on ROIs time stamps
#     vm = np.mean(x_pos0)
#     f = interp1d(x_time, x_pos0, bounds_error=False, fill_value=vm, kind='cubic')
   
#     # Convert to UTC time
#     real_time1 = [(x[0] / 1000) for x in result1]
#     real_time2 = [(x[0] / 1000) for x in result2]
#     real_time3 = [(x[0] / 1000) for x in result3]
#     real_time4 = [(x[0] / 1000) for x in result4]

#     # Re-order
#     #print('Size camera output', len(real_time1))
#     #print('Size DL output', len(x_pos0))

#     # Get DL position at the same time
#     x_pos = f(real_time2)
#     #min_flx = np.min(x_pos)
#     #min_pos = x_pos.argmin(min_flx)
#     #print(len(x_pos))

#     # Compute elasped time
#     real_time1 -= np.min(real_time1)
#     real_time2 -= np.min(real_time2)
#     real_time3 -= np.min(real_time3)
#     real_time4 -= np.min(real_time4)

#     # Return 
#     return x_pos, output1, output2, output3, output4

# #  Function to read field values from the REDIS database
# def get_data(field1, field2, field3, field4, delay):
#     """ Read field values over delay"""

#     # Define time interval
#     end   = datetime.utcnow() # - timedelta(seconds=0.9) # There is a 0.9 sec delay with redis
#     start = end - timedelta(seconds=delay) 
    
#     # Read data
#     r = redis.from_url('redis://10.33.178.176:6379')

#     # Extract data
#     ts = r.ts()

#      # Get ROI values
#     result1 = ts.range(field1, unix_time_ms(start), unix_time_ms(end))
#     result2 = ts.range(field2, unix_time_ms(start), unix_time_ms(end))
#     result3 = ts.range(field3, unix_time_ms(start), unix_time_ms(end))
#     result4 = ts.range(field4, unix_time_ms(start), unix_time_ms(end))
#     output1 = [(x[1]) for x in result1]
#     output2 = [(x[1]) for x in result2]
#     output3 = [(x[1]) for x in result3]
#     output4 = [(x[1]) for x in result4]

#     # Return 
#     return output1, output2, output3, output4

# #  Function to read the ROI max values and delay line position
# def grab_flux(delay, dl_name):
#     """ Function to read the ROI max values and delay line position """
#     data_at_null  = get_field('roi1_max', 'roi2_max', 'roi3_max', 'roi4_max',  delay, dl_name)
#     dl_pos = data_at_null[0]
#     flux2  = data_at_null[2]
#     bck = data_at_null[3]
        
#     # Rearrange
#     idx    = np.argsort(dl_pos)
#     flux2  = np.array(flux2)
#     flux2  = flux2[idx]
#     dl_pos = dl_pos[idx]

#     # Fit fringes
#     flx_coh = flux2.copy()
#     flx_mean = np.mean(flux2)
#     flx_coh = flx_coh - flx_mean

#     return dl_pos, flx_coh, data_at_null[2], bck

def get_field(field, start, end, return_avg, lag=0):
    """
    Get the data in the database of the required `field` in a time range limited by `start` and `end`.
    The returned object is a 2D-array which rows (1st axis) are the datapoints, the first column is the timestamp
    (in milliseconds) and the 2nd column is the value of `field`.

    Parameters
    ----------
    field : str
        Field of the database to colect.
    start : int
        start timestamp in milliseconds. The timezone must be the one of the server.
    end : int
        end timestamp in milliseconds. The timezone must be the one of the server.
    return_avg: bool
        Return the average value on the number of points.
    lag: float
        Lag to add to the timeline, in millisecond. The default is 0.

    Returns
    -------
    output : 2d-array
        Output of the required field from the database.

    """
    
    # REDIS database url (read from config.ini)
    configpars = ConfigParser()
    configpars.read('../../config.ini')
    db_address =  configpars['DEFAULT']['databaseurl']  
    
    # Read data
    r = redis.from_url(db_address)

    # Extract data
    ts = r.ts()

     # Get ROI values
    output = ts.range(field, start, end) # This function returns a list of tuples
    output = np.array(output) # Array
    output[:,0] = output[:,0] + lag

    if return_avg:
        output = output.mean(0) # Average along the number of points axis

    return  output

def define_time(delay):
    """
    Return the rounded timestamps of the start and end of period to grab from the database, in milliseconds.
    The `end` is the timestamp at which this function is called.
    The `start` is `delay` seconds before.
    The timestamps must be in the same timezone as the database.

    Parameters
    ----------
    delay: float
        Length of the timeserie to grab, in seconds.

    Returns
    -------
    start: int
        Rounded timestamp of the beginning of the timeserie to grab, in milliseconds
    end: int
        Rounded timestamp of the end of the timeserie to grab, in milliseconds
    """
    end = time.time()
    start = end - delay

    end = round(end * 1000)
    start = round(start * 1000)

    return start, end