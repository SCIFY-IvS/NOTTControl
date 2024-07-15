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

def fringes(dl_pos, ampl, g_delay, p_delay):
    # Spectrogon Saphire L narrow
    wav = 3.8
    bw  = 0.180  
    # Spectrogon Saphsire L band
    #wav = 3.7
    #bw  = 0.6  
    return ampl*np.sinc(2*(dl_pos-g_delay)*bw/wav**2)*np.cos(2*np.pi/wav*2*(dl_pos-p_delay))   # See Lawson 2001, Eq 2.7. Factor 2 because delay line postion is twice the OPD

def fringes2(dl_pos, ampl, g_delay, p_delay, bw):
    # Spectrogon Saphire L narrow
    wav = 3.8
    # bw  = 0.180  # Spectrogon Saphire L band
    # Spectrogon Saphsire L band
    #wav = 3.7
    #bw  = 0.6  
    return ampl*np.sinc(2*(dl_pos-g_delay)*bw/wav**2)*np.cos(2*np.pi/wav*2*(dl_pos-p_delay))   # See Lawson 2001, Eq 2.7. Factor 2 because delay line postion is twice the OPD

def fringes_env(dl_pos, ampl, g_delay):
    wav = 3.8
    bw  = 0.180  # Spectrogon Saphire L band
    # Spectrogon Saphire L band
    #wav = 3.7
    #bw  = 0.6 
    return abs(ampl*np.sinc(2*(dl_pos-g_delay)*bw/wav**2)) # See Lawson 2001, Eq 2.7. Factor 2 because delay line postion is twice the OPD

def fringes_env2(dl_pos, ampl, g_delay, bw):
    wav = 3.8
    # bw  = 0.180  # Spectrogon Saphire L band
    # Spectrogon Saphire L band
    #wav = 3.7
    #bw  = 0.6 
    return abs(ampl*np.sinc(2*(dl_pos-g_delay)*bw/wav**2)) # See Lawson 2001, Eq 2.7. Factor 2 because delay line postion is twice the OPD

def enveloppe(dl_pos, flx_coh):
    # Define the bins
    dl_min  = np.min(dl_pos)
    dl_max  = np.max(dl_pos)
    wav     = 3.8 # in um
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

# Move rel motor
def move_rel_dl(rel_pos, speed, opcua_motor):

    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()
    
    # parent = opcua_conn.client.get_node('ns=4;s=MAIN.DL_Servo_1')
    parent = opcua_conn.client.get_node('ns=4;s=MAIN.'+opcua_motor)
    method = parent.get_child("4:RPC_MoveRel")
    arguments = [rel_pos, speed]
    res = parent.call_method(method, *arguments)
    
    # Wait for the DL to be ready
    on_destination = False
    while not on_destination:
        time.sleep(0.01)
        # status, state = opcua_conn.read_nodes(['ns=4;s=MAIN.DL_Servo_1.stat.sStatus', 'ns=4;s=MAIN.DL_Servo_1.stat.sState'])
        status, state = opcua_conn.read_nodes(['ns=4;s=MAIN.'+opcua_motor+'.stat.sStatus', 'ns=4;s=MAIN.'+opcua_motor+'.stat.sState'])

        on_destination = status == 'STANDING' and state == 'OPERATIONAL'

    # Disconnect
    opcua_conn.disconnect()
    return 'done'

# Move abs motor
def move_abs_dl(pos, speed, opcua_motor):
    
    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']

    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()
    
    # parent = opcua_conn.client.get_node('ns=4;s=MAIN.DL_Servo_'+dl_id)
    parent = opcua_conn.client.get_node('ns=4;s=MAIN.'+opcua_motor)
    method = parent.get_child("4:RPC_MoveAbs")
    arguments = [pos, speed]
    res = parent.call_method(method, *arguments)
    
    # Wait for the DL to be ready
    on_destination = False
    while not on_destination:
        time.sleep(0.01)
        # status, state = opcua_conn.read_nodes(["ns=4;s=MAIN.DL_Servo_1.stat.sStatus", "ns=4;s=MAIN.DL_Servo_1.stat.sState"])
        status, state = opcua_conn.read_nodes(['ns=4;s=MAIN.'+opcua_motor+'.stat.sStatus', 'ns=4;s=MAIN.'+opcua_motor+'.stat.sState'])

        on_destination = status == 'STANDING' and state == 'OPERATIONAL'

    # Disconnect
    opcua_conn.disconnect()      
    return 'done'

def get_field(field1, field2, field3, field4, delay, dl_name):
    
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
    
    # Get DL position
    # temp   = ts.range('dl_pos_1', unix_time_ms(start), unix_time_ms(end))
    temp   = ts.range(dl_name, unix_time_ms(start), unix_time_ms(end))
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

    # Re-order
    #print('Size camera output', len(real_time1))
    #print('Size DL output', len(x_pos0))

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
   
def grab_flux(delay, dl_name):
    data_at_null  = get_field('roi1_max', 'roi2_max', 'roi3_max', 'roi4_max',  delay, dl_name)
    dl_pos = data_at_null[0]
    flux2  = data_at_null[2]
    bck = data_at_null[3]
        
    # Rearrange
    idx    = np.argsort(dl_pos)
    flux2  = np.array(flux2)
    flux2  = flux2[idx]
    dl_pos = dl_pos[idx]

    # Fit fringes
    flx_coh = flux2.copy()
    flx_mean = np.mean(flux2)
    flx_coh = flx_coh - flx_mean

    return dl_pos, flx_coh, data_at_null[2], bck

