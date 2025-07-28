""" Module to scan the NOTT delay lines and search for fringes """
import sys

# Add the path to sys.path
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/lib/')
from nott_control import move_rel_dl, move_abs_dl, read_current_pos, shutter_close
from nott_database import get_field, get_data, grab_flux
from nott_figure import move_figure
from nott_file import save_data
from nott_fringes import fringes, fringes_env, envelop_detector

# Import functions
import time
#import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy.optimize import curve_fit

# Script parameters
# delay = 40.0 # s, window to consider when scanning the fringes

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
    func_to_fit = fringes_env
    ampl         = np.abs(np.max(flx_coh)-np.min(flx_coh))/2
    # init_guess   = [ampl, 1000*np.abs(np.max(dl_end)+np.min(dl_start))/2]
    # lower_bounds = [0.95*ampl, 1000*dl_start]
    # upper_bounds = [1.05*ampl, 1000*dl_end]
    init_guess   = [ampl, 1000*np.abs(np.max(dl_end)+np.min(dl_start))/2]
    lower_bounds = [0.95*ampl, 1000*min(dl_start,dl_end), 0.1]
    upper_bounds = [1.05*ampl, 1000*max(dl_start,dl_end), 0.3]
    params, params_cov = curve_fit(func_to_fit, pos_env, flx_env, p0=init_guess, bounds=(lower_bounds, upper_bounds))
    print('FIT GD - Minimum value and its position:', flx_coh.min(), dl_pos[np.argmin(flx_coh)])
    print('FIT GD - Fringes amplitude :', params[0])
    print('FIT GD - Group delay [microns]:', params[1])
    #print('FIT GD - Bandwidth [microns]:', params[2])
    gd_params.append(params)
   
    # Extract best-fit envelop
    pos_env = np.linspace(dl_pos.min(), dl_pos.max(), dl_pos.size*2+1)
    flx_env = func_to_fit(pos_env, *params)

    # Now fit fringes
    func_to_fit = fringes
    # init_guess   = [params[0], params[1], 0.95]
    # lower_bounds = [0.99*params[0], 0.99*params[1], 0]
    # upper_bounds = [1.01*params[0], 1.01*params[1], 1.9]
    init_guess   = [params[0], params[1], 0.95]
    lower_bounds = [0.999*params[0], 0.999*params[1], 0, 0.999*params[2]]
    upper_bounds = [1.001*params[0], 1.001*params[1], 1.9, 1.001*params[2]]
    params, params_cov = curve_fit(func_to_fit, dl_pos, flx_coh, p0=init_guess, bounds=(lower_bounds, upper_bounds))
    print('FIT PD - Fringes amplitude :', params[0])
    print('FIT PD - Group delay [microns]:', params[1])
    print('FIT PD - Phase delay [microns]:', params[2])
    #print('FIT PD - Bandwidth [microns]:', params[3])
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
save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/cophasing/'
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