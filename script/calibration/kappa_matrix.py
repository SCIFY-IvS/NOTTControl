import sys
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/')
import redis
import time
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit
from datetime import datetime
from datetime import date
from datetime import timedelta
from opcua import OPCUAConnection
from configparser import ConfigParser
import os
import pickle
from scipy.signal import hilbert

epoch = datetime.utcfromtimestamp(0)

def unix_time_ms(time):
    return round((time - epoch).total_seconds() * 1000.0)


def define_time(delay):# Define time interval

        
    end   = datetime.utcnow() # - timedelta(seconds=0.9) # There is a 0.9 sec delay with redis
    start = end - timedelta(seconds=delay) 

    return(start,end)


def get_field(field1, start, end ):
    
    
    # Read data
    r = redis.from_url('redis://10.33.178.176:6379')

    # Extract data
    ts = r.ts()

     # Get ROI values
    result1 = ts.range(field1, unix_time_ms(start), unix_time_ms(end))

    output1 = [(x[1]) for x in result1]

    print( output1)
   
    
    # Return 
    return  output1
   

def get_mean_value(field, start, end):# Get the mean of field during delay seconds
    
    data=get_field(field, start, end)

    mean=sum(data)/len(data)
   
    return(mean)


def remove_backround(field,shift,start, end): #remove the backround of field and the shift

    #test=get_mean_value(field, start, end)
    value_i=get_mean_value(field, start, end)
    shift_i=get_mean_value(shift, start,end)

    #use shutters 

    value_f=get_mean_value(field, start,end)
    shift_f=get_mean_value(shift, start,end)

    value_f=get_mean_value(field, start,end)
    shift_f=get_mean_value(shift, start,end)

    value_f=get_mean_value(field, start,end)
    shift_f=get_mean_value(shift, start,end)

    return(value_i-shift_i-value_f+shift_f)


delay=1

start=define_time(delay)[0]
end=define_time(delay)[1]


print('background',remove_backround('roi1_sum','roi1_sum',start, end))