def read_current_pos(opcua_motor):
    # Read current position
    # initialize the OPC UA connection
    config = ConfigParser()
    config.read('../../config.ini')
    url =  config['DEFAULT']['opcuaaddress']
    opcua_conn = OPCUAConnection(url)
    opcua_conn.connect()
    target_pos = opcua_conn.read_node('ns=4;s=MAIN.'+opcua_motor+'.stat.lrPosActual')
    target_pos = target_pos * 1000
    opcua_conn.disconnect()

    return target_pos

def envelop_detector(signal):
    signal -= signal.mean()
    analytic_signal = hilbert(signal)
    flx_env = np.abs(analytic_signal)
    
    return flx_env

def save_data(data, path, name):
    print('MSG - Save data in:', path+name)
    list_saved_files = [elt for elt in os.listdir(path) if name in elt]
    count_file = len(list_saved_files) + 1
    name_file = name+'_%03d.pkl'%(count_file)
    dbfile = open(path + name_file, 'wb')
    pickle.dump(data, dbfile)
    dbfile.close()

def move_figure(f, x, y):
    """Move figure's upper left corner to pixel (x, y)"""
    backend = matplotlib.get_backend()
    if backend == 'TkAgg':
        f.canvas.manager.window.wm_geometry("+%d+%d" % (x, y))
    elif backend == 'WXAgg':
        f.canvas.manager.window.SetPosition((x, y))
    else:
        # This works for QT and GTK
        # You can also use window.setGeometry
        f.canvas.manager.window.move(x, y)

# PLOT of ROI vs time
# Start animation
plt.ion()
fig1, (ax1_t1, ax1_t2) = plt.subplots(2, 1, figsize=(8,5)) # Display scan forth
move_figure(fig1, 0, 0)
fig2, (ax2_t1, ax2_t2) = plt.subplots(2, 1, figsize=(8,5)) # Display scan back

# Label axes
ax1_t1.clear() 
ax1_t1.set_xlabel('DL position [microns]')
ax1_t1.set_ylabel('ROI value')
ax1_t2.clear() 
ax1_t2.set_xlabel('DL position [microns]')
ax1_t2.set_ylabel('ROI value')

ax2_t1.clear() 
ax2_t1.set_xlabel('DL position [microns]')
ax2_t1.set_ylabel('ROI value')
ax2_t2.clear() 
ax2_t2.set_xlabel('DL position [microns]')
ax2_t2.set_ylabel('ROI value')

# Loop over DL scanning iteration
dl_id = 1
speed = 0.005 #mm/s
wait_time = 0.08 / speed * 3 # Time in sec to scan X times the coherent envelope
grab_range = 0.08 / speed * 8 # Time in sec to scan X times the coherent envelope

if dl_id == 2:
    opcua_motor = 'nott_ics.Delay_Lines.NDL2'
    dl_name = 'DL_2_pos'
    dl_start = 1. # mm
    dl_end   = 1.3 # mm
    dl_init_pos1 = 1.65 # mm
    move_abs_dl(dl_init_pos1, speed, 'nott_ics.Delay_Lines.NDL1') # Move DL1 to its reference position
else:
    opcua_motor = 'nott_ics.Delay_Lines.NDL1'
    dl_name = 'DL_1_pos'
    dl_start = 1.85 # mm
    dl_end   = 2.05 # mm
    dl_init_pos2  = 0. # mm
    # dl_start, dl_end = dl_end, dl_start
    move_abs_dl(dl_init_pos2, speed, 'nott_ics.Delay_Lines.NDL2') # Move DL2 to its reference position

# =============================================================================
# Global scan
# =============================================================================
"""
Here we check the ability of the DL to perform global sca, find the null and reach it.
Given the backlash, reaching a position is always made from the same direction.

Two methods are tested:
    - single pass then reach the null
    - several pass and reach the average null
    
Null position can be defined as:
    - the minimum value of the flux during the scan
    - minimum value given a fit of the envelope then a fit of the fringes
It appears that none of these techniques accurately find the null, it will
mostly lock on the bright fringe, sometimes on the null and sometimes on a partial fringe.
The reason is not clear but it is the case for all the tests led with this script.

All tests use the ROI2 output.
"""
rel_pos  = dl_end - dl_start

# # Wait for the other delay lines to reach its position
# wait_time = 3. # in second
# print('Wait for the other delay lines to reach its position (%s sec)'%(wait_time))
# time.sleep(wait_time)

# Set DL to initial position
print('MSG - Move DL to initial position:', )
move_abs_dl(dl_start, speed, opcua_motor)

# Loop over DL scans
margin = 1
delay = abs(rel_pos)/speed + margin
n_pass = 10 # even number=back and forth
null_pos = np.array(range(n_pass), dtype=float)
# grab_range = delay

null_scans = []
null_scans_pos = []
null_scans_best_pos = []
nb_back_forth = n_pass // 2
gd_params = []

