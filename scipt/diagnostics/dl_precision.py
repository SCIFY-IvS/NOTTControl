import sys
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/')
import redis
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit
from datetime import datetime
from datetime import date
from datetime import timedelta
from opcua import OPCUAConnection
from configparser import ConfigParser

epoch = datetime.utcfromtimestamp(0)

# Script parameters
# delay = 40.0 # s, window to consider when scanning the fringes

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

def fringes(dl_pos, ampl, delay):
    wav = 3.8
    bw  = 4.0
    return ampl*np.sinc(np.pi*bw*delay/wav**2)*np.cos(2*np.pi/wav*dl_pos)

# Move rel motor
def move_rel_dl(rel_pos, speed):
    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()
    
    parent = opcua_conn.client.get_node('ns=4;s=MAIN.DL_Servo_1')
    method = parent.get_child("4:RPC_MoveRel")
    arguments = [rel_pos, speed]
    res = parent.call_method(method, *arguments)
    opcua_conn.disconnect()
    time.sleep(2)

    return 'done'

# Move rel motor
def move_abs_dl(pos, speed):
    
    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()
    
    parent = opcua_conn.client.get_node('ns=4;s=MAIN.DL_Servo_1')
    method = parent.get_child("4:RPC_MoveAbs")
    arguments = [pos, speed]
    res = parent.call_method(method, *arguments)
    opcua_conn.disconnect()  
    time.sleep(12)
    
    return 'done'

def get_field(field1, field2, field3, field4, delay):
    
    # Define time interval
    end   = datetime.utcnow() # - timedelta(seconds=0.9) # There is a 0.9 sec delay with redis
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
    from pdb import set_trace
    # set_trace()
    # Interpolate DL position on ROIs time stamps
    vm = np.mean(x_pos0)
    f = interp1d(x_time, x_pos0, bounds_error=False, fill_value=vm, kind='cubic')
   
    # Convert to UTC time
    real_time1 = [(x[0] / 1000) for x in result1]
    real_time2 = [(x[0] / 1000) for x in result2]
    real_time3 = [(x[0] / 1000) for x in result3]
    real_time4 = [(x[0] / 1000) for x in result4]

    # Re-order
    print('Size camera output', len(real_time1))
    print('Size DL output', len(x_pos0))

    # Get DL position at the same time
    x_pos = f(real_time2)
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
plt.ion()
fig, (ax_t1) = plt.subplots(1, 1, figsize=(5,12))

# Label axes
ax_t1.clear() 
ax_t1.set_xlabel('DL position [microns]')
ax_t1.set_ylabel('ROI value')

# Loop over DL scanning iteratoin
dl_start = 1.200 # m
dl_end   = 1.300 # ms
rel_pos  = dl_end - dl_start
speed    = 0.02 #mm/s

# Set DL to initial position
move_abs_dl(dl_start, speed)

# Loop over DL scans
margin = 1
delay  = rel_pos/speed + margin
n_iter = 4
for it in range(n_iter):

    # Current DL positoin
    cur_pos = dl_start + rel_pos*(-1)**(it)
    print(cur_pos)

    # Send DL comment
    move_rel_dl(rel_pos*(-1)**it, speed)  # Will go back and forth

    # Get data
    data  = get_field('roi1_max', 'roi2_max', 'roi3_max', 'roi4_max',  delay)
    dl_pos = data[0]
    flux1  = data[1]
    flux2  = data[2]
    flux3  = data[3]
    flux4  = data[4]
        
    # Fit fringes
    flx_coh = flux2
    #flx_mean = np.mean(flux2)
    for i in range(len(flux2)):        
        #flx_coh[i] = flux2[i] - flx_mean
        flux2[i] -= it*2000

    # rearrange
    #idx = np.asort(dl_pos)
    #dl_pos = dl_pos[idx]
    #flux2 = flux2[idx]

    # Fit fringes
    #params, params_cov = curve_fit(fringes, dl_pos, flx_coh)
    #print(params[0])
    #print(1.9*params[1]/np.pi)
    #flx_fit = fringes(dl_pos, params[0], params[1])

    # Adjust the axis range for time plot
    x_min, x_max = np.min(1000*dl_start), np.max(1000*dl_end) 
    margin = 20
    ax_t1.set_xlim(x_min - margin, x_max + margin)

    scale = 1
    y_min, y_max = -30000, 30000#np.min(flux2), np.max(flux2) 
    margin = 0
    ax_t1.set_ylim(y_min - margin, y_max + margin)    

    # Create a line object that will be updated
    line_t1, = ax_t1.plot(dl_pos, flux2)
    #line_t1, = ax_t1.plot(dl_pos, flx_fit)

    plt.draw()
    plt.pause(0.5)

plt.ioff()
plt.show()

# Set DL to initial position
move_abs_dl(dl_start, speed)