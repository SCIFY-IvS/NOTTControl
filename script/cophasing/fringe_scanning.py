""" Module to scan the NOTT delay lines and search for fringes """
import sys

# Add the path to sys.path
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/lib/')
import nott_control
from nott_control import move_rel_dl, move_abs_dl, read_current_pos, shutter_close
from nott_figure import move_figure
from nott_file import save_data
from nott_fringes import fringes, fringes_env, envelop_detector

sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/calibration/')
import kappa_matrix

# Import functions
import time
#import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d

def synchronize_ts(arr1, arr2):

    f = interp1d(arr1[:,0], arr1[:,1], bounds_error=False, fill_value=arr1[:,1].mean(), kind='cubic')

    interp_value = f(arr2[:,0])

    interp_arr = np.vstack((arr2[:,0], interp_value))
    interp_arr = interp_arr.T

    return interp_arr

def sync_devices(delay, margin, wait_db, shutter_id, shutter_name, flux_id, n_aper):
    lag = None
    for k in range(10):
        print('Measure lag - attempt %s / 10'%(k+1))
        nott_control.all_shutters_close(n_aper)
        time.sleep(delay)
        tsp = time.time() * 1000
        nott_control.shutter_open(shutter_id)
        time.sleep(delay)
        nott_control.shutter_close(shutter_id)

        duration = delay + margin + wait_db
        time.sleep(wait_db)
        start, end = kappa_matrix.define_time2(duration)
        time.sleep(wait_db)

        flux = kappa_matrix.get_field2(flux_id, start, end, False)
        shutter = kappa_matrix.get_field2(shutter_name, start, end, False)
        rescaled_shutter = shutter[:,1]/shutter[:,1].max() * (flux[:,1].max()-flux[:,1].min()) + flux[:,1].min()

        figsz = 15
        labelsz = 16
        ticksz = labelsz*0.875
        plt.figure(figsize=(figsz, figsz/1.6))
        plt.plot((shutter[:,0] - tsp), rescaled_shutter, '.', label='Shutter status')
        plt.plot((flux[:,0] - tsp), flux[:,1], '.', label='Flux P1')
        plt.grid()
        plt.xlabel('Elapsed time (s)', size=labelsz)
        plt.ylabel('Output value', size=labelsz)
        plt.legend(loc='best', fontsize=labelsz)
        plt.xticks(size=ticksz)
        plt.yticks(size=ticksz)
        plt.tight_layout()

        print('Measure the delay between shutter status and flux then close the figure')
        plt.ioff()
        plt.show()

        lag = input('Enter the lag in millisecond, to add to the camera:\n')
        lag = float(lag)

        print('Control the value. Close the plot to continue')
        flux = kappa_matrix.get_field2(P1, start, end, False, lag)
        shutter = kappa_matrix.get_field2(shutter_name, start, end, False)
        rescaled_shutter = shutter[:,1]/shutter[:,1].max() * (flux[:,1].max()-flux[:,1].min()) + flux[:,1].min()
        plt.figure(figsize=(figsz, figsz/1.6))
        plt.plot((shutter[:,0] - tsp)/1000, rescaled_shutter, '.', label='Shutter status')
        plt.plot((flux[:,0] - tsp)/1000, flux[:,1], '.', label='Flux P1')
        plt.grid()
        plt.xlabel('Elapsed time (s)', size=labelsz)
        plt.ylabel('Output value', size=labelsz)
        plt.legend(loc='best', fontsize=labelsz)
        plt.xticks(size=ticksz)
        plt.yticks(size=ticksz)
        plt.title('Redis data', size=labelsz*1.05)
        plt.tight_layout()
        plt.ioff()
        plt.show()

        answer = input('Is the lag correct? (y/n)\n')
        if answer.lower() == 'y':
            break
        else:
            pass

    nott_control.all_shutters_open(n_aper)
    return lag

# Script parameters
# delay = 40.0 # s, window to consider when scanning the fringes

P1='roi1_avg' # define all the ROI output
P2='roi2_avg'
I1='roi3_avg'
I2='roi4_avg'
I3='roi5_avg'
I4='roi6_avg'
P3='roi7_avg'
P4='roi8_avg'
detbg='roi9_avg'
return_avg_ts = False