for it in range(n_pass):
    print('MSG - Pass', it+1, '/', n_pass)
    # Current DL positoin
    cur_pos = dl_start + rel_pos*(-1)**(it)
    #print(cur_pos)

    # Send DL comment
    move_rel_dl(rel_pos*(-1)**it, speed, opcua_motor)  # Will go back and forth

    # Get data
    data  = get_field('roi1_max', 'roi2_max', 'roi3_max', 'roi4_max',  delay, dl_name)
    dl_pos = data[0]
    flux1  = data[1]
    flux2  = data[2]
    flux3  = data[3]
    flux4  = data[4]
        
    # Rearrange
    idx    = np.argsort(dl_pos)
    flux2  = np.array(flux2)
    flux2  = flux2[idx]
    dl_pos = dl_pos[idx]

    # Fit fringes
    flx_coh = flux2.copy()
    flx_mean = np.mean(flux2)
    flx_coh = flx_coh - flx_mean

    # # Save dl_pos and coherent flux
    null_scans.append(flx_coh)
    null_scans_pos.append(dl_pos)

    # Find enveloppe
    # pos_env, flx_env = enveloppe(dl_pos, flx_coh)
    flx_env = envelop_detector(flx_coh)
    pos_env = dl_pos

    # Fit group delay to enveloppe
    func_to_fit = fringes_env2
    ampl         = np.abs(np.max(flx_coh)-np.min(flx_coh))/2
    # init_guess   = [ampl, 1000*np.abs(np.max(dl_end)+np.min(dl_start))/2]
    # lower_bounds = [0.95*ampl, 1000*dl_start]
    # upper_bounds = [1.05*ampl, 1000*dl_end]
    init_guess   = [ampl, 1000*np.abs(np.max(dl_end)+np.min(dl_start))/2, 0.18]
    lower_bounds = [0.95*ampl, 1000*min(dl_start,dl_end), 0.1]
    upper_bounds = [1.05*ampl, 1000*max(dl_start,dl_end), 0.3]
    params, params_cov = curve_fit(func_to_fit, pos_env, flx_env, p0=init_guess, bounds=(lower_bounds, upper_bounds))
    print('FIT GD - Minimum value and its position:', flx_coh.min(), dl_pos[np.argmin(flx_coh)])
    print('FIT GD - Fringes amplitude :', params[0])
    print('FIT GD - Group delay [microns]:', params[1])
    print('FIT GD - Bandwidth [microns]:', params[2])
    gd_params.append(params)
   
    # Extract best-fit envelop
    pos_env = np.linspace(dl_pos.min(), dl_pos.max(), dl_pos.size*2+1)
    flx_env = func_to_fit(pos_env, *params)

    # Now fit fringes
    func_to_fit = fringes2
    # init_guess   = [params[0], params[1], 0.95]
    # lower_bounds = [0.99*params[0], 0.99*params[1], 0]
    # upper_bounds = [1.01*params[0], 1.01*params[1], 1.9]
    init_guess   = [params[0], params[1], 0.95, params[2]]
    lower_bounds = [0.999*params[0], 0.999*params[1], 0, 0.999*params[2]]
    upper_bounds = [1.001*params[0], 1.001*params[1], 1.9, 1.001*params[2]]
    params, params_cov = curve_fit(func_to_fit, dl_pos, flx_coh, p0=init_guess, bounds=(lower_bounds, upper_bounds))
    print('FIT PD - Fringes amplitude :', params[0])
    print('FIT PD - Group delay [microns]:', params[1])
    print('FIT PD - Phase delay [microns]:', params[2])
    print('FIT PD - Bandwidth [microns]:', params[3])
    #pos_fit, flx_fit = enveloppe(dl_pos, flx_coh) # This works!
    
    # Extract fitted curve
    pos_fit = np.linspace(dl_pos.min(), dl_pos.max(), dl_pos.size*2+1)
    flx_fit = func_to_fit(pos_fit, *params)

    # Find best position
    idx_null     = np.argmin(flx_fit)
    # null_pos[it] = dl_pos[idx_null]
    null_pos[it] = pos_fit[idx_null]
    print('RESULT - Position of the null :', null_pos[it])
    null_scans_best_pos.append(null_pos[it])

    # Adjust the axis range for time plot
    x_min, x_max = np.min(1000*min(dl_start,dl_end)), np.max(1000*max(dl_start,dl_end)) 
    marginx = 25

    scale = 1
    y_min, y_max = np.min(flx_coh), np.max(flx_coh) 
    marginy = 0

    if (it+1)%2 != 0:
        # Clear the axes
        ax1_t1.clear() 
        fig1.suptitle('Forth direction - Best null pos: %.5f'%(null_scans_best_pos[-1]))
        ax1_t1.set_xlabel('DL position [microns]')
        ax1_t1.set_ylabel('ROI value')
        ax1_t2.clear() 
        ax1_t2.set_xlabel('DL position [microns]')
        ax1_t2.set_ylabel('ROI value')

        # Set x and y dynamic ranges
        ax1_t1.set_ylim(y_min - marginy, y_max + marginy)    
        ax1_t2.set_ylim(y_min - marginy, y_max + marginy)    
        ax1_t1.set_xlim(x_min - marginx, x_max + marginx)
        ax1_t2.set_xlim(null_scans_best_pos[-1] - marginx, null_scans_best_pos[-1] + marginx)

        # Plot curves
        line_t3, = ax1_t1.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
        line_t2, = ax1_t1.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
        line_t1, = ax1_t1.plot(dl_pos, flx_coh, label='Fringes')
        line_t4 = ax1_t1.axvline(null_scans_best_pos[-1], y_min - margin, y_max + margin, color='magenta', label='Best null')
        ax1_t1.legend(loc='best')

        line_t3, = ax1_t2.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
        line_t2, = ax1_t2.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
        line_t1, = ax1_t2.plot(dl_pos, flx_coh, label='Fringes')
        line_t4 = ax1_t2.axvline(null_scans_best_pos[-1], y_min - margin, y_max + margin, color='magenta', label='Best null')
    else:
        # Clear the axes
        fig2.suptitle('Back direction - Best null pos: %.5f'%(null_scans_best_pos[-1]))
        ax2_t1.clear() 
        ax2_t1.set_xlabel('DL position [microns]')
        ax2_t1.set_ylabel('ROI value')
        ax2_t2.clear() 
        ax2_t2.set_xlabel('DL position [microns]')
        ax2_t2.set_ylabel('ROI value')
        
        # Set x and y dynamic ranges
        ax2_t1.set_ylim(y_min - marginy, y_max + marginy)    
        ax2_t2.set_ylim(y_min - marginy, y_max + marginy)    
        ax2_t1.set_xlim(x_min - marginx, x_max + marginx)
        ax2_t2.set_xlim(null_scans_best_pos[-1] - marginx, null_scans_best_pos[-1] + marginx)

        # Plot curves
        line_t3, = ax2_t1.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
        line_t2, = ax2_t1.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
        line_t1, = ax2_t1.plot(dl_pos, flx_coh, label='Fringes')
        line_t4 = ax2_t1.axvline(null_scans_best_pos[-1], y_min - margin, y_max + margin, color='magenta', label='Best null')
        ax2_t1.legend(loc='best')

        line_t3, = ax2_t2.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
        line_t2, = ax2_t2.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
        line_t1, = ax2_t2.plot(dl_pos, flx_coh, label='Fringes')
        line_t4 = ax2_t2.axvline(null_scans_best_pos[-1], y_min - margin, y_max + margin, color='magenta', label='Best null')

    plt.draw()
    plt.tight_layout()
    plt.pause(0.5)

