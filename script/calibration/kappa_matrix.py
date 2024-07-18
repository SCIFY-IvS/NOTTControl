import sys

# Add the path to sys.path
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/lib/')
import redis
import time
from datetime import datetime, timedelta
from nott_control import shutter_close, shutter_open
import numpy as np

# Get epoch
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

    #print( output1)
   
    
    # Return 
    return  output1
   

def get_mean_value(field, start, end):# Get the mean of field during delay seconds
    
    data=get_field(field, start, end)

    mean=sum(data)/len(data)
   
    return(mean)


def remove_background(field,shift,start, end): #remove the backround of field and the shift

    value_i=get_mean_value(field, start, end)
    shift_i=get_mean_value(shift, start,end)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    start = datetime.utcnow() # - timedelta(seconds=0.9) # There is a 0.9 sec delay with redis

    time.sleep(1)

    end = datetime.utcnow() # - timedelta(seconds=0.9) # There is a 0.9 sec delay with redis

    value_f=get_mean_value(field, start,end)
    shift_f=get_mean_value(shift, start,end)

    shutter_open('1')
    shutter_open('2')
    shutter_open('3')
    shutter_open('4')

    return(value_i-shift_i-value_f+shift_f)



delay=1 # define the time to take the measure and to do the mean


P1='roi1_sum' # define all the ROI output
P2='roi2_sum'
I1='roi3_sum'
I2='roi4_sum'
I3='roi5_sum'
I4='roi6_sum'
P3='roi7_sum'
P4='roi8_sum'
Shift='roi9_sum'

shutter_open('1') # Measure the beam 1's outputs
shutter_close('2')
shutter_close('3')
shutter_close('4')

time.sleep(delay)

[start, end]=define_time(delay)

Value_P1=get_mean_value(P1, start,end)
Value_I1=get_mean_value(I1, start,end)
Value_I2=get_mean_value(I2, start,end)
Value_I3=get_mean_value(I3, start,end)
Value_I4=get_mean_value(I4, start,end)
Value_Shift=get_mean_value(Shift, start,end)

shutter_close('1')
shutter_close('2')
shutter_close('3')
shutter_close('4')

time.sleep(delay)
[start, end]=define_time(delay)

P1_clean=Value_P1-Value_Shift-get_mean_value(P1, start,end)+get_mean_value(Shift, start,end)# clean background

P1_coefficients=[Value_I1-Value_Shift-get_mean_value(I1, start,end)+get_mean_value(Shift, start,end),Value_I2-Value_Shift-get_mean_value(I2, start,end)+get_mean_value(Shift, start,end),Value_I3-Value_Shift-get_mean_value(I3, start,end)+get_mean_value(Shift, start,end),Value_I4-Value_Shift-get_mean_value(I4, start,end)+get_mean_value(Shift, start,end) ]/P1_clean

shutter_open('2') # Measure the beam 2's outputs
shutter_close('1')
shutter_close('3')
shutter_close('4')

time.sleep(delay)

[start, end]=define_time(delay)

Value_P2=get_mean_value(P2, start,end)
Value_I1=get_mean_value(I1, start,end)
Value_I2=get_mean_value(I2, start,end)
Value_I3=get_mean_value(I3, start,end)
Value_I4=get_mean_value(I4, start,end)
Value_Shift=get_mean_value(Shift, start,end)

shutter_close('1')
shutter_close('2')
shutter_close('3')
shutter_close('4')


time.sleep(delay)
[start, end]=define_time(delay)

P2_clean=Value_P2-Value_Shift-get_mean_value(P2, start,end)+get_mean_value(Shift, start,end)

P2_coefficients=[Value_I1-Value_Shift-get_mean_value(I1, start,end)+get_mean_value(Shift, start,end),Value_I2-Value_Shift-get_mean_value(I2, start,end)+get_mean_value(Shift, start,end),Value_I3-Value_Shift-get_mean_value(I3, start,end)+get_mean_value(Shift, start,end),Value_I4-Value_Shift-get_mean_value(I4, start,end)+get_mean_value(Shift, start,end) ]/P2_clean


shutter_open('3') # Measure the beam 3's outputs
shutter_close('1')
shutter_close('2')
shutter_close('4')

time.sleep(delay)

[start, end]=define_time(delay)

Value_P3=get_mean_value(P3, start,end)
Value_I1=get_mean_value(I1, start,end)
Value_I2=get_mean_value(I2, start,end)
Value_I3=get_mean_value(I3, start,end)
Value_I4=get_mean_value(I4, start,end)
Value_Shift=get_mean_value(Shift, start,end)

shutter_close('1')
shutter_close('2')
shutter_close('3')
shutter_close('4')

time.sleep(delay)
[start, end]=define_time(delay)

P3_clean=Value_P3-Value_Shift-get_mean_value(P3, start,end)+get_mean_value(Shift, start,end)

P3_coefficients=[Value_I1-Value_Shift-get_mean_value(I1, start,end)+get_mean_value(Shift, start,end),Value_I2-Value_Shift-get_mean_value(I2, start,end)+get_mean_value(Shift, start,end),Value_I3-Value_Shift-get_mean_value(I3, start,end)+get_mean_value(Shift, start,end),Value_I4-Value_Shift-get_mean_value(I4, start,end)+get_mean_value(Shift, start,end) ]/P3_clean


shutter_open('4') # Measure the beam 4's outputs
shutter_close('1')
shutter_close('3')
shutter_close('2')

time.sleep(delay)

[start, end]=define_time(delay)

Value_P4=get_mean_value(P4, start,end)
Value_I1=get_mean_value(I1, start,end)
Value_I2=get_mean_value(I2, start,end)
Value_I3=get_mean_value(I3, start,end)
Value_I4=get_mean_value(I4, start,end)
Value_Shift=get_mean_value(Shift, start,end)

shutter_close('1')
shutter_close('2')
shutter_close('3')
shutter_close('4')

time.sleep(delay)
[start, end]=define_time(delay)

P4_clean=Value_P4-Value_Shift-get_mean_value(P4, start,end)+get_mean_value(Shift, start,end)

P4_coefficients=[Value_I1-Value_Shift-get_mean_value(I1, start,end)+get_mean_value(Shift, start,end),Value_I2-Value_Shift-get_mean_value(I2, start,end)+get_mean_value(Shift, start,end),Value_I3-Value_Shift-get_mean_value(I3, start,end)+get_mean_value(Shift, start,end),Value_I4-Value_Shift-get_mean_value(I4, start,end)+get_mean_value(Shift, start,end) ]/P4_clean


shutter_open('1')
shutter_open('2')
shutter_open('3')
shutter_open('4')


P1_coefficients = np.array(P1_coefficients).reshape(-1, 1)
P2_coefficients = np.array(P2_coefficients).reshape(-1, 1)
P3_coefficients = np.array(P3_coefficients).reshape(-1, 1)
P4_coefficients = np.array(P4_coefficients).reshape(-1, 1)

Kappa_matrice = np.hstack((P1_coefficients, P2_coefficients, P3_coefficients, P4_coefficients))

print(Kappa_matrice)