# Loop over DL scanning iteration
dl_id = 0#4
speed = 0.02 #mm/s
wait_time = 0.08 / speed * 3 # Time in sec to scan X times the coherent envelope
grab_range = 0.08 / speed * 8 # Time in sec to scan X times the coherent envelope

if dl_id == 4:
    opcua_motor = 'nott_ics.Delay_Lines.NDL4'
    dl_name = 'DL_4_pos'
    ref_dl_name = 'nott_ics.Delay_Lines.NDL3'
    dl_start = 5.97 # mm
    dl_end   = 6.12 # mm
    dl_init_pos = 2. # mm
    fields_of_interest = [P3, P4, I4, I3, I2, detbg]
    shutter_id = '1'
    shutter_name = 'Shutter 1_pos'
elif dl_id == 3:
    opcua_motor = 'nott_ics.Delay_Lines.NDL3'
    dl_name = 'DL_3_pos'
    ref_dl_name = 'nott_ics.Delay_Lines.NDL4'
    dl_start = 1.875 # mm
    dl_end   = 2.025 # mm
    dl_init_pos = 6. # mm
    fields_of_interest = [P3, P4, I4, I3, I2, detbg]
    shutter_id = '1'
    shutter_name = 'Shutter 1_pos'
elif dl_id == 2:
    opcua_motor = 'nott_ics.Delay_Lines.NDL2'
    dl_name = 'DL_2_pos'
    ref_dl_name = 'nott_ics.Delay_Lines.NDL1'
    dl_start = 1.8#0.9 # mm
    dl_end   = 2.1#1.1 # mm
    dl_init_pos = 1.68 # mm
    fields_of_interest = [P1, P2, I1, I2, I3, detbg]
    shutter_id = '1'
    shutter_name = 'Shutter 1_pos'
elif dl_id == 1:
    opcua_motor = 'nott_ics.Delay_Lines.NDL1'
    dl_name = 'DL_1_pos'
    ref_dl_name = 'nott_ics.Delay_Lines.NDL2'
    dl_start = 1.55 # mm
    dl_end   = 1.82 # mm
    dl_init_pos = 1. # mm
    fields_of_interest = [P1, P2, I1, I2, I3, detbg]
    shutter_id = '1'
    shutter_name = 'Shutter 1_pos'
elif dl_id == 0:
    opcua_motor = 'nott_ics.Delay_Lines.NDL3'
    dl_name = 'DL_3_pos'
    ref_dl_name = 'nott_ics.Delay_Lines.NDL2'
    dl_start = 1.85 # mm
    dl_end   = 2.05 # mm
    dl_init_pos = 2. # mm
    fields_of_interest = [I1, I2, I1, I2, I3, detbg]
    shutter_id = '3'
    shutter_name = 'Shutter 3_pos'    

move_abs_dl(dl_init_pos, speed, ref_dl_name) # Move ref DL to its reference position     

# Loop over DL scans
rel_pos  = dl_end - dl_start
margin = 1
delay = abs(rel_pos)/speed + margin
n_pass = 10 # even number=back and forth
null_pos = np.array(range(n_pass), dtype=float)
wait_db = 0.1
n_aper = 4

# =============================================================================
# Measure lag
# =============================================================================
"""
There is a lag between the timestamps of the opto-mechanics and the camera.
We visually correct for it before performing the test.
"""
# lag = sync_devices(2., 0.5, wait_db, shutter_id, shutter_name, fields_of_interest[0], n_aper)
# input('Put the filter back on the source. Then enter anything to continue\n')
lag = 0.