print('MSG - End of pass')

# =============================================================================
# Set DL to NULL
# =============================================================================
print('\n*** Set DL to NULL ***')
speed2 = speed
current_pos = read_current_pos(opcua_motor)
print('MSG - Current position:', current_pos)
print('MSG - Now moving to null position :', null_pos[0])
cmd_null = (null_pos[0] - current_pos)/1000
print('Sending command', cmd_null)
move_rel_dl(cmd_null, speed2, opcua_motor)
#move_abs_dl(null_pos[0]/1000, speed, opcua_motor)
# Save the last move to check how precise the null is reached
time.sleep(wait_time)
to_null_pos, to_null_flx, to_null_flx2, bck = grab_flux(grab_range, dl_name)
print('MSG - Reached position', read_current_pos(opcua_motor))
print('MSG - Gap position', read_current_pos(opcua_motor) - null_pos[0])
# cmd_null = (null_pos[0] - read_current_pos(opcua_motor))/1000*2
# print('Sending correction command', cmd_null)
# print('MSG - Gap position after correction', read_current_pos(opcua_motor) - null_pos[0])

plt.figure()
t_scale = np.linspace(-grab_range, 0., len(to_null_flx2))
plt.plot(t_scale, to_null_flx2)
plt.grid()
plt.xlabel('Time (s)')
plt.ylabel('Flux (count)')
plt.title('Reached null position: %.5f\nTargeted position: %.5f'%(read_current_pos(opcua_motor), null_pos[0]))

line_t5 = ax1_t1.axvline(read_current_pos(opcua_motor), y_min - margin, y_max + margin, ls='--', color='magenta', label='Final position')
line_t5 = ax1_t2.axvline(read_current_pos(opcua_motor), y_min - margin, y_max + margin, ls='--', color='magenta', label='Final position')
ax1_t1.legend(loc='best')
line_t5 = ax2_t1.axvline(read_current_pos(opcua_motor), y_min - margin, y_max + margin, ls='--', color='magenta', label='Final position')
line_t5 = ax2_t2.axvline(read_current_pos(opcua_motor), y_min - margin, y_max + margin, ls='--', color='magenta', label='Final position')
ax2_t1.legend(loc='best')

print('TODO - Close the plot(s) to continue')
plt.ioff()
plt.show()

# Go back to starting position when closed
print('MSG - Moving back to initial position')
move_abs_dl(dl_start, speed, opcua_motor)
time.sleep(1.) # the DL overshoot, let it time to reach the targeted position

# =============================================================================
# Set DL to average NULL position
# =============================================================================
print('\n*** Set DL to average NULL position ***')
null_scans_best_pos = np.array(null_scans_best_pos)
null_scans_best_pos = np.reshape(null_scans_best_pos, (2, -1))

