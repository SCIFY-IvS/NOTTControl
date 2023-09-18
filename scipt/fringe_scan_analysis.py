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
delay = 4.0 # s, window to consider when scanning the fringes

# Function definitions
def unix_time_ms(time):
    return round((time - epoch).total_seconds() * 1000.0)

def real_time(unix_time):
    return datetime.utcfromtimestamp(unix_time / 1000)

def get_field(frame, field, delay):
    
    # Define time interval
    end   = datetime.utcnow()
    start = end - timedelta(seconds=delay) 
    
    # Read data
    r = redis.from_url('redis://10.33.178.176:6379')

    # Extract data
    ts = r.ts()

     # Get ROI values
    result = ts.range(field, unix_time_ms(start), unix_time_ms(end))
    output = [(x[1]) for x in result]
    
    # Convert to UTC time
    real_time = [(x[0] / 1000) for x in result]
    real_time -= np.min(real_time)

    # Update line
    line.set_xdata(real_time)   
    line.set_ydata(output)  

    # Adjust the axis range
    x_min, x_max = np.min(real_time), np.max(real_time) 
    margin = 0
    ax.set_xlim(x_min - margin, x_max + margin) 

    y_min, y_max = np.min(output), np.max(output) 
    margin = 0.2*(y_max - y_min)
    ax.set_ylim(y_min - margin, y_max + margin) 

    # Return 
    return line

# Start animation
fig, ax = plt.subplots()

# Label axes
ax.clear() 
ax.set_xlabel('Elapsed time [s]')
ax.set_ylabel('ROI value')

# Some initial data
x = np.linspace(0, delay, 10)
y = np.cos(x)

# Create a line object that will be updated
line, = ax.plot(x, y)

# Start animation
ani_roi = FuncAnimation(fig, get_field, frames=range(100), fargs=('roi1_max', delay), blit=False)  

plt.show()
# dl_pos_1