# =============================================================================
# Global scan
# =============================================================================
"""
Here we check the ability of the DL to perform global scan, find the null and reach it.
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

# # Wait for the other delay lines to reach its position
# wait_time = 3. # in second
# print('Wait for the other delay lines to reach its position (%s sec)'%(wait_time))
# time.sleep(wait_time)

# Set DL to initial position
print('MSG - Move DL to initial position:', )
move_abs_dl(dl_start, speed, opcua_motor)



null_scans = []
null_scans_pos = []
null_scans_best_pos = []
nb_back_forth = n_pass // 2
gd_params = []

for it in range(n_pass):
    print('MSG - Pass', it+1, '/', n_pass)
    # Current DL positoin
    cur_pos = dl_start + rel_pos*(-1)**(it)

    # Send DL comment
    move_rel_dl(rel_pos*(-1)**it, speed, opcua_motor)  # Will go back and forth

    # Get data
    time.sleep(wait_db)
    start, end = kappa_matrix.define_time2(delay)
    time.sleep(wait_db)
    data_IA = kappa_matrix.get_field2(fields_of_interest[2], start, end, return_avg_ts, lag) # Output of the first stage coupler
    dl_pos0 = kappa_matrix.get_field2(dl_name, start, end, return_avg_ts)
    
    dl_pos = synchronize_ts(dl_pos0, data_IA)
    data_IA = data_IA[:,1]
    dl_pos = dl_pos[:,1]

    # Rearrange
    idx = np.argsort(dl_pos)
    data_IA = data_IA[idx]
    dl_pos = dl_pos[idx]

    # Remove offset structures on the 1st stage output
    popt = np.polyfit(dl_pos, data_IA, 3) # We fit a polynom of degree 3
    flx_coh = data_IA - np.poly1d(popt)(dl_pos)

    # Save dl_pos and coherent flux
    null_scans.append(flx_coh)
    null_scans_pos.append(dl_pos)

    # Find enveloppe
    flx_env = envelop_detector(flx_coh)

    # Fit group delay to enveloppe
    func_to_fit = fringes_env
    ampl         = np.abs(np.max(flx_coh)-np.min(flx_coh))/2
    init_guess   = [ampl, 1000*np.abs(np.max(dl_end)+np.min(dl_start))/2]
    lower_bounds = [0.95*ampl, 1000*min(dl_start,dl_end)]
    upper_bounds = [1.05*ampl, 1000*max(dl_start,dl_end)]
    params, params_cov = curve_fit(func_to_fit, dl_pos, flx_env, p0=init_guess, bounds=(lower_bounds, upper_bounds))
    print('FIT GD - Maximum value and its position:', flx_coh.max(), dl_pos[np.argmax(flx_coh)])
    print('FIT GD - Fringes amplitude :', params[0])
    print('FIT GD - Group delay [microns]:', params[1])
    gd_params.append(params)
   
    # Extract best-fit envelop
    pos_env = np.linspace(dl_pos.min(), dl_pos.max(), dl_pos.size*2+1)
    flx_env = func_to_fit(pos_env, *params)

    # Now fit fringes
    func_to_fit = fringes
    init_guess   = [params[0], params[1], 0.]
    lower_bounds = [0.999*params[0], params[1]-3.8/4, -3.8/4]
    upper_bounds = [1.001*params[0], params[1]+3.8/4, 3.8/4]
    params, params_cov = curve_fit(func_to_fit, dl_pos, flx_coh, p0=init_guess, bounds=(lower_bounds, upper_bounds))
    print('FIT PD - Fringes amplitude :', params[0])
    print('FIT PD - Group delay [microns]:', params[1])
    print('FIT PD - Phase delay [microns]:', params[2])
    
    # Extract fitted curve
    pos_fit = np.linspace(dl_pos.min(), dl_pos.max(), dl_pos.size*2+1)
    flx_fit = func_to_fit(pos_fit, *params)

    # Find best position
    # We look at the bright output of the coupler
    idx_null = np.argmax(flx_fit) 
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
        fig1.suptitle('Forward direction - Best null pos: %.5f'%(null_scans_best_pos[-1]))
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
        line_t4 = ax1_t1.axvline(null_scans_best_pos[-1], y_min - margin, y_max + margin, 
                                 color='magenta', label='Best null')
        ax1_t1.legend(loc='best')

        line_t3, = ax1_t2.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
        line_t2, = ax1_t2.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
        line_t1, = ax1_t2.plot(dl_pos, flx_coh, label='Fringes')
        line_t4 = ax1_t2.axvline(null_scans_best_pos[-1], y_min - margin, y_max + margin, 
                                 color='magenta', label='Best null')
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
        line_t4 = ax2_t1.axvline(null_scans_best_pos[-1], y_min - margin, y_max + margin, 
                                 color='magenta', label='Best null')
        ax2_t1.legend(loc='best')

        line_t3, = ax2_t2.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
        line_t2, = ax2_t2.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
        line_t1, = ax2_t2.plot(dl_pos, flx_coh, label='Fringes')
        line_t4 = ax2_t2.axvline(null_scans_best_pos[-1], y_min - margin, y_max + margin, 
                                 color='magenta', label='Best null')

    plt.draw()
    plt.tight_layout()
    plt.pause(0.5)
    # time.sleep(np.random.uniform(0.05, 2.))

print('MSG - End of pass')


# =============================================================================
# Set DL to NULL
# =============================================================================
time.sleep(1.)
print('\n*** Set DL to NULL ***')
speed2 = speed
current_pos = read_current_pos(opcua_motor)
print('MSG - Current position:', current_pos)
print('MSG - Now moving to null position :', null_pos[0])
cmd_null = (null_pos[0] - current_pos)/1000
print('Sending command', cmd_null)
move_rel_dl(cmd_null, speed2, opcua_motor)
# Save the last move to check how precise the null is reached
time.sleep(wait_time)
start, end = kappa_matrix.define_time2(grab_range)
time.sleep(wait_db)
to_null_pos = kappa_matrix.get_field2(dl_name, start, end, return_avg_ts)[:,1]
to_null_flx = kappa_matrix.get_field2(fields_of_interest[2], start, end, return_avg_ts, lag)
current_null_pos = read_current_pos(opcua_motor)
print('MSG - Reached position', current_pos)
print('MSG - Gap position', read_current_pos(opcua_motor) - null_pos[0])

plt.figure()
t_scale = to_null_flx[:,0] - to_null_flx[:,0].max()
to_null_flx = to_null_flx[:,1]
plt.plot(t_scale, to_null_flx)
plt.grid()
plt.xlabel('Time (s)')
plt.ylabel('Flux (count)')
plt.title('Reached null position: %.5f\nTargeted position: %.5f'%(read_current_pos(opcua_motor), null_pos[0]))

line_t5 = ax1_t1.axvline(read_current_pos(opcua_motor), y_min - margin, y_max + margin, 
                         ls='--', color='magenta', label='Final position')
line_t5 = ax1_t2.axvline(read_current_pos(opcua_motor), y_min - margin, y_max + margin, 
                         ls='--', color='magenta', label='Final position')
ax1_t1.legend(loc='best')
line_t5 = ax2_t1.axvline(read_current_pos(opcua_motor), y_min - margin, y_max + margin, 
                         ls='--', color='magenta', label='Final position')
line_t5 = ax2_t2.axvline(read_current_pos(opcua_motor), y_min - margin, y_max + margin, 
                         ls='--', color='magenta', label='Final position')
ax2_t1.legend(loc='best')

print('TODO - Close the plot(s) to continue')
# plt.ioff()
# plt.show()

# Go back to starting position when closed
print('MSG - Moving back to initial position')
move_abs_dl(dl_start, speed, opcua_motor)
time.sleep(1.) # the DL overshoot, let it time to reach the targeted position

# =============================================================================
# Set DL to average NULL position
# =============================================================================
print('\n*** Set DL to average NULL position ***')
null_scans_best_pos = np.array(null_scans_best_pos)
null_scans_best_pos = np.reshape(null_scans_best_pos, (-1, 2))
null_scans_best_pos = null_scans_best_pos.T

avg_null_pos = np.mean(null_scans_best_pos[0])
current_pos = read_current_pos(opcua_motor)
print('MSG - Mean, std, median, mini, maxi of forward null depth')
print(avg_null_pos, np.std(null_scans_best_pos[0]), np.median(null_scans_best_pos[0]), np.min(null_scans_best_pos[0]), np.max(null_scans_best_pos[0]))
print('MSG - Current position:', current_pos)
print('MSG - Now moving to null position :', avg_null_pos)
cmd_pos = (avg_null_pos - current_pos)/1000
print('MSG - Sending command', cmd_pos)
move_rel_dl(cmd_pos, speed2, opcua_motor)
# Save the last move to check how precise the null is reached
time.sleep(wait_time)
start, end = kappa_matrix.define_time2(grab_range)
time.sleep(wait_db)
to_null_pos_avg = kappa_matrix.get_field2(dl_name, start, end, return_avg_ts)[:,1]
to_null_flx_avg = kappa_matrix.get_field2(fields_of_interest[2], start, end, return_avg_ts, lag)[:,1]
current_null_pos_avg = read_current_pos(opcua_motor)
print('MSG - Reached position', current_null_pos_avg)
print('MSG - Gap position', read_current_pos(opcua_motor) - null_pos[0])

plt.figure(figsize=(10, 5))
plt.subplot(121)
plt.plot(to_null_flx)
plt.grid()
plt.xlabel('Time (count)')
plt.ylabel('Flux (count)')
plt.title('Reached null position 1st scan\n (%.5f, %.5f)'%(null_pos[0], current_null_pos))
plt.subplot(122)
plt.plot(to_null_flx_avg)
plt.grid()
plt.xlabel('Time (count)')
plt.ylabel('Flux (count)')
plt.title('Reached null position average strategy\n (%.5f, %.5f)'%(avg_null_pos, current_null_pos_avg))
plt.tight_layout()

print('TODO - Close the plot(s) to continue')
# plt.ioff()
# plt.show()

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
[plt.plot(scans_forth_pos[i], scans_forth[i]) for i in range(len(scans_forth))]
plt.grid()
plt.xlabel('DL pos (um)')
plt.ylabel('Flux (count)')
plt.legend(loc='best')
plt.subplot(212)
[plt.plot(scans_back_pos[i], scans_back[i]) for i in range(len(scans_back))]
plt.grid()
plt.xlabel('DL pos (um)')
plt.ylabel('Flux (count)')
plt.legend(loc='best')
plt.tight_layout()

print('TODO - Close the plot(s) to continue')
plt.ioff()
plt.show()

# Save the data
save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/cophasing/'
name_file = 'null_scans_'+dl_name+'_speed_%s'%(speed)
db = {'scans_forth_pos':scans_forth_pos, 'scans_forth':scans_forth, \
      'scans_back_pos':scans_back_pos, 'scans_back':scans_back,\
        'null_scans_best_pos': null_scans_best_pos,\
            'to_null':[to_null_pos, to_null_flx],\
                 'to_null_avg':[to_null_pos_avg, to_null_flx_avg]}

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
repeat_null_pos2 = []
repeat_reached_pos = []
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
    start, end = kappa_matrix.define_time2(grab_range)
    to_null_pos = kappa_matrix.get_field2(dl_name, start, end, return_avg_ts)
    to_null_flx = kappa_matrix.get_field2(fields_of_interest[2], start, end, return_avg_ts, lag)
    to_null_pos2 = synchronize_ts(to_null_pos, to_null_flx)
    to_null_pos = to_null_pos[:,1]
    to_null_flx = to_null_flx[:,1]
    to_null_pos2 = to_null_pos2[:,1]

    repeat_null_pos.append(to_null_pos)
    repeat_null_flx.append(to_null_flx)
    repeat_null_pos2.append(to_null_pos2)
    reached_pos = read_current_pos(opcua_motor)
    print('MSG - Reached position', reached_pos)
    repeat_reached_pos.append(reached_pos)
    print('MSG - Gap position', read_current_pos(opcua_motor) - null_pos[0])

    t_scale = np.linspace(-grab_range, 0., len(to_null_flx))
    ax1.plot(t_scale, to_null_flx)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Flux (count)')
    ax2.plot(to_null_pos2, to_null_flx)
    ax2.set_xlabel('DL pos (um)')
    ax2.set_ylabel('Flux (count)')
    fig.suptitle('Reached null position')
    
    # Go back to starting position when closed
    print('MSG - Moving back to initial position')
    move_abs_dl(dl_start, speed, opcua_motor)
    time.sleep(1.) # the DL overshoot, let it time to reach the targeted position
    print(' ')

save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/cophasing/'
name_file = 'null_repeat_'+dl_name+'_speed_%s'%(speed)
db = {'repeat_null_flx':repeat_null_flx, 'repeat_null_pos':repeat_null_pos,\
      'gd_params':gd_params,\
        'scans_forth_pos':scans_forth_pos, 'scans_forth':scans_forth, \
      'scans_back_pos':scans_back_pos, 'scans_back':scans_back,\
        'targeted_pos':targeted_pos, 'repeat_reached_pos':repeat_reached_pos,
        'repeat_null_pos2':repeat_null_pos2}
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

save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/cophasing/'
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
nb_pass = 10 # Even number for back and forth
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

save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/cophasing/'
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