avg_null_pos = np.mean(null_scans_best_pos[0])
current_pos = read_current_pos(opcua_motor)
print('MSG - Current position:', current_pos)
print('MSG - Now moving to null position :', avg_null_pos)
cmd_pos = (avg_null_pos - current_pos)/1000
print('MSG - Sending command', cmd_pos)
move_rel_dl(cmd_pos, speed, opcua_motor)
# Save the last move to check how precise the null is reached
time.sleep(wait_time)
to_null_pos_avg, to_null_flx_avg, to_null_flx_avg2, bck = grab_flux(grab_range, dl_name)
print('MSG - Reached position', read_current_pos(opcua_motor))
print('MSG - Gap position', read_current_pos(opcua_motor) - null_pos[0])

plt.figure(figsize=(10, 5))
plt.subplot(121)
plt.plot(to_null_flx2)
plt.grid()
plt.xlabel('Time (count)')
plt.ylabel('Flux (count)')
plt.title('Reached null position 1st scan (%.5f)'%(null_pos[0]))
plt.subplot(122)
plt.plot(to_null_flx_avg2)
plt.grid()
plt.xlabel('Time (count)')
plt.ylabel('Flux (count)')
plt.title('Reached null position (average strategy, %.5f)'%(avg_null_pos))
plt.tight_layout()

print('TODO - Close the plot(s) to continue')
plt.ioff()
plt.show()

# Go back to starting position when closed
print('MSG - Moving back to initial position')
move_abs_dl(dl_start, speed, opcua_motor)

# Show results of the scans, individual scan can have different numbers of points
scans_forth = null_scans[::2]
scans_forth_pos = null_scans_pos[::2]
scans_back = null_scans[1::2]
scans_back_pos = null_scans_pos[1::2]

# This plot shows how repeatable a scan is
plt.figure()
plt.subplot(211)
[plt.plot(scans_forth_pos[i], scans_forth[i], label='Forth') for i in range(len(scans_forth))]
plt.grid()
plt.xlabel('DL pos (um)')
plt.ylabel('Flux (count)')
plt.legend(loc='best')
plt.subplot(212)
[plt.plot(scans_back_pos[i], scans_back[i], label='Back') for i in range(len(scans_back))]
plt.grid()
plt.xlabel('DL pos (um)')
plt.ylabel('Flux (count)')
plt.legend(loc='best')
plt.tight_layout()

print('TODO - Close the plot(s) to continue')
plt.ioff()
plt.show()

# Save the data
save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/scipt/diagnostics/'
name_file = 'null_scans_'+opcua_motor+'_speed_%s'%(speed)
db = {'scans_forth_pos':scans_forth_pos, 'scans_forth':scans_forth, \
      'scans_back_pos':scans_back_pos, 'scans_back':scans_back,\
        'null_scans_best_pos': null_scans_best_pos,\
            'to_null':[to_null_pos, to_null_flx, to_null_flx2],\
                 'to_null_avg':[to_null_pos_avg, to_null_flx_avg, to_null_flx_avg2],
                 'bck':[bck]}

save_data(db, save_path, name_file)

# =============================================================================
# Repeat DL location
# =============================================================================
"""
Here we qualify the ability of the DL to reach precisely and accurately a position given
a relative move.
"""
print('\n*** Repeatedly Setting DL to NULL ***')

targeted_pos = null_pos[0] # null_scans_pos[0][np.argmin(null_scans[0])]

scans_forth = null_scans[::2]
scans_forth_pos = null_scans_pos[::2]
scans_back = null_scans[1::2]
scans_back_pos = null_scans_pos[1::2]

repeat_null_flx = []
repeat_null_pos = []
repeat_reached_pos = []
repeat_bck = []
n_repeat = 10

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10,5))
ax1.grid()
ax2.grid()

for k in range(n_repeat):
    print('Reaching null', k+1, '/', n_repeat)
    current_pos = read_current_pos(opcua_motor)
    print('MSG - Current position:', current_pos)
    print('MSG - Now moving to null position :', targeted_pos)
    cmd_null = (targeted_pos - current_pos)/1000
    print('Sending command', cmd_null)
    move_rel_dl(cmd_null, speed, opcua_motor)
    
    # Save the last move to check how precise the null is reached
    time.sleep(wait_time)
    to_null_pos, to_null_flx, to_null_flx2, bck = grab_flux(grab_range, dl_name)
    repeat_null_pos.append(to_null_pos)
    repeat_null_flx.append(to_null_flx2)
    repeat_bck.append(bck)
    reached_pos = read_current_pos(opcua_motor)
    print('MSG - Reached position', reached_pos)
    repeat_reached_pos.append(reached_pos)
    print('MSG - Gap position', read_current_pos(opcua_motor) - null_pos[0])

    t_scale = np.linspace(-grab_range, 0., len(to_null_flx2))
    ax1.plot(t_scale, to_null_flx2)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Flux (count)')
    ax2.plot(to_null_pos, to_null_flx2)
    ax2.set_xlabel('DL pos (um)')
    ax2.set_ylabel('Flux (count)')
    fig.suptitle('Reached null position')
    
    # Go back to starting position when closed
    print('MSG - Moving back to initial position')
    move_abs_dl(dl_start, speed, opcua_motor)
    time.sleep(1.) # the DL overshoot, let it time to reach the targeted position
    print(' ')

