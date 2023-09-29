import redis
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy.interpolate import interp1d
from datetime import datetime
from datetime import date
from datetime import timedelta
from opcua import OPCUAConnection
from configparser import ConfigParser

epoch = datetime.utcfromtimestamp(0)

# Script parameters
delay = 20.0 # s, window to consider when scanning the fringes

# Function definitions
def unix_time_ms(time):
    return round((time - epoch).total_seconds() * 1000.0)

def real_time(unix_time):
    return datetime.utcfromtimestamp(unix_time / 1000)

def compute_mean_sampling(time_vector):
    delta_ts = np.diff(time_vector)
    mean_delta_ts = np.mean(delta_ts)
    mean_fs = 1 / mean_delta_ts
    return mean_fs

def fringes(wav):
    fringes = wav
    return fringes

# Move rel motor
def move_rel_dl(rel_pos, speed):
    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()
    
    parent = opcua_conn.client.get_node('ns=4;s=MAIN.DL_Servo_1')
    method = parent.get_child("4:RPC_MoveRel")
    arguments = [rel_pos, speed]
    res = parent.call_method(method, *arguments)
    opcua_conn.disconnect()

    return 'done'

# Move rel motor
def move_abs_dl(pos, speed):
    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()
    
    parent = opcua_conn.client.get_node('ns=4;s=MAIN.DL_Servo_1')
    method = parent.get_child("4:RPC_MoveAbs")
    arguments = [pos, speed]
    res = parent.call_method(method, *arguments)
    opcua_conn.disconnect()

    return 'done'

def get_field(frame, field1, field2, field3, field4, delay):
    
    # Define time interval
    end   = datetime.utcnow() - timedelta(seconds=0.9) # There is a 0.9 sec delay with redis
    start = end - timedelta(seconds=delay) 
    
    # Read data
    r = redis.from_url('redis://10.33.178.176:6379')

    # Extract data
    ts = r.ts()

     # Get ROI values
    result1 = ts.range(field1, unix_time_ms(start), unix_time_ms(end))
    result2 = ts.range(field2, unix_time_ms(start), unix_time_ms(end))
    result3 = ts.range(field3, unix_time_ms(start), unix_time_ms(end))
    result4 = ts.range(field4, unix_time_ms(start), unix_time_ms(end))
    output1 = [(x[1]) for x in result1]
    output2 = [(x[1]) for x in result2]
    output3 = [(x[1]) for x in result3]
    output4 = [(x[1]) for x in result4]
    #print(len(output1))
    
    # Get DL position
    temp   = ts.range('dl_pos_1', unix_time_ms(start), unix_time_ms(end))
    x_time = [(x[0] / 1000) for x in temp]
    x_pos0 = [(x[1]) for x in temp]

    # Interpolate DL position on ROIs time stamps
    vm = np.mean(x_pos0)
    f = interp1d(x_time, x_pos0, bounds_error=False, fill_value=vm, kind='cubic')
   
    # Convert to UTC time
    real_time1 = [(x[0] / 1000) for x in result1]
    real_time2 = [(x[0] / 1000) for x in result2]
    real_time3 = [(x[0] / 1000) for x in result3]
    real_time4 = [(x[0] / 1000) for x in result4]

    # Get DL position at the same time
    x_pos = f(real_time1)
    #min_flx = np.min(x_pos)
    #min_pos = x_pos.argmin(min_flx)
    #print(len(x_pos))

    # Compute elasped time
    real_time1 -= np.min(real_time1)
    real_time2 -= np.min(real_time2)
    real_time3 -= np.min(real_time3)
    real_time4 -= np.min(real_time4)

    # Return 
    return x_pos, output1, output2, output3, output4
   
# PLOT of ROI vs time
# Start animation
fig, (ax_t1, ax_t2, ax_t3, ax_t4) = plt.subplots(4, 1, figsize=(5,12))

# Label axes
ax_t1.clear() 
ax_t1.set_xlabel('DL position [microns]')
ax_t1.set_ylabel('ROI value')
ax_t2.clear() 
ax_t2.set_xlabel('DL position [microns]')
ax_t2.set_ylabel('ROI value')
ax_t3.clear() 
ax_t3.set_xlabel('DL position [microns]')
ax_t3.set_ylabel('ROI value')
ax_t4.clear() 
ax_t4.set_xlabel('DL position [microns]')
ax_t4.set_ylabel('ROI value')

# Loop over DL scanning iteratoin
dl_start = 1200 # microns
dl_end   = 1300
rel_pos  = dl_end - dl_start
speed    = 0.05 #mm/s

# Set DL to initial position
move_abs_dl(dl_start, speed)

# Loop over DL scans
margin = 1
delay  = 0.001*rel_pos/speed + margin
n_iter = 20
for it in range(n_iter):

    # Send DL comment
    move_rel_dl(rel_pos*(-1)^it, speed)  # Will go back and forth

    # Current DL positoin
    cur_pos = dl_start + rel_pos*(-1)^it
    print(cur_pos)

    # Get data
    data  = get_field('roi1_max', 'roi2_max', 'roi3_max', 'roi4_max',  delay)
    dl_pos = data[0]
    flux1  = data[1]
    flux2  = data[2]
    flux3  = data[3]
    flux4  = data[4]
    
    # Adjust the axis range for time plot
    x_min, x_max = np.min(dl_pos), np.max(dl_pos) 
    margin = 1
    ax_t1.set_xlim(x_min - margin, x_max + margin)
    ax_t2.set_xlim(x_min - margin, x_max + margin) 
    ax_t3.set_xlim(x_min - margin, x_max + margin)  
    ax_t4.set_xlim(x_min - margin, x_max + margin) 

    scale = 2
    y_min, y_max = np.min(flux1), np.max(flux1) 
    margin = scale*(y_max - y_min)
    ax_t1.set_ylim(y_min - margin, y_max + margin) 

    y_min, y_max = np.min(flux2), np.max(flux2) 
    margin = scale*(y_max - y_min)
    ax_t2.set_ylim(y_min - margin, y_max + margin) 

    y_min, y_max = np.min(flux3), np.max(flux3) 
    margin = scale*(y_max - y_min)
    ax_t3.set_ylim(y_min - margin, y_max + margin)

    y_min, y_max = np.min(flux4), np.max(flux4) 
    margin = scale*(y_max - y_min)
    ax_t4.set_ylim(y_min - margin, y_max + margin)     

    # Create a line object that will be updated
    line_t1, = ax_t1.plot(dl_pos, y, 'o', markersize=2)
    line_t2, = ax_t2.plot(dl_pos, y, 'o', markersize=2)
    line_t3, = ax_t3.plot(dl_pos, y, 'o', markersize=2)
    line_t4, = ax_t4.plot(dl_pos, y, 'o', markersize=2)

    plt.show()
# dl_pos_1