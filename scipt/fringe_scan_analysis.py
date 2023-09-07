import redis
import time
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from datetime import date
from datetime import timedelta

epoch = datetime.utcfromtimestamp(0)

# Script parameters
delay = 10 # s, window to consider when scanning the fringes

# Function definitions
def unix_time_ms(time):
    return round((time - epoch).total_seconds() * 1000.0)

def real_time(unix_time):
    return datetime.utcfromtimestamp(unix_time / 1000)

# Initiate live loop and plot
#plt.ion()
fig, ax = plt.subplots()

for i in range(1):

    # Connect to REDIS database 
    r = redis.from_url('redis://10.33.178.176:6379')
    ts = r.ts()

    # Get all data for the fringe scan
    # Define time window
    end   = datetime.utcnow()
    start = end - timedelta(seconds=delay) 
    #print(epoch, start, end)
    
    # Get ROI values
    result_roi1 = ts.range('roi1_max', unix_time_ms(start), unix_time_ms(end))
    result_roi2 = ts.range('roi2_max', unix_time_ms(start), unix_time_ms(end))
    result_roi3 = ts.range('roi3_max', unix_time_ms(start), unix_time_ms(end))
    result_roi4 = ts.range('roi4_max', unix_time_ms(start), unix_time_ms(end))
    
    # Convert to UTC time
    real_time_time_roi1    = [(x[0] / 1000) for x in result_roi1]
    real_time_time_roi1    -= np.min(real_time_time_roi1)
    real_time_results_roi1 = [(x[1]) for x in result_roi1]
    real_time_results_roi2 = [(x[1]) for x in result_roi2]
    real_time_results_roi3 = [(x[1]) for x in result_roi3]
    real_time_results_roi4 = [(x[1]) for x in result_roi4]

    # Get DL position
    dl1_pos = ts.range('dl_pos_1', unix_time_ms(start), unix_time_ms(end))
    real_time_dl_time = [((x[0] / 1000)) for x in dl1_pos]
    real_time_dl_time -= np.min(real_time_dl_time)
    real_time_dl_pos  = [(x[1]) for x in dl1_pos]

    ax.clear() 
    ax.set_xlim(np.min(real_time_time_roi1), np.max(real_time_time_roi1))
    ax.set_ylim(np.min(real_time_results_roi1), np.max(real_time_results_roi1))
    ax.set_xlabel('Elapsed time [s]')
    ax.set_ylabel('ROI value')

    ax.plot(real_time_time_roi1, real_time_results_roi1, '-o')

    plt.draw()
    plt.show()
    time.sleep(1)

# Turn off plot plot
#plt.ioff