save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/scipt/diagnostics/'
name_file = 'null_repeat_'+opcua_motor+'_speed_%s'%(speed)
db = {'repeat_null_flx':repeat_null_flx, 'repeat_null_pos':repeat_null_pos,\
      'gd_params':gd_params,\
        'scans_forth_pos':scans_forth_pos, 'scans_forth':scans_forth, \
      'scans_back_pos':scans_back_pos, 'scans_back':scans_back,\
        'targeted_pos':targeted_pos, 'repeat_reached_pos':repeat_reached_pos,
        'repeat_bck':repeat_bck}
save_data(db, save_path, name_file)

print('TODO - Close the plot(s) to continue')
plt.ioff()
plt.show()

# =============================================================================
# Intra-fringe scan (need global scan to work)
# =============================================================================
"""
This test checks the capability of the DL to perform a scan on a short range, typically
on a single fringe width.

It also commission the capability of the DL to reach a position via an absolute command
(unlike the previous test which use relative command to reach a position)
"""
plt.close('all')
plt.ioff()
plt.show()

print('\n*** Intra-fringe scan ***')
print('MSG - Global scan - The null position is:', null_pos[0])
# targeted_pos = null_scans_pos[0][np.argmin(null_scans[0])] # Use the minimum value of the scan
targeted_pos = null_pos[0] # Fitted value
# current_pos = read_current_pos(opcua_motor)
# print('MSG - Current position:', current_pos)
# print('MSG - Now moving to null position :', targeted_pos)
# move_abs_dl(targeted_pos/1000, speed, opcua_motor)

nb_fringes = 2 # Total number of fringes which are scanned
nb_pass = 5 # Even number for back and forth
wav = 3.8 # Wavelength in um
period = wav / 2 # The DL position is half the OPD
current_pos = read_current_pos(opcua_motor)
intrafringe_start = targeted_pos - period * nb_fringes
intrafringe_end = targeted_pos + period * nb_fringes
print('MSG - Move to start position:', intrafringe_start)
move_abs_dl(intrafringe_start/1000, speed, opcua_motor)

print('MSG - Start intra-fringe scan (%s - %s)'%(intrafringe_start, intrafringe_end))
rel_pos  = intrafringe_end - intrafringe_start
rel_pos /= 1000. # convert to mm
speed = rel_pos / 2.
delay = rel_pos/speed
print('MSG - Speed & Delay', speed, delay)
time.sleep(1.)

list_infrafringe_pos = []
list_infrafringe_flx = []
list_infrafringe_flx2 = []
list_infrafringe_params = []
list_intrafringe_bck = []

plt.figure(figsize=(15, 8))

for it in range(nb_pass):
    print('Pass', it+1, '/', nb_pass)
    move_rel_dl(rel_pos*(-1)**it, speed, opcua_motor)
    intrafringe_pos, intrafringe_flx, intrafringe_flx2, bck = grab_flux(delay, dl_name)
    list_infrafringe_pos.append(intrafringe_pos)
    list_infrafringe_flx.append(intrafringe_flx)
    list_infrafringe_flx2.append(intrafringe_flx2)
    list_intrafringe_bck.append(bck)

    init_guess   = [gd_params[0][0], gd_params[0][1], 0.95]
    lower_bounds = [0.99*init_guess[0], 0.99*init_guess[1], 0]
    upper_bounds = [1.01*init_guess[0], 1.01*init_guess[1], 1.9]
    try:
        params, _ = curve_fit(fringes, intrafringe_pos, intrafringe_flx, p0=init_guess, bounds=(lower_bounds, upper_bounds))
    except RuntimeError as e:
        print(e)
        params = init_guess
    list_infrafringe_params.append(params)
    flx_fit = fringes(intrafringe_pos, *params)

    if (-1)**it == 1:
        fig_id = 1
        fig_title = 'Forth'
    else:
        fig_id = 2
        fig_title = 'Back'
    plt.subplot(1, 3, fig_id)
    plt.plot(intrafringe_pos, intrafringe_flx)
    plt.plot(intrafringe_pos, flx_fit)
    plt.grid(True)
    plt.xlabel('DL pos (um)')
    plt.ylabel('Flux (count)')
    plt.title(fig_title)
    plt.subplot(1,3,3)
    plt.plot(intrafringe_pos, intrafringe_flx2)
    plt.grid(True)


# plt.ioff()
# plt.show()
print('MSG - Move to intra-fringe start position')
move_abs_dl(intrafringe_start/1000, speed, opcua_motor)

print('MSG - Finding the null by averaging the fits of the scans')
list_infrafringe_pos = list_infrafringe_pos[::2]
list_infrafringe_flx = list_infrafringe_flx[::2]
list_infrafringe_flx2 = list_infrafringe_flx2[::2]
list_infrafringe_params = list_infrafringe_params[::2]

x_axis = list_infrafringe_pos[0]
y = np.array([fringes(x_axis, *elt) for elt in list_infrafringe_params])
ymean = np.mean(y, 0) # Average over all the scans
intra_null_pos = x_axis[np.argmin(ymean)]

print('MSG - Null position is:', intra_null_pos)
plt.subplot(1, 3, 1)
plt.plot(intra_null_pos, 0., 's', markersize=16)
plt.subplot(1, 3, 2)
plt.plot(intra_null_pos, 0., 's', markersize=16)
plt.tight_layout()
plt.savefig('intrafringe_%s_speed_%s_nbfringe_%02d.png'%(opcua_motor, speed, nb_fringes), format='png', dpi=150)

