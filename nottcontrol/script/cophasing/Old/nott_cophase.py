import redis
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy.interpolate import interp1d
from datetime import datetime
from datetime import date
from datetime import timedelta

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
    
    # Update line
    line_t1.set_xdata(real_time1)
    line_t1.set_ydata(output1)
    line_t2.set_xdata(real_time2)
    line_t2.set_ydata(output2)  
    line_t3.set_xdata(real_time3)   
    line_t3.set_ydata(output3)  
    line_t4.set_xdata(real_time4)
    line_t4.set_ydata(output4)

    # Update line
    line_f1.set_xdata(x_pos)   
    line_f1.set_ydata(output1)  
    line_f2.set_xdata(x_pos)   
    line_f2.set_ydata(output2)  
    line_f3.set_xdata(x_pos)   
    line_f3.set_ydata(output3)  
    line_f4.set_xdata(x_pos)   
    line_f4.set_ydata(output4)  

    # Adjust the axis range for time plot
    x_min, x_max = np.min(real_time1), np.max(real_time1) 
    margin = 1
    ax_t1.set_xlim(x_min - margin, x_max + margin)
    ax_t2.set_xlim(x_min - margin, x_max + margin) 
    ax_t3.set_xlim(x_min - margin, x_max + margin)  
    ax_t4.set_xlim(x_min - margin, x_max + margin) 

    scale = 2
    y_min, y_max = np.min(output1), np.max(output1) 
    margin = scale*(y_max - y_min)
    ax_t1.set_ylim(y_min - margin, y_max + margin) 

    y_min, y_max = np.min(output2), np.max(output2) 
    margin = scale*(y_max - y_min)
    ax_t2.set_ylim(y_min - margin, y_max + margin) 

    y_min, y_max = np.min(output3), np.max(output3) 
    margin = scale*(y_max - y_min)
    ax_t3.set_ylim(y_min - margin, y_max + margin)
 
    y_min, y_max = np.min(output4), np.max(output4) 
    margin = scale*(y_max - y_min)
    ax_t4.set_ylim(y_min - margin, y_max + margin) 

    # Adjust the axis range for frequency plot
    x_min, x_max = 1180, 1280 # Fringes are at around 1200 (Sept. 2023)
    margin = 0
    ax_f1.set_xlim(x_min - margin, x_max + margin) 
    ax_f2.set_xlim(x_min - margin, x_max + margin) 
    ax_f3.set_xlim(x_min - margin, x_max + margin) 
    ax_f4.set_xlim(x_min - margin, x_max + margin) 

    scale = 2
    y_min, y_max = np.min(output1), np.max(output1) 
    margin = scale*(y_max - y_min)
    ax_f1.set_ylim(y_min - margin, y_max + margin) 

    y_min, y_max = np.min(output2), np.max(output2) 
    margin = scale*(y_max - y_min)
    ax_f2.set_ylim(y_min - margin, y_max + margin) 

    y_min, y_max = np.min(output3), np.max(output3) 
    margin = scale*(y_max - y_min)
    ax_f3.set_ylim(y_min - margin, y_max + margin)
 
    y_min, y_max = np.min(output4), np.max(output4) 
    margin = scale*(y_max - y_min)
    ax_f4.set_ylim(y_min - margin, y_max + margin) 

    # Return 
    return line_f1, line_t1, line_f2, line_t2, line_f3, line_t3, line_f4, line_t4 

# PLOT of ROI vs time
# Start animation
fig, ((ax_t1, ax_f1), (ax_t2, ax_f2), (ax_t3, ax_f3), (ax_t4, ax_f4)) = plt.subplots(4, 2, figsize=(10,12))

# Label axes
ax_t1.clear() 
ax_t1.set_xlabel('Elapsed time [s]')
ax_t1.set_ylabel('ROI value')
ax_t2.clear() 
ax_t2.set_xlabel('Elapsed time [s]')
ax_t2.set_ylabel('ROI value')
ax_t3.clear() 
ax_t3.set_xlabel('Elapsed time [s]')
ax_t3.set_ylabel('ROI value')
ax_t4.clear() 
ax_t4.set_xlabel('Elapsed time [s]')
ax_t4.set_ylabel('ROI value')

ax_f1.clear() 
ax_f1.set_xlabel('DL position [microns]')
ax_f1.set_ylabel('ROI value')
ax_f2.clear() 
ax_f2.set_xlabel('DL position [microns]')
ax_f2.set_ylabel('ROI value')
ax_f3.clear() 
ax_f3.set_xlabel('DL position [microns]')
ax_f3.set_ylabel('ROI value')
ax_f4.clear() 
ax_f4.set_xlabel('DL position [microns]')
ax_f4.set_ylabel('ROI value')

# Some initial data
x = np.linspace(0, delay, 10)
y = np.cos(x)

# Create a line object that will be updated
line_t1, = ax_t1.plot(x, y, 'o', markersize=2)
line_f1, = ax_f1.plot(x, y, 'o', markersize=2)
line_t2, = ax_t2.plot(x, y, 'o', markersize=2)
line_f2, = ax_f2.plot(x, y, 'o', markersize=2)
line_t3, = ax_t3.plot(x, y, 'o', markersize=2)
line_f3, = ax_f3.plot(x, y, 'o', markersize=2)
line_t4, = ax_t4.plot(x, y, 'o', markersize=2)
line_f4, = ax_f4.plot(x, y, 'o', markersize=2)

# Start animation
ani_roi = FuncAnimation(fig, get_field, frames=range(100), fargs=('roi1_max', 'roi2_max', 'roi3_max', 'roi4_max',  delay), blit=False)  

plt.show()
# dl_pos_1