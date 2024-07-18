import redis
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from datetime import datetime
from datetime import date
from datetime import timedelta

epoch = datetime.utcfromtimestamp(0)

# Script parameters
delay = 2.0 # s, window to consider when scanning the fringes

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

    # Convert to UTC time
    real_time1 = [(x[0] / 1000) for x in result1]
    real_time1 -= np.min(real_time1)
    real_time2 = [(x[0] / 1000) for x in result2]
    real_time2 -= np.min(real_time2)
    real_time3 = [(x[0] / 1000) for x in result3]
    real_time3 -= np.min(real_time3)
    real_time4 = [(x[0] / 1000) for x in result4]
    real_time4 -= np.min(real_time4)

    # Compute power spectrum
    fs = compute_mean_sampling(real_time1)
    print(f"Mean Sampling rate: {fs:.2f} Hz")
    fft1 = np.fft.fft(output1)
    pow1 = np.abs(fft1)**2
    freq1 = np.fft.fftfreq(len(fft1), 1/fs)
    fft2 = np.fft.fft(output2)
    pow2 = np.abs(fft2)**2
    freq2 = np.fft.fftfreq(len(fft2), 1/fs)
    fft3 = np.fft.fft(output3)
    pow3 = np.abs(fft3)**2
    freq3 = np.fft.fftfreq(len(fft3), 1/fs)
    fft4 = np.fft.fft(output4)
    pow4 = np.abs(fft4)**2
    freq4 = np.fft.fftfreq(len(fft4), 1/fs)
    
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
    line_f1.set_xdata(freq1[freq1 > 0])   
    line_f1.set_ydata(pow1[freq1 > 0])  
    line_f2.set_xdata(freq2[freq2 > 0])   
    line_f2.set_ydata(pow2[freq2 > 0])  
    line_f3.set_xdata(freq3[freq3 > 0])   
    line_f3.set_ydata(pow3[freq3 > 0])  
    line_f4.set_xdata(freq4[freq4 > 0])   
    line_f4.set_ydata(pow4[freq4 > 0])  

    # Adjust the axis range for time plot
    x_min, x_max = np.min(real_time1), np.max(real_time1) 
    margin = 0
    ax_t1.set_xlim(x_min - margin, x_max + margin)
    ax_t2.set_xlim(x_min - margin, x_max + margin) 
    ax_t3.set_xlim(x_min - margin, x_max + margin)  
    ax_t4.set_xlim(x_min - margin, x_max + margin) 

    scale = 4
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
    x_min, x_max = 0, np.max(freq1) 
    margin = 0
    ax_f1.set_xlim(x_min - margin, x_max + margin) 
    ax_f2.set_xlim(x_min - margin, x_max + margin) 
    ax_f3.set_xlim(x_min - margin, x_max + margin) 
    ax_f4.set_xlim(x_min - margin, x_max + margin) 

    y_min, y_max = np.min(pow1), np.max(pow1) 
    margin = 0.2*(y_max - y_min)
    ax_f1.set_ylim(y_min - margin, y_max + margin) 

    y_min, y_max = np.min(pow2), np.max(pow2) 
    margin = 0.2*(y_max - y_min)
    ax_f2.set_ylim(y_min - margin, y_max + margin) 

    y_min, y_max = np.min(pow3), np.max(pow3) 
    margin = 0.2*(y_max - y_min)
    ax_f3.set_ylim(y_min - margin, y_max + margin) 

    y_min, y_max = np.min(pow4), np.max(pow4) 
    margin = 0.2*(y_max - y_min)
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
ax_f1.set_xlabel('Frequency [Hz]')
ax_f1.set_ylabel('Power spectrum')
ax_f1.set_xscale('log')
ax_f1.set_yscale('log')
ax_f2.clear() 
ax_f2.set_xlabel('Frequency [Hz]')
ax_f2.set_ylabel('Power spectrum')
ax_f2.set_xscale('log')
ax_f2.set_yscale('log')
ax_f3.clear() 
ax_f3.set_xlabel('Frequency [Hz]')
ax_f3.set_ylabel('Power spectrum')
ax_f3.set_xscale('log')
ax_f3.set_yscale('log')
ax_f4.clear() 
ax_f4.set_xlabel('Frequency [Hz]')
ax_f4.set_ylabel('Power spectrum')
ax_f4.set_xscale('log')
ax_f4.set_yscale('log')

# Some initial data
x = np.linspace(0, delay, 10)
y = np.cos(x)

# Create a line object that will be updated
line_t1, = ax_t1.plot(x, y)
line_f1, = ax_f1.plot(x, y)
line_t2, = ax_t2.plot(x, y)
line_f2, = ax_f2.plot(x, y)
line_t3, = ax_t3.plot(x, y)
line_f3, = ax_f3.plot(x, y)
line_t4, = ax_t4.plot(x, y)
line_f4, = ax_f4.plot(x, y)

# Start animation
ani_roi = FuncAnimation(fig, get_field, frames=range(100), fargs=('roi1_max', 'roi2_max', 'roi3_max', 'roi4_max',  delay), blit=False)  

plt.show()
# dl_pos_1