plt.figure()
plt.plot(x_axis, y.T)
plt.plot(x_axis, ymean, c='k')
plt.grid()

print('\n*** Repeatedly Setting DL to NULL (absolute cmd) ***')

targeted_pos = intra_null_pos
repeat_null_flx = []
repeat_null_pos = []
repeat_reached_pos = []
repeat_bck = []
n_repeat = 10 # Even number for back and forth
grab_range = 0.08 / speed + 1

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15,8))
ax1.grid()
ax2.grid()

for k in range(n_repeat):
    # Go back to starting position when closed
    print('MSG - Moving back to initial position')
    move_abs_dl(intrafringe_start/1000, speed, opcua_motor)
    print(' ')

    print('Reaching null', k+1, '/', n_repeat)
    print('MSG - Now moving to null position :', targeted_pos)
    move_abs_dl(targeted_pos/1000, speed, opcua_motor)
    
    # Save the last move to check how precise the null is reached
    time.sleep(wait_time)
    to_null_pos, to_null_flx, to_null_flx2, bck = grab_flux(grab_range, dl_name)
    repeat_null_pos.append(to_null_pos)
    repeat_null_flx.append(to_null_flx2)
    reached_pos = read_current_pos(opcua_motor)
    print('MSG - Reached position', reached_pos)
    repeat_reached_pos.append(reached_pos)
    repeat_bck.append(bck)

    t_scale = np.linspace(-grab_range, 0., len(to_null_flx2))
    ax1.plot(t_scale, to_null_flx2)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Flux (count)')
    ax2.plot(to_null_pos, to_null_flx2)
    ax2.set_xlabel('DL pos (um)')
    ax2.set_ylabel('Flux (count)')
    fig.suptitle('Reached null position')

save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/scipt/diagnostics/'
name_file = 'intrafringe_absolute_'+opcua_motor+'_nbfringes_%02d'%(nb_fringes)
db = {'repeat_null_flx':repeat_null_flx, 'repeat_null_pos':repeat_null_pos,\
      'gd_params':gd_params, 'targeted_pos':targeted_pos,\
          'repeat_reached_pos':repeat_reached_pos,\
          'intrafringe_range':(intrafringe_start, intrafringe_end),\
            'list_infrafringe_pos':list_infrafringe_pos,\
            'list_infrafringe_flx':list_infrafringe_flx,\
            'list_infrafringe_flx2': list_infrafringe_flx2,
                'repeat_bck':repeat_bck, 'list_intrafringe_bck':list_intrafringe_bck}
save_data(db, save_path, name_file)

print('TODO - Close the plot(s) to continue')
plt.ioff()
plt.show()
print('MSG - Moving back to initial position')

# =============================================================================
# Intra-fringe scan with backlash (need global scan to work)
# =============================================================================
plt.close('all')
plt.ioff()
plt.show()

"""
This test checks the capability of the DL to perform a scan on a short range, typically
on a single fringe width.

It also commission the capability of the DL to reach a position via an absolute command
(unlike the previous test which use relative command to reach a position)
"""
print('\n*** Intra-fringe scan ***')
print('MSG - Global scan - The null position is:', null_pos[0])
# targeted_pos = null_scans_pos[0][np.argmin(null_scans[0])] # Use the minimum value of the scan
targeted_pos = null_pos[0] # Fitted value
# current_pos = read_current_pos(opcua_motor)
# print('MSG - Current position:', current_pos)
# print('MSG - Now moving to null position :', targeted_pos)
# move_abs_dl(targeted_pos/1000, speed, opcua_motor)

nb_fringes = 2 # Total number of fringes which are scanned
nb_pass = 5 # Even number for back and forth
wav = 3.8 # Wavelength in um
period = wav / 2 # The DL position is half the OPD
current_pos = read_current_pos(opcua_motor)
intrafringe_start = targeted_pos - period * nb_fringes - 5
intrafringe_end = targeted_pos + period * nb_fringes
print('MSG - Move to start position:', intrafringe_start)
move_abs_dl(intrafringe_start/1000, speed, opcua_motor)

print('MSG - Start intra-fringe scan (%s - %s)'%(intrafringe_start, intrafringe_end))
rel_pos  = intrafringe_end - intrafringe_start
rel_pos /= 1000. # convert to mm
speed = rel_pos / 2.
delay = rel_pos/speed
print('MSG - Speed & Delay', speed, delay)
time.sleep(1.)

list_infrafringe_pos = []
list_infrafringe_flx = []
list_infrafringe_flx2 = []
list_infrafringe_params = []
list_intrafringe_bck = []

plt.figure(figsize=(15, 8))

for it in range(nb_pass):
    print('Pass', it+1, '/', nb_pass)
    move_rel_dl(rel_pos*(-1)**it, speed, opcua_motor)
    intrafringe_pos, intrafringe_flx, intrafringe_flx2, bck = grab_flux(delay, dl_name)
    list_infrafringe_pos.append(intrafringe_pos)
    list_infrafringe_flx.append(intrafringe_flx)
    list_infrafringe_flx2.append(intrafringe_flx2)
    list_intrafringe_bck.append(bck)

    init_guess   = [gd_params[0][0], gd_params[0][1], 0.95]
    lower_bounds = [0.99*init_guess[0], 0.99*init_guess[1], 0]
    upper_bounds = [1.01*init_guess[0], 1.01*init_guess[1], 1.9]
    try:
        params, _ = curve_fit(fringes, intrafringe_pos, intrafringe_flx, p0=init_guess, bounds=(lower_bounds, upper_bounds))
    except RuntimeError as e:
        print(e)
        params = init_guess
    list_infrafringe_params.append(params)
    flx_fit = fringes(intrafringe_pos, *params)

    if (-1)**it == 1:
        fig_id = 1
        fig_title = 'Forth'
    else:
        fig_id = 2
        fig_title = 'Back'
    plt.subplot(1, 3, fig_id)
    plt.plot(intrafringe_pos, intrafringe_flx)
    plt.plot(intrafringe_pos, flx_fit)
    plt.grid(True)
    plt.xlabel('DL pos (um)')
    plt.ylabel('Flux (count)')
    plt.title(fig_title)
    plt.subplot(1,3,3)
    plt.plot(intrafringe_pos, intrafringe_flx2)
    plt.grid(True)


# plt.ioff()
# plt.show()
print('MSG - Move to intra-fringe start position')
move_abs_dl(intrafringe_start/1000, speed, opcua_motor) # Make sure we remove backlash
move_abs_dl(intrafringe_start/1000, speed, opcua_motor)

print('MSG - Finding the null by averaging the fits of the scans')
list_infrafringe_pos = list_infrafringe_pos[::2]
list_infrafringe_flx = list_infrafringe_flx[::2]
list_infrafringe_flx2 = list_infrafringe_flx2[::2]
list_infrafringe_params = list_infrafringe_params[::2]

x_axis = list_infrafringe_pos[0]
y = np.array([fringes(x_axis, *elt) for elt in list_infrafringe_params])
ymean = np.mean(y, 0) # Average over all the scans
null_pos = x_axis[np.argmin(ymean)]

print('MSG - Null position is:', null_pos)
plt.subplot(1, 3, 1)
plt.plot(null_pos, 0., 's', markersize=16)
plt.subplot(1, 3, 2)
plt.plot(null_pos, 0., 's', markersize=16)
plt.tight_layout()
plt.savefig('intrafringe_backlash_%s_speed_%s_nbfringe_%02d.png'%(opcua_motor, speed, nb_fringes), format='png', dpi=150)

plt.figure()
plt.plot(x_axis, y.T)
plt.plot(x_axis, ymean, c='k')
plt.grid()

print('\n*** Repeatedly Setting DL to NULL (absolute cmd) ***')

targeted_pos = null_pos
repeat_null_flx = []
repeat_null_pos = []
repeat_reached_pos = []
repeat_bck = []
n_repeat = nb_pass # Even number for back and forth
grab_range = 0.08 / speed + 1

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15,8))
ax1.grid()
ax2.grid()

for k in range(n_repeat):
    # Go back to starting position when closed
    print('MSG - Moving back to initial position')
    move_abs_dl(intrafringe_start/1000, speed, opcua_motor)
    print(' ')

    print('Reaching null', k+1, '/', n_repeat)
    print('MSG - Now moving to null position :', targeted_pos)
    move_abs_dl(targeted_pos/1000, speed, opcua_motor)
    
    # Save the last move to check how precise the null is reached
    time.sleep(wait_time)
    to_null_pos, to_null_flx, to_null_flx2, bck = grab_flux(grab_range, dl_name)
    repeat_null_pos.append(to_null_pos)
    repeat_null_flx.append(to_null_flx2)
    reached_pos = read_current_pos(opcua_motor)
    print('MSG - Reached position', reached_pos)
    repeat_reached_pos.append(reached_pos)
    repeat_bck.append(bck)

    t_scale = np.linspace(-grab_range, 0., len(to_null_flx2))
    ax1.plot(t_scale, to_null_flx2)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Flux (count)')
    ax2.plot(to_null_pos, to_null_flx2)
    ax2.set_xlabel('DL pos (um)')
    ax2.set_ylabel('Flux (count)')
    fig.suptitle('Reached null position')

save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/scipt/diagnostics/'
name_file = 'intrafringe_absolute_'+opcua_motor+'_nbfringes_%02d'%(nb_fringes)
db = {'repeat_null_flx':repeat_null_flx, 'repeat_null_pos':repeat_null_pos,\
      'gd_params':gd_params, 'targeted_pos':targeted_pos,\
          'repeat_reached_pos':repeat_reached_pos,\
          'intrafringe_range':(intrafringe_start, intrafringe_end),\
            'list_infrafringe_pos':list_infrafringe_pos,\
            'list_infrafringe_flx':list_infrafringe_flx,\
            'list_infrafringe_flx2': list_infrafringe_flx2, 
              'repeat_bck':repeat_bck, 'list_intrafringe_bck':list_intrafringe_bck}
save_data(db, save_path, name_file)

print('TODO - Close the plot(s) to continue')
plt.ioff()
plt.show()
print('MSG - Moving back to initial position')
move_abs_dl(dl_start, 0.05, opcua_motor)