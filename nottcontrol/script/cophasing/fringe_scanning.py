""" Module to scan the NOTT delay lines and search for fringes """
import sys

# Add the path to sys.path
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/lib/')
import nott_control
from nott_control import move_abs_dl, read_current_pos, shutter_close
from nott_figure import move_figure
from nott_file import save_data
from nott_fringes import fringes, fringes_env, envelop_detector
from nott_database import define_time, get_field

# Import functions
import time
#import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from configparser import ConfigParser
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d

def interpolate_ts(arr1, arr2):

    f = interp1d(arr1[:,0], arr1[:,1], bounds_error=False, fill_value=arr1[:,1].mean(), kind='cubic')

    interp_value = f(arr2[:,0])

    interp_arr = np.vstack((arr2[:,0], interp_value))
    interp_arr = interp_arr.T

    return interp_arr

def do_scans(dl_name, dl_end_pos, speed, opcua_motor, field_of_interest, delay, 
             return_avg_ts, wait_db, dl_start, dl_end, wav, pos_offset, revert_ts):

    move_abs_dl(dl_end_pos, speed, opcua_motor, pos_offset)

    # Get data
    time.sleep(wait_db)
    start, end = define_time(delay)
    time.sleep(wait_db)
    data_IA = get_field(field_of_interest, start, end, return_avg_ts) # Output of the first stage coupler
    dl_pos0 = get_field(dl_name, start, end, return_avg_ts)

    if revert_ts:
        data_IA = data_IA[::-1]
        dl_pos0 = dl_pos0[::-1]
    
    dl_pos = interpolate_ts(dl_pos0, data_IA)
    data_IA = data_IA[:,1]
    dl_pos = dl_pos[:,1]

    # Rearrange
    idx = np.argsort(dl_pos)
    data_IA = data_IA[idx]
    dl_pos = dl_pos[idx]

    # Remove offset structures on the 1st stage output
    popt = np.polyfit(dl_pos, data_IA, 3) # We fit a polynom of degree 3
    flx_coh = data_IA - np.poly1d(popt)(dl_pos)

    # Find enveloppe
    flx_env = envelop_detector(flx_coh)

    # Fit group delay to enveloppe
    func_to_fit = fringes_env
    ampl         = np.abs(np.max(flx_coh)-np.min(flx_coh))/2
    init_guess   = [ampl, 1000*(min(dl_start,dl_end)+max(dl_start,dl_end))/2.]
    # init_guess   = [ampl, dl_pos[np.argmax(flx_coh)]]
    lower_bounds = [0.95*ampl, 1000*min(dl_start,dl_end)]
    upper_bounds = [1.05*ampl, 1000*max(dl_start,dl_end)]
    gdparams, params_cov = curve_fit(func_to_fit, dl_pos, flx_env, p0=init_guess, bounds=(lower_bounds, upper_bounds))
    print('FIT GD - Maximum value and its position:', flx_coh.max(), dl_pos[np.argmax(flx_coh)])
    print('FIT GD - Fringes amplitude :', gdparams[0])
    print('FIT GD - Group delay [microns]:', gdparams[1])
   
    # Extract best-fit envelop
    pos_env = np.linspace(dl_pos.min(), dl_pos.max(), dl_pos.size*2+1)
    flx_env = func_to_fit(pos_env, *gdparams)

    # Now fit fringes
    func_to_fit = fringes
    init_guess   = [gdparams[0], gdparams[1], 0.]
    lower_bounds = [0.999*gdparams[0], gdparams[1]-wav/4, -wav/4] # range of 1 fringe so +/- half fringe which means 1/*4 of fringes in DL range
    upper_bounds = [1.001*gdparams[0], gdparams[1]+wav/4, wav/4] # range of 1 fringe so +/- half fringe which means 1/*4 of fringes in DL range
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
    print('RESULT - Position of the null :', pos_fit[idx_null])

    fit_data = [pos_env, flx_env, pos_fit, flx_fit]
    return pos_fit[idx_null], flx_coh, dl_pos, gdparams, fit_data

def set_dl_to_null(null_singlepass, opcua_motor, speed2, grab_range, dl_name, return_avg_ts, pos_offset, field_of_interest):
    """
    null_singlepass in um
    """
    current_pos = read_current_pos(opcua_motor) * 1000 # convert in um
    print('MSG - Current position:', current_pos)
    print('MSG - Now moving to null position :', null_singlepass)
    move_abs_dl(null_singlepass/1000, speed2, opcua_motor, pos_offset)
    # Save the last move to check how precise the null is reached
    time.sleep(wait_time)
    start, end = define_time(grab_range)
    time.sleep(wait_db)
    to_null_pos = get_field(dl_name, start, end, return_avg_ts) # we only keep the position
    to_null_flx = get_field(field_of_interest, start, end, return_avg_ts) # we keep both timestamp (in ms) and flux
    current_null_pos = read_current_pos(opcua_motor) * 1000 # convert in um
    print('MSG - Reached position', current_null_pos)
    print('MSG - Gap position', current_null_pos - null_singlepass)
    
    return to_null_pos, to_null_flx, current_null_pos

# Read config file
config = ConfigParser()
config.read('../cfg/config.cfg')

plt.ion()

# Read config file
config = configparser.ConfigParser()
config.read('../cfg/config.cfg')


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
wav = 3.8 # in un

# Loop over DL scanning iteration
dl_id = 1#4
speed = config['cophasing']['dl_speed'] #mm/s
speed0 = speed
wait_time = 0.08 / speed * 2 # Time in sec to scan X times the coherent envelope
grab_range = 0.08 / speed * 3 # Time in sec to scan X times the coherent envelope

pos_offset = 0.24 / 1000. # in mm

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
    dl_start = 2.9
    dl_end   = 3.1
    dl_init_pos = 3.7 # mm
    fields_of_interest = [P1, P2, I1, I2, I3, detbg]
    shutter_id = '1'
    shutter_name = 'Shutter 1_pos'
elif dl_id == 1:
    opcua_motor = 'nott_ics.Delay_Lines.NDL1'
    dl_name = 'DL_1_pos'
    ref_dl_name = 'nott_ics.Delay_Lines.NDL2'
    dl_start = 3.65 # mm
    dl_end   = 3.85 # mm
    dl_init_pos = 3. # mm
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
    fields_of_interest = [I1, I2, I2, I1, I3, detbg]
    shutter_id = '3'
    shutter_name = 'Shutter 3_pos'    

# move_abs_dl(dl_init_pos, speed, ref_dl_name, 0.) # Move ref DL to its reference position     

# Loop over DL scans
rel_pos  = dl_end - dl_start
margin = 1.
delay = abs(rel_pos)/speed + margin
n_pass = 2 # even number=back and forth
wait_db = 0.1
n_aper = 4
ymargin = 1.

# # =============================================================================
# # Global scan
# # =============================================================================
# """
# Here we check the ability of the DL to perform global scan and find the null or the bright fringe.
# Given the backlash, reaching a position is always made from the same direction.

# Two methods are tested:
#     - single pass then reach the null
#     - several pass and reach the average null
    
# Null position can be defined as:
#     - the minimum value of the flux during the scan
#     - minimum value given a fit of the envelope then a fit of the fringes
# It appears that none of these techniques accurately find the null, it will
# mostly lock on the bright fringe, sometimes on the null and sometimes on a partial fringe.
# The reason is not clear but it is the case for all the tests led with this script.

# """
# fig1, (ax1_t1, ax1_t2) = plt.subplots(2, 1, figsize=(8,5)) # Display scan forth
# move_figure(fig1, 0, 0)
# fig2, (ax2_t1, ax2_t2) = plt.subplots(2, 1, figsize=(8,5)) # Display scan back

# # Set DL to initial position
# print('MSG - Move DL to initial position:', )
# move_abs_dl(dl_start, speed, opcua_motor, pos_offset)

# null_scans = []
# null_scans_pos = []
# null_scans_best_pos = []
# nb_back_forth = n_pass // 2
# gd_params = []

# dl_bounds = [dl_end, dl_start]

# for it in range(n_pass):
#     print('MSG - Pass', it+1, '/', n_pass)
    
#     if it % 2 == 0: # Scan forward
#         revert_ts = False
#     else: # Scan backward
#         revert_ts = True

#     best_null_pos, flx_coh, dl_pos, params, fit_data = do_scans(dl_name, dl_bounds[it%2], speed, opcua_motor, fields_of_interest[2], delay, 
#                   return_avg_ts, wait_db, dl_start, dl_end, wav, pos_offset, revert_ts)
    
#     pos_env, flx_env, pos_fit, flx_fit = fit_data
#     null_scans_best_pos.append(best_null_pos)
#     gd_params.append(params)
#     null_scans.append(flx_coh)
#     null_scans_pos.append(dl_pos)    

#     # Adjust the axis range for time plot
#     x_min, x_max = np.min(1000*min(dl_start,dl_end)), np.max(1000*max(dl_start,dl_end)) 
#     marginx = 25

#     y_min, y_max = np.min(flx_coh), np.max(flx_coh) 
#     marginy = 0

#     if (it+1)%2 != 0:
#         # Clear the axes
#         ax1_t1.clear() 
#         fig1.suptitle('Forward direction - Best null pos: %.5f'%(best_null_pos))
#         ax1_t1.set_xlabel('DL position [microns]')
#         ax1_t1.set_ylabel('ROI value')
#         ax1_t2.clear() 
#         ax1_t2.set_xlabel('DL position [microns]')
#         ax1_t2.set_ylabel('ROI value')

#         # Set x and y dynamic ranges
#         ax1_t1.set_ylim(y_min - marginy, y_max + marginy)    
#         ax1_t2.set_ylim(y_min - marginy, y_max + marginy)    
#         ax1_t1.set_xlim(x_min - marginx, x_max + marginx)
#         ax1_t2.set_xlim(best_null_pos - marginx, best_null_pos + marginx)

#         # Plot curves
#         line_t3, = ax1_t1.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
#         line_t2, = ax1_t1.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
#         line_t1, = ax1_t1.plot(dl_pos, flx_coh, label='Fringes')
#         line_t4 = ax1_t1.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
#                                   color='magenta', label='Best null')
#         ax1_t1.legend(loc='best')

#         line_t3, = ax1_t2.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
#         line_t2, = ax1_t2.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
#         line_t1, = ax1_t2.plot(dl_pos, flx_coh, label='Fringes')
#         line_t4 = ax1_t2.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
#                                   color='magenta', label='Best null')
#     else:
#         # Clear the axes
#         fig2.suptitle('Back direction - Best null pos: %.5f'%(best_null_pos))
#         ax2_t1.clear() 
#         ax2_t1.set_xlabel('DL position [microns]')
#         ax2_t1.set_ylabel('ROI value')
#         ax2_t2.clear() 
#         ax2_t2.set_xlabel('DL position [microns]')
#         ax2_t2.set_ylabel('ROI value')
        
#         # Set x and y dynamic ranges
#         ax2_t1.set_ylim(y_min - marginy, y_max + marginy)    
#         ax2_t2.set_ylim(y_min - marginy, y_max + marginy)    
#         ax2_t1.set_xlim(x_min - marginx, x_max + marginx)
#         ax2_t2.set_xlim(best_null_pos - marginx, best_null_pos + marginx)

#         # Plot curves
#         line_t3, = ax2_t1.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
#         line_t2, = ax2_t1.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
#         line_t1, = ax2_t1.plot(dl_pos, flx_coh, label='Fringes')
#         line_t4 = ax2_t1.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
#                                   color='magenta', label='Best null')
#         ax2_t1.legend(loc='best')

#         line_t3, = ax2_t2.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
#         line_t2, = ax2_t2.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
#         line_t1, = ax2_t2.plot(dl_pos, flx_coh, label='Fringes')
#         line_t4 = ax2_t2.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
#                                   color='magenta', label='Best null')

#     plt.draw()
#     plt.tight_layout()
#     plt.pause(0.5)

# print('MSG - End of pass')
# # plt.ioff()
# # plt.show()

# # Show results of the scans, individual scan can have different numbers of points
# scans_forth = null_scans[::2]
# scans_forth_pos = null_scans_pos[::2]
# scans_back = null_scans[1::2]
# scans_back_pos = null_scans_pos[1::2]

# """
# This plot shows how repeatable a scan is
# """
# fig3, (ax31, ax32) = plt.subplots(2, 1, figsize=(8,5)) # Display scan forth
# ax31.set_title('Forward')
# [ax31.plot(scans_forth_pos[i], scans_forth[i]) for i in range(len(scans_forth))]
# ax31.grid()
# ax31.set_xlabel('DL pos (um)')
# ax31.set_ylabel('Flux (count)')
# ax32.set_title('Backward')
# [ax32.plot(scans_back_pos[i], scans_back[i]) for i in range(len(scans_back))]
# ax32.grid()
# ax32.set_xlabel('DL pos (um)')
# ax32.set_ylabel('Flux (count)')
# fig3.tight_layout()

# print('TODO - Close the plot(s) to continue')
# # plt.ioff()
# # plt.show()

# # =============================================================================
# # Set DL to NULL
# # =============================================================================
# time.sleep(1.)
# print('\n*** Set DL to NULL in FORWARD direction***')
# speed2 = speed
# null_singlepass = null_scans_best_pos[0]
# fwd_to_null_pos, fwd_to_null_flx0, fwd_current_null_pos = set_dl_to_null(null_singlepass, opcua_motor, speed2, grab_range, dl_name, return_avg_ts, pos_offset, fields_of_interest[2])

# plt.figure()
# t_scale = fwd_to_null_flx0[:,0] - fwd_to_null_flx0[:,0].max()
# fwd_to_null_flx = fwd_to_null_flx0[:,1]
# plt.plot(t_scale/1000, fwd_to_null_flx)
# plt.grid()
# plt.xlabel('Time (s)')
# plt.ylabel('Flux (count)')
# plt.title('FORWARD Reached null position: %.5f\nTargeted position: %.5f'%(fwd_current_null_pos, null_singlepass))

# ax31.axvline(fwd_current_null_pos, min([min(elt) for elt in scans_forth]) - margin, max([max(elt) for elt in scans_forth]) + margin, 
#                           ls='--', color='magenta', label='Final position forward single pass')

# print('TODO - Close the plot(s) to continue')
# # plt.ioff()
# # plt.show()

# # Go to end of range to reach the null from the other side
# print('MSG - Moving to end of range')
# move_abs_dl(dl_end, speed0, opcua_motor, pos_offset)
# time.sleep(1.) # the DL overshoot, let it time to reach the targeted position

# print('\n*** Set DL to NULL in BACKWARD direction***')
# # speed2 = speed
# null_singlepass = null_scans_best_pos[1]
# bcw_to_null_pos, bcw_to_null_flx0, bcw_current_null_pos = set_dl_to_null(null_singlepass, opcua_motor, speed2, grab_range, dl_name, return_avg_ts, pos_offset, fields_of_interest[2])

# plt.figure()
# t_scale = bcw_to_null_flx0[:,0] - bcw_to_null_flx0[:,0].max()
# bcw_to_null_flx = bcw_to_null_flx0[:,1]
# plt.plot(t_scale/1000, bcw_to_null_flx)
# plt.grid()
# plt.xlabel('Time (s)')
# plt.ylabel('Flux (count)')
# plt.title('BACKWARD Reached null position: %.5f\nTargeted position: %.5f'%(bcw_current_null_pos, null_singlepass))

# ax32.axvline(bcw_current_null_pos, min([min(elt) for elt in scans_back]) - margin, max([max(elt) for elt in scans_back]) + margin,
#                           ls='--', color='magenta', label='Final position backward single pass')

# print('TODO - Close the plot(s) to continue')
# plt.ioff()
# plt.show()

# # Go back to starting position when closed
# print('MSG - Moving back to initial position')
# move_abs_dl(dl_start, speed0, opcua_motor, pos_offset)
# time.sleep(1.) # the DL overshoot, let it time to reach the targeted position

# # =============================================================================
# # Set DL to average NULL position
# # =============================================================================
# print('\n*** Set DL to average FORWARD NULL position ***')
# null_scans_best_pos = np.array(null_scans_best_pos)
# null_scans_best_pos = np.reshape(null_scans_best_pos, (-1, 2))
# null_scans_best_pos = null_scans_best_pos.T
# null_singlepass = null_scans_best_pos[0,0]
# fwd_avg_null_pos = np.median(null_scans_best_pos[0,:])
# print('MSG - Mean, std, median, mini, maxi of forward null depth')
# print(fwd_avg_null_pos, np.std(null_scans_best_pos[0]), np.median(null_scans_best_pos[0]), np.min(null_scans_best_pos[0]), np.max(null_scans_best_pos[0]))

# fwd_to_null_pos_avg, fwd_to_null_flx_avg0, fwd_current_null_pos_avg = set_dl_to_null(fwd_avg_null_pos, opcua_motor, speed2, grab_range, dl_name, return_avg_ts, pos_offset*0, fields_of_interest[2])

# plt.figure(figsize=(10, 5))
# t_scale = fwd_to_null_flx0[:,0] - fwd_to_null_flx0[:,0].max()
# fwd_to_null_flx = fwd_to_null_flx0[:,1]
# t_scale_avg = fwd_to_null_flx_avg0[:,0] - fwd_to_null_flx_avg0[:,0].max()
# fwd_to_null_flx_avg = fwd_to_null_flx_avg0[:,1]
# plt.subplot(121)
# plt.plot(t_scale/1000, fwd_to_null_flx)
# plt.grid()
# plt.xlabel('Time (s)')
# plt.ylabel('Flux (count)')
# plt.title('FORWARD Reached null position 1st scan\n (%.5f, %.5f)'%(null_singlepass, fwd_current_null_pos))
# plt.subplot(122)
# plt.plot(t_scale_avg/1000, fwd_to_null_flx_avg)
# plt.grid()
# plt.xlabel('Time (s)')
# plt.ylabel('Flux (count)')
# plt.title('FORWARD Reached null position average strategy\n (%.5f, %.5f)'%(fwd_avg_null_pos, fwd_current_null_pos_avg))
# plt.tight_layout()

# ax31.axvline(fwd_current_null_pos_avg, min([min(elt) for elt in scans_forth]) - margin, max([max(elt) for elt in scans_forth]) + margin,  
#                           ls='-', color='magenta', label='Final position forward average')

# print('TODO - Close the plot(s) to continue')
# # plt.ioff()
# # plt.show()

# # Go to end of range to reach the null from the other side
# print('MSG - Moving to end of range')
# move_abs_dl(dl_end, speed0, opcua_motor, pos_offset)
# time.sleep(1.) # the DL overshoot, let it time to reach the targeted position

# print('\n*** Set DL to average BACKWARD NULL position ***')
# null_singlepass = null_scans_best_pos[1,0]
# bcw_avg_null_pos = np.median(null_scans_best_pos[1,:])
# bcw_to_null_pos_avg, bcw_to_null_flx_avg0, bcw_current_null_pos_avg = set_dl_to_null(bcw_avg_null_pos, opcua_motor, speed2, grab_range, dl_name, return_avg_ts, pos_offset*0, fields_of_interest[2])

# plt.figure(figsize=(10, 5))
# t_scale = bcw_to_null_flx0[:,0] - bcw_to_null_flx0[:,0].max()
# bcw_to_null_flx = bcw_to_null_flx0[:,1]
# t_scale_avg = bcw_to_null_flx_avg0[:,0] - bcw_to_null_flx_avg0[:,0].max()
# bcw_to_null_flx_avg = bcw_to_null_flx_avg0[:,1]
# plt.subplot(121)
# plt.plot(t_scale/1000, bcw_to_null_flx)
# plt.grid()
# plt.xlabel('Time (s)')
# plt.ylabel('Flux (count)')
# plt.title('BACKWARD Reached null position 1st scan\n (%.5f, %.5f)'%(null_singlepass, bcw_current_null_pos))
# plt.subplot(122)
# plt.plot(t_scale_avg/1000, bcw_to_null_flx_avg)
# plt.grid()
# plt.xlabel('Time (s)')
# plt.ylabel('Flux (count)')
# plt.title('BACKWARD Reached null position average strategy\n (%.5f, %.5f)'%(bcw_avg_null_pos, bcw_current_null_pos_avg))
# plt.tight_layout()

# ax32.axvline(bcw_current_null_pos_avg, min([min(elt) for elt in scans_back]) - margin, max([max(elt) for elt in scans_back]) + margin, 
#                           ls='-', color='magenta', label='Final position backward average')

# ax31.legend(loc='best')
# ax32.legend(loc='best')
# fig3.tight_layout()

# # Save the data
# save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/cophasing/'
# name_file = 'null_scans_'+dl_name+'_speed_%s'%(speed)
# db = {'scans_forth_pos':scans_forth_pos, 'scans_forth':scans_forth,
#       'scans_back_pos':scans_back_pos, 'scans_back':scans_back,
#         'null_scans_best_pos': null_scans_best_pos,
#             'fwd_to_null':[fwd_to_null_pos, fwd_to_null_flx, fwd_to_null_flx0],
#                   'fwd_to_null_avg':[fwd_to_null_pos_avg, fwd_to_null_flx_avg, fwd_to_null_flx_avg0],
#                               'bcw_to_null':[bcw_to_null_pos, bcw_to_null_flx, bcw_to_null_flx0],
#                   'bcw_to_null_avg':[bcw_to_null_pos_avg, bcw_to_null_flx_avg, bcw_to_null_flx_avg0]}

# save_data(db, save_path, name_file)

# # Go to end of range to reach the null from the other side
# print('MSG - Moving to initial position')
# move_abs_dl(dl_start, speed0, opcua_motor, pos_offset)
# time.sleep(1.) # the DL overshoot, let it time to reach the targeted position

# print('TODO - Close the plot(s) to continue')
# plt.ioff()
# plt.show()

# # =============================================================================
# # Repeat DL location
# # =============================================================================
# """
# Here we qualify the ability of the DL to reach precisely and accurately a position given
# a relative move.
# """
# print('\n*** Repeatedly Setting DL to NULL ***')

# targeted_pos = null_scans_best_pos[0] # null_scans_pos[0][np.argmin(null_scans[0])]

# scans_forth = null_scans[::2]
# scans_forth_pos = null_scans_pos[::2]
# scans_back = null_scans[1::2]
# scans_back_pos = null_scans_pos[1::2]

# repeat_null_flx = []
# repeat_null_pos = []
# repeat_null_pos2 = []
# repeat_reached_pos = []
# n_repeat = 10

# fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10,5))
# ax1.grid()
# ax2.grid()

# for k in range(n_repeat):
#     print('Reaching null', k+1, '/', n_repeat)
#     current_pos = read_current_pos(opcua_motor) * 1000 # convert in um
#     print('MSG - Current position:', current_pos)
#     print('MSG - Now moving to null position :', targeted_pos)
#     cmd_null = (targeted_pos / 1000 - current_pos)
#     print('Sending command', cmd_null)
#     move_rel_dl(cmd_null, speed, opcua_motor)
    
#     # Save the last move to check how precise the null is reached
#     time.sleep(wait_time)
#     start, end = define_time(grab_range)
#     to_null_pos = get_field(dl_name, start, end, return_avg_ts)
#     to_null_flx = get_field(fields_of_interest[2], start, end, return_avg_ts)
#     to_null_pos2 = interpolate_ts(to_null_pos, to_null_flx)
#     to_null_pos = to_null_pos[:,1]
#     to_null_flx = to_null_flx[:,1]
#     to_null_pos2 = to_null_pos2[:,1]

#     repeat_null_pos.append(to_null_pos)
#     repeat_null_flx.append(to_null_flx)
#     repeat_null_pos2.append(to_null_pos2)
#     reached_pos = read_current_pos(opcua_motor) * 1000 # convert in um
#     print('MSG - Reached position', reached_pos)
#     repeat_reached_pos.append(reached_pos)
#     print('MSG - Gap position', reached_pos - null_scans_best_pos[0])

#     t_scale = np.linspace(-grab_range, 0., len(to_null_flx))
#     ax1.plot(t_scale, to_null_flx)
#     ax1.set_xlabel('Time (s)')
#     ax1.set_ylabel('Flux (count)')
#     ax2.plot(to_null_pos2, to_null_flx)
#     ax2.set_xlabel('DL pos (um)')
#     ax2.set_ylabel('Flux (count)')
#     fig.suptitle('Reached null position')
    
#     # Go back to starting position when closed
#     print('MSG - Moving back to initial position')
#     move_abs_dl(dl_start, speed, opcua_motor)
#     time.sleep(1.) # the DL overshoot, let it time to reach the targeted position
#     print(' ')

# save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/cophasing/'
# name_file = 'null_repeat_'+dl_name+'_speed_%s'%(speed)
# db = {'repeat_null_flx':repeat_null_flx, 'repeat_null_pos':repeat_null_pos,\
#       'gd_params':gd_params,\
#         'scans_forth_pos':scans_forth_pos, 'scans_forth':scans_forth, \
#       'scans_back_pos':scans_back_pos, 'scans_back':scans_back,\
#         'targeted_pos':targeted_pos, 'repeat_reached_pos':repeat_reached_pos,
#         'repeat_null_pos2':repeat_null_pos2}
# save_data(db, save_path, name_file)

# print('TODO - Close the plot(s) to continue')
# plt.ioff()
# plt.show()

# # =============================================================================
# # Intra-fringe scan (need global scan to work)
# # =============================================================================
# """
# This test checks the capability of the DL to perform a scan on a short range, typically
# on a single fringe width.

# It also commission the capability of the DL to reach a position via an absolute command
# (unlike the previous test which use relative command to reach a position)
# """
# plt.close('all')
# plt.ioff()
# plt.show()

# print('\n*** Intra-fringe scan ***')
# print('MSG - Global scan - The null position is:', null_scans_best_pos[0])
# # targeted_pos = null_scans_pos[0][np.argmin(null_scans[0])] # Use the minimum value of the scan
# targeted_pos = null_scans_best_pos[0] # Fitted value
# # current_pos = read_current_pos(opcua_motor) * 1000 # in um
# # print('MSG - Current position:', current_pos)
# # print('MSG - Now moving to null position :', targeted_pos)
# # move_abs_dl(targeted_pos/1000, speed, opcua_motor)

# nb_fringes = 2 # Total number of fringes which are scanned
# nb_pass = 5 # Even number for back and forth
# wav = 3.8 # Wavelength in um
# period = wav / 2 # The DL position is half the OPD
# current_pos = read_current_pos(opcua_motor) * 1000
# intrafringe_start = targeted_pos - period * nb_fringes
# intrafringe_end = targeted_pos + period * nb_fringes
# print('MSG - Move to start position:', intrafringe_start)
# move_abs_dl(intrafringe_start/1000, speed, opcua_motor)

# print('MSG - Start intra-fringe scan (%s - %s)'%(intrafringe_start, intrafringe_end))
# rel_pos  = intrafringe_end - intrafringe_start
# rel_pos /= 1000. # convert to mm
# speed = rel_pos / 2.
# delay = rel_pos/speed
# print('MSG - Speed & Delay', speed, delay)
# time.sleep(1.)

# list_infrafringe_pos = []
# list_infrafringe_flx = []
# list_infrafringe_flx2 = []
# list_infrafringe_params = []
# list_intrafringe_bck = []

# plt.figure(figsize=(15, 8))

# for it in range(nb_pass):
#     print('Pass', it+1, '/', nb_pass)
#     move_rel_dl(rel_pos*(-1)**it, speed, opcua_motor)

#     time.sleep(wait_db)
#     start, end = define_time(delay)
#     time.sleep(wait_db)
#     intrafringe_flx = get_field(fields_of_interest[2], start, end, return_avg_ts)    
#     intrafringe_pos = get_field(dl_name, start, end, return_avg_ts)
#     intrafringe_flx = intrafringe_flx[:,1]
#     intrafringe_pos = intrafringe_pos[:,1]

#     # Rearrange
#     idx = np.argsort(intrafringe_pos)
#     intrafringe_flx = intrafringe_flx[idx]
#     intrafringe_pos = intrafringe_pos[idx]

#     # Remove offset structures on the 1st stage output
#     popt = np.polyfit(dl_pos, data_IA, 3) # We fit a polynom of degree 3
#     intrafringe_flx2 = intrafringe_flx - np.poly1d(popt)(intrafringe_pos)

#     to_null_pos = get_field(dl_name, start, end, return_avg_ts)
#     to_null_flx = get_field(fields_of_interest[2], start, end, return_avg_ts)
#     to_null_pos = to_null_pos[:,1]
#     to_null_flx = to_null_flx[:,1]

#     list_infrafringe_pos.append(intrafringe_pos)
#     list_infrafringe_flx.append(intrafringe_flx)
#     list_infrafringe_flx2.append(intrafringe_flx2)

#     init_guess   = [gd_params[0][0], gd_params[0][1], 0.95]
#     lower_bounds = [0.999*params[0], params[1]-wav/4, -wav/4] # range of 1 fringe so +/- half fringe which means 1/*4 of fringes in DL range
#     upper_bounds = [1.001*params[0], params[1]+wav/4, wav/4] # range of 1 fringe so +/- half fringe which means 1/*4 of fringes in DL range  
#     try:
#         params, _ = curve_fit(fringes, intrafringe_pos, intrafringe_flx2, p0=init_guess, bounds=(lower_bounds, upper_bounds))
#     except RuntimeError as e:
#         print(e)
#         params = init_guess
#     list_infrafringe_params.append(params)
#     flx_fit = fringes(intrafringe_pos, *params)

#     if (-1)**it == 1:
#         fig_id = 1
#         fig_title = 'Forth'
#     else:
#         fig_id = 2
#         fig_title = 'Back'
#     plt.subplot(1, 3, fig_id)
#     plt.plot(intrafringe_pos, intrafringe_flx)
#     plt.plot(intrafringe_pos, flx_fit)
#     plt.grid(True)
#     plt.xlabel('DL pos (um)')
#     plt.ylabel('Flux (count)')
#     plt.title(fig_title)
#     plt.subplot(1,3,3)
#     plt.plot(intrafringe_pos, intrafringe_flx2)
#     plt.grid(True)


# # plt.ioff()
# # plt.show()
# print('MSG - Move to intra-fringe start position')
# move_abs_dl(intrafringe_start/1000, speed, opcua_motor)

# print('MSG - Finding the null by averaging the fits of the scans')
# list_infrafringe_pos = list_infrafringe_pos[::2]
# list_infrafringe_flx = list_infrafringe_flx[::2]
# list_infrafringe_flx2 = list_infrafringe_flx2[::2]
# list_infrafringe_params = list_infrafringe_params[::2]

# x_axis = list_infrafringe_pos[0]
# y = np.array([fringes(x_axis, *elt) for elt in list_infrafringe_params])
# ymean = np.mean(y, 0) # Average over all the scans
# intra_null_pos = x_axis[np.argmin(ymean)]

# print('MSG - Null position is:', intra_null_pos)
# plt.subplot(1, 3, 1)
# plt.plot(intra_null_pos, 0., 's', markersize=16)
# plt.subplot(1, 3, 2)
# plt.plot(intra_null_pos, 0., 's', markersize=16)
# plt.tight_layout()
# plt.savefig(save_path+'intrafringe_%s_speed_%s_nbfringe_%02d.png'%(opcua_motor, speed, nb_fringes), format='png', dpi=150)

# plt.figure()
# plt.plot(x_axis, y.T)
# plt.plot(x_axis, ymean, c='k')
# plt.grid()

# print('\n*** Repeatedly Setting DL to NULL (absolute cmd) ***')

# targeted_pos = intra_null_pos
# repeat_null_flx = []
# repeat_null_pos = []
# repeat_reached_pos = []
# repeat_bck = []
# n_repeat = 10 # Even number for back and forth
# grab_range = 0.08 / speed + 1

# fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15,8))
# ax1.grid()
# ax2.grid()

# for k in range(n_repeat):
#     # Go back to starting position when closed
#     print('MSG - Moving back to initial position')
#     move_abs_dl(intrafringe_start/1000, speed, opcua_motor)
#     print(' ')

#     print('Reaching null', k+1, '/', n_repeat)
#     print('MSG - Now moving to null position :', targeted_pos)
#     move_abs_dl(targeted_pos/1000, speed, opcua_motor)
    
#     # Save the last move to check how precise the null is reached
#     time.sleep(wait_db)
#     start, end = define_time(delay)
#     time.sleep(wait_db)
#     intrafringe_flx = get_field(fields_of_interest[2], start, end, return_avg_ts)    
#     intrafringe_pos = get_field(dl_name, start, end, return_avg_ts)
#     intrafringe_flx = intrafringe_flx[:,1]
#     intrafringe_pos = intrafringe_pos[:,1]

#     # Rearrange
#     idx = np.argsort(intrafringe_pos)
#     intrafringe_flx = intrafringe_flx[idx]
#     intrafringe_pos = intrafringe_pos[idx]

#     # Remove offset structures on the 1st stage output
#     popt = np.polyfit(dl_pos, data_IA, 3) # We fit a polynom of degree 3
#     intrafringe_flx2 = intrafringe_flx - np.poly1d(popt)(intrafringe_pos)

#     to_null_pos = get_field(dl_name, start, end, return_avg_ts)
#     to_null_flx = get_field(fields_of_interest[2], start, end, return_avg_ts)
#     to_null_pos = to_null_pos[:,1]
#     to_null_flx = to_null_flx[:,1]

#     repeat_null_pos.append(to_null_pos)
#     repeat_null_flx.append(to_null_flx)
#     reached_pos = read_current_pos(opcua_motor) * 1000 # in um
#     print('MSG - Reached position', reached_pos)
#     repeat_reached_pos.append(reached_pos)

#     t_scale = np.linspace(-grab_range, 0., len(to_null_flx))
#     ax1.plot(t_scale, to_null_flx)
#     ax1.set_xlabel('Time (s)')
#     ax1.set_ylabel('Flux (count)')
#     ax2.plot(to_null_pos, to_null_flx)
#     ax2.set_xlabel('DL pos (um)')
#     ax2.set_ylabel('Flux (count)')
#     fig.suptitle('Reached null position')

# save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/cophasing/'
# name_file = 'intrafringe_absolute_'+opcua_motor+'_nbfringes_%02d'%(nb_fringes)
# db = {'repeat_null_flx':repeat_null_flx, 'repeat_null_pos':repeat_null_pos,\
#       'gd_params':gd_params, 'targeted_pos':targeted_pos,\
#           'repeat_reached_pos':repeat_reached_pos,\
#           'intrafringe_range':(intrafringe_start, intrafringe_end),\
#             'list_infrafringe_pos':list_infrafringe_pos,\
#             'list_infrafringe_flx':list_infrafringe_flx,\
#             'list_infrafringe_flx2': list_infrafringe_flx2,
#                 'repeat_bck':repeat_bck, 'list_intrafringe_bck':list_intrafringe_bck}
# save_data(db, save_path, name_file)

# print('TODO - Close the plot(s) to continue')
# plt.ioff()
# plt.show()
# print('MSG - Moving back to initial position')

# # =============================================================================
# # Intra-fringe scan with backlash (need global scan to work)
# # =============================================================================
# plt.close('all')
# plt.ioff()
# plt.show()

# """
# This test checks the capability of the DL to perform a scan on a short range, typically
# on a single fringe width.

# It also commission the capability of the DL to reach a position via an absolute command
# (unlike the previous test which use relative command to reach a position)
# """
# print('\n*** Intra-fringe scan ***')
# print('MSG - Global scan - The null position is:', null_scans_best_pos[0])
# # targeted_pos = null_scans_pos[0][np.argmin(null_scans[0])] # Use the minimum value of the scan
# targeted_pos = null_scans_best_pos[0] # Fitted value
# # current_pos = read_current_pos(opcua_motor) * 1000 # in um
# # print('MSG - Current position:', current_pos)
# # print('MSG - Now moving to null position :', targeted_pos)
# # move_abs_dl(targeted_pos/1000, speed, opcua_motor)

# nb_fringes = 2 # Total number of fringes which are scanned
# nb_pass = 10 # Even number for back and forth
# wav = 3.8 # Wavelength in um
# period = wav / 2 # The DL position is half the OPD
# current_pos = read_current_pos(opcua_motor) * 1000 # in um
# intrafringe_start = targeted_pos - period * nb_fringes - 5
# intrafringe_end = targeted_pos + period * nb_fringes
# print('MSG - Move to start position:', intrafringe_start)
# move_abs_dl(intrafringe_start/1000, speed, opcua_motor)

# print('MSG - Start intra-fringe scan (%s - %s)'%(intrafringe_start, intrafringe_end))
# rel_pos  = intrafringe_end - intrafringe_start
# rel_pos /= 1000. # convert to mm
# speed = rel_pos / 2.
# delay = rel_pos/speed
# print('MSG - Speed & Delay', speed, delay)
# time.sleep(1.)

# list_infrafringe_pos = []
# list_infrafringe_flx = []
# list_infrafringe_flx2 = []
# list_infrafringe_params = []
# list_intrafringe_bck = []

# plt.figure(figsize=(15, 8))

# for it in range(nb_pass):
#     print('Pass', it+1, '/', nb_pass)
#     move_rel_dl(rel_pos*(-1)**it, speed, opcua_motor)

#     time.sleep(wait_db)
#     start, end = define_time(delay)
#     time.sleep(wait_db)
#     intrafringe_flx = get_field(fields_of_interest[2], start, end, return_avg_ts)    
#     intrafringe_pos = get_field(dl_name, start, end, return_avg_ts)
#     intrafringe_flx = intrafringe_flx[:,1]
#     intrafringe_pos = intrafringe_pos[:,1]

#     # Rearrange
#     idx = np.argsort(intrafringe_pos)
#     intrafringe_flx = intrafringe_flx[idx]
#     intrafringe_pos = intrafringe_pos[idx]

#     # Remove offset structures on the 1st stage output
#     popt = np.polyfit(dl_pos, data_IA, 3) # We fit a polynom of degree 3
#     intrafringe_flx2 = intrafringe_flx - np.poly1d(popt)(intrafringe_pos)

#     to_null_pos = get_field(dl_name, start, end, return_avg_ts)
#     to_null_flx = get_field(fields_of_interest[2], start, end, return_avg_ts)
#     to_null_pos = to_null_pos[:,1]
#     to_null_flx = to_null_flx[:,1]

#     list_infrafringe_pos.append(intrafringe_pos)
#     list_infrafringe_flx.append(intrafringe_flx)
#     list_infrafringe_flx2.append(intrafringe_flx2)

#     init_guess   = [gd_params[0][0], gd_params[0][1], 0.95]
#     lower_bounds = [0.999*params[0], params[1]-wav/4, -wav/4] # range of 1 fringe so +/- half fringe which means 1/*4 of fringes in DL range
#     upper_bounds = [1.001*params[0], params[1]+wav/4, wav/4] # range of 1 fringe so +/- half fringe which means 1/*4 of fringes in DL range
#     try:
#         params, _ = curve_fit(fringes, intrafringe_pos, intrafringe_flx2, p0=init_guess, bounds=(lower_bounds, upper_bounds))
#     except RuntimeError as e:
#         print(e)
#         params = init_guess
#     list_infrafringe_params.append(params)
#     flx_fit = fringes(intrafringe_pos, *params)

#     if (-1)**it == 1:
#         fig_id = 1
#         fig_title = 'Forth'
#     else:
#         fig_id = 2
#         fig_title = 'Back'
#     plt.subplot(1, 3, fig_id)
#     plt.plot(intrafringe_pos, intrafringe_flx)
#     plt.plot(intrafringe_pos, flx_fit)
#     plt.grid(True)
#     plt.xlabel('DL pos (um)')
#     plt.ylabel('Flux (count)')
#     plt.title(fig_title)
#     plt.subplot(1,3,3)
#     plt.plot(intrafringe_pos, intrafringe_flx2)
#     plt.grid(True)


# # plt.ioff()
# # plt.show()
# print('MSG - Move to intra-fringe start position')
# move_abs_dl(intrafringe_start/1000, speed, opcua_motor) # Make sure we remove backlash
# move_abs_dl(intrafringe_start/1000, speed, opcua_motor)

# print('MSG - Finding the null by averaging the fits of the scans')
# list_infrafringe_pos = list_infrafringe_pos[::2]
# list_infrafringe_flx = list_infrafringe_flx[::2]
# list_infrafringe_flx2 = list_infrafringe_flx2[::2]
# list_infrafringe_params = list_infrafringe_params[::2]

# x_axis = list_infrafringe_pos[0]
# y = np.array([fringes(x_axis, *elt) for elt in list_infrafringe_params])
# ymean = np.mean(y, 0) # Average over all the scans
# null_pos = x_axis[np.argmin(ymean)]

# print('MSG - Null position is:', null_pos)
# plt.subplot(1, 3, 1)
# plt.plot(null_pos, 0., 's', markersize=16)
# plt.subplot(1, 3, 2)
# plt.plot(null_pos, 0., 's', markersize=16)
# plt.tight_layout()
# plt.savefig(save_path+'intrafringe_backlash_%s_speed_%s_nbfringe_%02d.png'%(opcua_motor, speed, nb_fringes), format='png', dpi=150)

# plt.figure()
# plt.plot(x_axis, y.T)
# plt.plot(x_axis, ymean, c='k')
# plt.grid()

# print('\n*** Repeatedly Setting DL to NULL (absolute cmd) ***')

# targeted_pos = null_pos
# repeat_null_flx = []
# repeat_null_pos = []
# repeat_reached_pos = []
# repeat_bck = []
# n_repeat = nb_pass # Even number for back and forth
# grab_range = 0.08 / speed + 1

# fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15,8))
# ax1.grid()
# ax2.grid()

# for k in range(n_repeat):
#     # Go back to starting position when closed
#     print('MSG - Moving back to initial position')
#     move_abs_dl(intrafringe_start/1000, speed, opcua_motor)
#     print(' ')

#     print('Reaching null', k+1, '/', n_repeat)
#     print('MSG - Now moving to null position :', targeted_pos)
#     move_abs_dl(targeted_pos/1000, speed, opcua_motor)
    
#     # Save the last move to check how precise the null is reached
#     time.sleep(wait_time)
#     to_null_pos, to_null_flx, to_null_flx2, bck = grab_flux(grab_range, dl_name)
#     repeat_null_pos.append(to_null_pos)
#     repeat_null_flx.append(to_null_flx2)
#     reached_pos = read_current_pos(opcua_motor) * 1000 # in um
#     print('MSG - Reached position', reached_pos)
#     repeat_reached_pos.append(reached_pos)
#     repeat_bck.append(bck)

#     t_scale = np.linspace(-grab_range, 0., len(to_null_flx2))
#     ax1.plot(t_scale, to_null_flx2)
#     ax1.set_xlabel('Time (s)')
#     ax1.set_ylabel('Flux (count)')
#     ax2.plot(to_null_pos, to_null_flx2)
#     ax2.set_xlabel('DL pos (um)')
#     ax2.set_ylabel('Flux (count)')
#     fig.suptitle('Reached null position')

# save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/cophasing/'
# name_file = 'intrafringe_absolute_'+opcua_motor+'_nbfringes_%02d'%(nb_fringes)
# db = {'repeat_null_flx':repeat_null_flx, 'repeat_null_pos':repeat_null_pos,\
#       'gd_params':gd_params, 'targeted_pos':targeted_pos,\
#           'repeat_reached_pos':repeat_reached_pos,\
#           'intrafringe_range':(intrafringe_start, intrafringe_end),\
#             'list_infrafringe_pos':list_infrafringe_pos,\
#             'list_infrafringe_flx':list_infrafringe_flx,\
#             'list_infrafringe_flx2': list_infrafringe_flx2, 
#               'repeat_bck':repeat_bck, 'list_intrafringe_bck':list_intrafringe_bck}
# save_data(db, save_path, name_file)

# print('TODO - Close the plot(s) to continue')
# plt.ioff()
# plt.show()
# print('MSG - Moving back to initial position')
# move_abs_dl(dl_start, 0.05, opcua_motor)

# # =============================================================================
# # Global scan with stop at every null
# # =============================================================================
# """
# Here we check the ability of the DL to perform global scan, find the null and reach it at every pass.
# Given the backlash, reaching a position is always made from the same direction.
# """
# plt.ion()
# speed2 = speed
# n_pass = 10

# # Set DL to initial position
# print('MSG - Move DL to initial position:', )
# move_abs_dl(dl_start, speed, opcua_motor, pos_offset)

# null_scans = []
# null_scans_pos = []
# null_scans_best_pos = []
# gd_params = []
# to_null_positions = []
# to_null_flux = []
# histo_current_positions = []

# dl_bounds = [dl_end, dl_start]
# dl_bounds2 = [dl_start, dl_end]

# fig1, (ax1_t1, ax1_t2) = plt.subplots(2, 1, figsize=(8,5)) # Display scan forth
# move_figure(fig1, 0, 0)
# fig2, (ax2_t1, ax2_t2) = plt.subplots(2, 1, figsize=(8,5)) # Display scan back

# for it in range(n_pass):

#     print('MSG - Pass', it+1, '/', n_pass)

#     if it % 2 == 0: # Scan forward
#         revert_ts = False
#     else: # Scan backward
#         revert_ts = True

#     best_null_pos, flx_coh, dl_pos, params, fit_data = do_scans(dl_name, dl_bounds[it%2], speed, opcua_motor, fields_of_interest[2], delay, 
#                  return_avg_ts, wait_db, dl_start, dl_end, wav, pos_offset, revert_ts)
#     pos_env, flx_env, pos_fit, flx_fit = fit_data

#     null_scans_best_pos.append(best_null_pos)
#     gd_params.append(params)
#     null_scans.append(flx_coh)
#     null_scans_pos.append(dl_pos)

#     # Adjust the axis range for time plot
#     x_min, x_max = np.min(1000*min(dl_start,dl_end)), np.max(1000*max(dl_start,dl_end)) 
#     marginx = 25

#     y_min, y_max = np.min(flx_coh), np.max(flx_coh) 
#     marginy = 0

#     if (it+1)%2 != 0:
#         # Clear the axes
#         ax1_t1.clear() 
#         fig1.suptitle('Forward direction - Best null pos: %.5f'%(best_null_pos))
#         ax1_t1.set_xlabel('DL position [microns]')
#         ax1_t1.set_ylabel('ROI value')
#         ax1_t2.clear() 
#         ax1_t2.set_xlabel('DL position [microns]')
#         ax1_t2.set_ylabel('ROI value')

#         # Set x and y dynamic ranges
#         ax1_t1.set_ylim(y_min - marginy, y_max + marginy)    
#         ax1_t2.set_ylim(y_min - marginy, y_max + marginy)    
#         ax1_t1.set_xlim(x_min - marginx, x_max + marginx)
#         ax1_t2.set_xlim(best_null_pos - marginx, best_null_pos + marginx)

#         # Plot curves
#         line_t3, = ax1_t1.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
#         line_t2, = ax1_t1.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
#         line_t1, = ax1_t1.plot(dl_pos, flx_coh, label='Fringes')
#         line_t4 = ax1_t1.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
#                                   color='magenta', label='Best null')
#         ax1_t1.legend(loc='best')

#         line_t3, = ax1_t2.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
#         line_t2, = ax1_t2.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
#         line_t1, = ax1_t2.plot(dl_pos, flx_coh, label='Fringes')
#         line_t4 = ax1_t2.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
#                                   color='magenta', label='Best null')
#     else:
#         # Clear the axes
#         fig2.suptitle('Back direction - Best null pos: %.5f'%(best_null_pos))
#         ax2_t1.clear() 
#         ax2_t1.set_xlabel('DL position [microns]')
#         ax2_t1.set_ylabel('ROI value')
#         ax2_t2.clear() 
#         ax2_t2.set_xlabel('DL position [microns]')
#         ax2_t2.set_ylabel('ROI value')
        
#         # Set x and y dynamic ranges
#         ax2_t1.set_ylim(y_min - marginy, y_max + marginy)    
#         ax2_t2.set_ylim(y_min - marginy, y_max + marginy)    
#         ax2_t1.set_xlim(x_min - marginx, x_max + marginx)
#         ax2_t2.set_xlim(best_null_pos - marginx, best_null_pos + marginx)

#         # Plot curves
#         line_t3, = ax2_t1.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
#         line_t2, = ax2_t1.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
#         line_t1, = ax2_t1.plot(dl_pos, flx_coh, label='Fringes')
#         line_t4 = ax2_t1.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
#                                   color='magenta', label='Best null')
#         ax2_t1.legend(loc='best')

#         line_t3, = ax2_t2.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
#         line_t2, = ax2_t2.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
#         line_t1, = ax2_t2.plot(dl_pos, flx_coh, label='Fringes')
#         line_t4 = ax2_t2.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
#                                   color='magenta', label='Best null')

#     print('MSG - Moving to the best null position: going back to starting point of scan')
#     move_abs_dl(dl_bounds2[it%2], speed, opcua_motor, pos_offset)
    
#     to_null_pos, to_null_flx0, current_null_pos = set_dl_to_null(best_null_pos, opcua_motor, speed2, grab_range, dl_name, return_avg_ts, pos_offset, fields_of_interest[2])
#     t_scale = to_null_flx0[:,0] - to_null_flx0[:,0].max()
#     to_null_flx = to_null_flx0[:,1]

#     to_null_positions.append(to_null_pos)
#     to_null_flux.append(to_null_flx0)
#     histo_current_positions.append(current_null_pos)

#     if it % 2 == 0:
#         figx, (axe1, axe2) = plt.subplots(2, 1, figsize=(8,5)) # Display scan forth
#         axe1.grid()
#         axe1.set_xlabel('Time (s)')
#         axe1.set_ylabel('Flux (count)')
#         axe2.grid()
#         axe2.set_xlabel('Time (s)')
#         axe2.set_ylabel('Flux (count)')
#         axe1.plot(t_scale/1e3, to_null_flx)
#         axe1.set_title('%s - FORWARD Reached null position: %.5f\nTargeted position: %.5f'%(it+1, current_null_pos, best_null_pos))
#     else:
#         axe2.plot(t_scale/1e3, to_null_flx)
#         axe2.set_title('%s - BACKWARD Reached null position: %.5f\nTargeted position: %.5f'%(it+1, current_null_pos, best_null_pos))
    
#     figx.tight_layout()

#     print('MSG - Moving to the other side')
#     move_abs_dl(dl_bounds[it%2], speed, opcua_motor, pos_offset)
#     print(' ')

# print('MSG - End of pass')
# # plt.ioff()
# # plt.show()

# # Show results of the scans, individual scan can have different numbers of points
# scans_forth = null_scans[::2]
# scans_forth_pos = null_scans_pos[::2]
# scans_back = null_scans[1::2]
# scans_back_pos = null_scans_pos[1::2]
# fwd_to_null_pos = to_null_positions[::2]
# fwd_to_null_flx = to_null_flux[::2]
# fwd_histo_current_pos = histo_current_positions[::2]
# bcw_to_null_pos = to_null_positions[1::2]
# bcw_to_null_flx = to_null_flux[1::2]
# bcw_histo_current_pos = histo_current_positions[1::2]

# db = {'scans_forth_pos':scans_forth_pos, 'scans_forth':scans_forth,
#       'scans_back_pos':scans_back_pos, 'scans_back':scans_back,
#         'null_scans_best_pos': null_scans_best_pos,
#             'fwd_to_null':[fwd_to_null_pos, fwd_to_null_flx],
#                               'bcw_to_null':[bcw_to_null_pos, bcw_to_null_flx],
#                               'fwd_histo_current_pos': fwd_histo_current_pos,
#                               'bcw_histo_current_pos': bcw_histo_current_pos
#                   }

# save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/cophasing/'
# name_file = 'mech_scans_'+dl_name+'_speed_%s'%(speed)
# save_data(db, save_path, name_file)

# """
# This plot shows how repeatable a scan is
# """
# colours = plt.rcParams['axes.prop_cycle'].by_key()['color']

# fig3, (ax31, ax32) = plt.subplots(2, 1, figsize=(8,5)) # Display scan forth
# ax31.set_title('Forward')
# [ax31.plot(scans_forth_pos[i], scans_forth[i], c=colours[i]) for i in range(len(scans_forth))]
# [ax31.axvline(null_scans_best_pos[::2][i], min(scans_forth[i]) - ymargin, max(scans_forth[i]) + ymargin, color=colours[i]) for i in range(len(scans_forth))]
# [ax31.axvline(fwd_histo_current_pos[i], min(scans_forth[i]) - ymargin, max(scans_forth[i]) + ymargin, color=colours[i], ls='--') for i in range(len(scans_forth))]
# ax31.grid()
# ax31.set_xlabel('DL pos (um)')
# ax31.set_ylabel('Flux (count)')
# ax32.set_title('Backward')
# [ax32.plot(scans_back_pos[i], scans_back[i]) for i in range(len(scans_back))]
# [ax32.axvline(null_scans_best_pos[1::2][i], min(scans_back[i]) - ymargin, max(scans_back[i]) + ymargin, color=colours[i]) for i in range(len(scans_forth))]
# [ax32.axvline(bcw_histo_current_pos[i], min(scans_forth[i]) - ymargin, max(scans_forth[i]) + ymargin, color=colours[i], ls='--') for i in range(len(scans_forth))]
# ax32.grid()
# ax32.set_xlabel('DL pos (um)')
# ax32.set_ylabel('Flux (count)')
# fig3.tight_layout()

# print('TODO - Close the plot(s) to continue')
# plt.ioff()
# plt.show()

# # =============================================================================
# # Global scan with stop at every null in only one direction then the other
# # =============================================================================
# """
# Here we check the ability of the DL to perform global scan, find the null and reach it at every pass.
# We first reproduce the scans in the same direction after make a new serie with the other.
# Given the backlash, reaching a position is always made from the same direction.
# """
# plt.ion()
# speed2 = speed
# n_pass = 5
# revert_ts = False

# dl_bounds = [dl_end, dl_start]
# dl_bounds2 = [dl_start, dl_end]

# null_scans = []
# null_scans_pos = []
# null_scans_best_pos = []
# gd_params = []
# to_null_positions = []
# to_null_flux = []
# histo_current_positions = []

# for direction in range(2):
#     print('MSG - DIRECTION:', direction)
#     if direction == 1:
#         dl_bounds = dl_bounds[::-1]
#         dl_bounds2 = dl_bounds2[::-1]

#     # Set DL to initial position
#     print('MSG - Move DL to initial position')
#     move_abs_dl(dl_bounds2[0], speed, opcua_motor, pos_offset)

#     fig1, (ax1_t1, ax1_t2) = plt.subplots(2, 1, figsize=(8,5)) # Display scan forth
#     move_figure(fig1, 0, 0)

#     for it in range(n_pass):
#         print('MSG - Pass', it+1, '/', n_pass)
#         print('MSG - Moving to the starting side')
#         move_abs_dl(dl_bounds2[0], speed, opcua_motor, pos_offset)
#         print('MSG - Start scan')
#         best_null_pos, flx_coh, dl_pos, params, fit_data = do_scans(dl_name, dl_bounds[0], speed, opcua_motor, fields_of_interest[2], delay, 
#                     return_avg_ts, wait_db, dl_start, dl_end, wav, pos_offset, revert_ts)
#         pos_env, flx_env, pos_fit, flx_fit = fit_data

#         null_scans_best_pos.append(best_null_pos)
#         gd_params.append(params)
#         null_scans.append(flx_coh)
#         null_scans_pos.append(dl_pos)

#         # Adjust the axis range for time plot
#         x_min, x_max = np.min(1000*min(dl_start,dl_end)), np.max(1000*max(dl_start,dl_end)) 
#         marginx = 25

#         y_min, y_max = np.min(flx_coh), np.max(flx_coh) 
#         marginy = 0

#         # Clear the axes
#         ax1_t1.clear() 
#         if direction == 0:
#             fig1.suptitle('Forward direction - Best null pos: %.5f'%(best_null_pos))
#         else:
#             fig1.suptitle('Backward direction - Best null pos: %.5f'%(best_null_pos))
#         ax1_t1.set_xlabel('DL position [microns]')
#         ax1_t1.set_ylabel('ROI value')
#         ax1_t2.clear() 
#         ax1_t2.set_xlabel('DL position [microns]')
#         ax1_t2.set_ylabel('ROI value')

#         # Set x and y dynamic ranges
#         ax1_t1.set_ylim(y_min - marginy, y_max + marginy)    
#         ax1_t2.set_ylim(y_min - marginy, y_max + marginy)    
#         ax1_t1.set_xlim(x_min - marginx, x_max + marginx)
#         ax1_t2.set_xlim(best_null_pos - marginx, best_null_pos + marginx)

#         # Plot curves
#         line_t3, = ax1_t1.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
#         line_t2, = ax1_t1.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
#         line_t1, = ax1_t1.plot(dl_pos, flx_coh, label='Fringes')
#         line_t4 = ax1_t1.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
#                                     color='magenta', label='Best null')
#         ax1_t1.legend(loc='best')

#         line_t3, = ax1_t2.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
#         line_t2, = ax1_t2.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
#         line_t1, = ax1_t2.plot(dl_pos, flx_coh, label='Fringes')
#         line_t4 = ax1_t2.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
#                                     color='magenta', label='Best null')
#         fig1.tight_layout()
#         plt.draw()


#         print('MSG - Moving to the best null position: going back to starting point of scan')
#         move_abs_dl(dl_bounds2[0], speed, opcua_motor, pos_offset)

#         print('MSG - Moving to the best null position: going to null')
#         to_null_pos, to_null_flx0, current_null_pos = set_dl_to_null(best_null_pos, opcua_motor, speed2, grab_range, dl_name, return_avg_ts, pos_offset, fields_of_interest[2])
#         t_scale = to_null_flx0[:,0] - to_null_flx0[:,0].max()
#         to_null_flx = to_null_flx0[:,1]

#         to_null_pos_interp = interpolate_ts(to_null_pos, to_null_flx0)

#         to_null_positions.append(to_null_pos)
#         to_null_flux.append(to_null_flx0)
#         histo_current_positions.append(current_null_pos)

#         figx, (axe1, axe2, axe3) = plt.subplots(3, 1, figsize=(8,5)) # Display reaching null
#         axe1.grid()
#         axe1.set_xlabel('Time (s)')
#         axe1.set_ylabel('Flux (count)')
#         axe1.plot(t_scale/1e3, to_null_flx)
#         if direction == 0:
#             axe1.set_title('%s - FORWARD Reached null position: %.5f\nTargeted position: %.5f'%(it+1, current_null_pos, best_null_pos))
#         else:
#             axe1.set_title('%s - BACKWARD Reached null position: %.5f\nTargeted position: %.5f'%(it+1, current_null_pos, best_null_pos))
#         axe2.plot(to_null_pos_interp[:,1], c, '.')
#         axe2.grid()
#         axe2.set_xlabel('DL position (um)')
#         axe2.set_ylabel('Flux (count)')
#         axe3.plot(t_scale/1e3, to_null_pos_interp[:,1])
#         axe3.grid()
#         axe3.set_xlabel('Time (s)')
#         axe3.set_ylabel('DL position (um)')

#         figx.tight_layout()
#         plt.draw()
#         figx.tight_layout()
#         plt.pause(0.2)

#         print(' ')

# print('MSG - End of pass')

# # Show results of the scans, individual scan can have different numbers of points
# scans_forth = null_scans[:len(null_scans)//2]
# scans_forth_pos = null_scans_pos[:len(null_scans_pos)//2]
# scans_back = null_scans[len(null_scans)//2:]
# scans_back_pos = null_scans_pos[len(null_scans_pos)//2:]
# fwd_to_null_pos = to_null_positions[:len(to_null_positions)//2]
# fwd_to_null_flx = to_null_flux[:len(to_null_flux)//2]
# fwd_histo_current_pos = histo_current_positions[:len(histo_current_positions)//2]
# bcw_to_null_pos = to_null_positions[len(to_null_positions)//2:]
# bcw_to_null_flx = to_null_flux[len(to_null_flux)//2:]
# bcw_histo_current_pos = histo_current_positions[len(histo_current_positions)//2:]
# fwd_null_scans_best_pos = null_scans_best_pos[:len(null_scans_best_pos)//2]
# bcw_null_scans_best_pos = null_scans_best_pos[len(null_scans_best_pos)//2:]

# db = {'scans_forth_pos':scans_forth_pos, 'scans_forth':scans_forth,
#       'scans_back_pos':scans_back_pos, 'scans_back':scans_back,
#         'fwd_null_scans_best_pos': fwd_null_scans_best_pos,
#         'bcw_null_scans_best_pos':bcw_null_scans_best_pos,
#             'fwd_to_null':[fwd_to_null_pos, fwd_to_null_flx],
#                               'bcw_to_null':[bcw_to_null_pos, bcw_to_null_flx],
#                               'fwd_histo_current_pos': fwd_histo_current_pos,
#                               'bcw_histo_current_pos': bcw_histo_current_pos
#                   }

# save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/cophasing/'
# name_file = 'mech_scans_unidirection_'+dl_name+'_speed_%s'%(speed)
# save_data(db, save_path, name_file)

# """
# This plot shows how repeatable a scan is
# """
# colours = plt.rcParams['axes.prop_cycle'].by_key()['color']

# fig3, (ax31, ax32) = plt.subplots(2, 1, figsize=(8,5)) # Display scan forth
# ax31.set_title('Forward')
# [ax31.plot(scans_forth_pos[i], scans_forth[i], c=colours[i]) for i in range(len(scans_forth))]
# [ax31.axvline(fwd_null_scans_best_pos[i], min(scans_forth[i]) - ymargin, max(scans_forth[i]) + ymargin, color=colours[i]) for i in range(len(scans_forth))]
# [ax31.axvline(fwd_histo_current_pos[i], min(scans_forth[i]) - ymargin, max(scans_forth[i]) + ymargin, color=colours[i], ls='--') for i in range(len(scans_forth))]
# ax31.grid()
# ax31.set_xlabel('DL pos (um)')
# ax31.set_ylabel('Flux (count)')
# ax32.set_title('Backward')
# [ax32.plot(scans_back_pos[i], scans_back[i]) for i in range(len(scans_back))]
# [ax32.axvline(bcw_null_scans_best_pos[i], min(scans_back[i]) - ymargin, max(scans_back[i]) + ymargin, color=colours[i]) for i in range(len(scans_back))]
# [ax32.axvline(bcw_histo_current_pos[i], min(scans_forth[i]) - ymargin, max(scans_forth[i]) + ymargin, color=colours[i], ls='--') for i in range(len(scans_back))]
# ax32.grid()
# ax32.set_xlabel('DL pos (um)')
# ax32.set_ylabel('Flux (count)')
# fig3.tight_layout()

# print('TODO - Close the plot(s) to continue')
# plt.ioff()
# plt.show()

# =============================================================================
# Global scan and directly reach the null depth
# =============================================================================
"""
Here we check the ability of the DL to perform global scan, find the null and reach it at every pass.
We first reproduce the scans in the same direction after make a new serie with the other.
Once the null detected, we go for it.
"""
plt.ion()
speed2 = speed
n_pass = 10

# Set DL to initial position
print('MSG - Move DL to initial position:', )
move_abs_dl(dl_start, speed, opcua_motor, pos_offset)

null_scans = []
null_scans_pos = []
null_scans_best_pos = []
gd_params = []
to_null_positions = []
to_null_flux = []
histo_current_positions = []

dl_bounds = [dl_end, dl_start]

fig1, (ax1_t1, ax1_t2) = plt.subplots(2, 1, figsize=(8,5)) # Display scan forth
move_figure(fig1, 0, 0)
fig2, (ax2_t1, ax2_t2) = plt.subplots(2, 1, figsize=(8,5)) # Display scan back

for it in range(n_pass):

    print('MSG - Pass', it+1, '/', n_pass)

    if it % 2 == 0: # Scan forward
        revert_ts = False
    else: # Scan backward
        revert_ts = True

    best_null_pos, flx_coh, dl_pos, params, fit_data = do_scans(dl_name, dl_bounds[it%2], speed, opcua_motor, fields_of_interest[2], delay, 
                 return_avg_ts, wait_db, dl_start, dl_end, wav, pos_offset, revert_ts)
    pos_env, flx_env, pos_fit, flx_fit = fit_data

    null_scans_best_pos.append(best_null_pos)
    gd_params.append(params)
    null_scans.append(flx_coh)
    null_scans_pos.append(dl_pos)

    # Adjust the axis range for time plot
    x_min, x_max = np.min(1000*min(dl_start,dl_end)), np.max(1000*max(dl_start,dl_end)) 
    marginx = 25

    y_min, y_max = np.min(flx_coh), np.max(flx_coh) 
    marginy = 0

    if (it+1)%2 != 0:
        # Clear the axes
        ax1_t1.clear() 
        fig1.suptitle('Forward direction - Best null pos: %.5f'%(best_null_pos))
        ax1_t1.set_xlabel('DL position [microns]')
        ax1_t1.set_ylabel('ROI value')
        ax1_t2.clear() 
        ax1_t2.set_xlabel('DL position [microns]')
        ax1_t2.set_ylabel('ROI value')

        # Set x and y dynamic ranges
        ax1_t1.set_ylim(y_min - marginy, y_max + marginy)    
        ax1_t2.set_ylim(y_min - marginy, y_max + marginy)    
        ax1_t1.set_xlim(x_min - marginx, x_max + marginx)
        ax1_t2.set_xlim(best_null_pos - marginx, best_null_pos + marginx)

        # Plot curves
        line_t3, = ax1_t1.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
        line_t2, = ax1_t1.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
        line_t1, = ax1_t1.plot(dl_pos, flx_coh, label='Fringes')
        line_t4 = ax1_t1.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
                                  color='magenta', label='Best null')
        ax1_t1.legend(loc='best')

        line_t3, = ax1_t2.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
        line_t2, = ax1_t2.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
        line_t1, = ax1_t2.plot(dl_pos, flx_coh, label='Fringes')
        line_t4 = ax1_t2.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
                                  color='magenta', label='Best null')
    else:
        # Clear the axes
        fig2.suptitle('Back direction - Best null pos: %.5f'%(best_null_pos))
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
        ax2_t2.set_xlim(best_null_pos - marginx, best_null_pos + marginx)

        # Plot curves
        line_t3, = ax2_t1.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
        line_t2, = ax2_t1.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
        line_t1, = ax2_t1.plot(dl_pos, flx_coh, label='Fringes')
        line_t4 = ax2_t1.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
                                  color='magenta', label='Best null')
        ax2_t1.legend(loc='best')

        line_t3, = ax2_t2.plot(pos_fit, flx_fit, color='grey', linewidth=0.4, label='Best-fit fringes')
        line_t2, = ax2_t2.plot(pos_env, flx_env, color='blue', linewidth=0.8, label='Best-fit envelope')
        line_t1, = ax2_t2.plot(dl_pos, flx_coh, label='Fringes')
        line_t4 = ax2_t2.axvline(best_null_pos, y_min - ymargin, y_max + ymargin, 
                                  color='magenta', label='Best null')
    plt.draw()

    
    to_null_pos, to_null_flx0, current_null_pos = set_dl_to_null(best_null_pos, opcua_motor, speed2, grab_range, dl_name, return_avg_ts, pos_offset, fields_of_interest[2])
    t_scale = to_null_flx0[:,0] - to_null_flx0[:,0].max()
    to_null_flx = to_null_flx0[:,1]

    to_null_pos_interp = interpolate_ts(to_null_pos, to_null_flx0)

    to_null_positions.append(to_null_pos)
    to_null_flux.append(to_null_flx0)
    histo_current_positions.append(current_null_pos)

    figx, (axe1, axe2, axe3) = plt.subplots(3, 1, figsize=(8,5)) # Display reaching null
    axe1.grid()
    axe1.set_xlabel('Time (s)')
    axe1.set_ylabel('Flux (count)')
    axe1.plot(t_scale/1e3, to_null_flx)
    if it % 2 == 0:
        axe1.set_title('%s - FORWARD Reached null position: %.5f\nTargeted position: %.5f'%(it+1, current_null_pos, best_null_pos))
    else:
        axe1.set_title('%s - BACKWARD Reached null position: %.5f\nTargeted position: %.5f'%(it+1, current_null_pos, best_null_pos))
    axe2.plot(to_null_pos_interp[:,1], to_null_flx)
    axe2.grid()
    axe2.set_xlabel('DL position (um)')
    axe2.set_ylabel('Flux (count)')
    axe3.plot(t_scale/1e3, to_null_pos_interp[:,1])
    axe3.grid()
    axe3.set_xlabel('Time (s)')
    axe3.set_ylabel('DL position (um)')
    figx.tight_layout()
    plt.draw()
    plt.pause(0.2)    

    print('MSG - Moving to the other side')
    move_abs_dl(dl_bounds[it%2], speed, opcua_motor, pos_offset)
    print(' ')

print('MSG - End of pass')
# plt.ioff()
# plt.show()

# Show results of the scans, individual scan can have different numbers of points
scans_forth = null_scans[::2]
scans_forth_pos = null_scans_pos[::2]
scans_back = null_scans[1::2]
scans_back_pos = null_scans_pos[1::2]
fwd_to_null_pos = to_null_positions[::2]
fwd_to_null_flx = to_null_flux[::2]
fwd_histo_current_pos = histo_current_positions[::2]
bcw_to_null_pos = to_null_positions[1::2]
bcw_to_null_flx = to_null_flux[1::2]
bcw_histo_current_pos = histo_current_positions[1::2]
fwd_null_scans_best_pos = null_scans_best_pos[:len(null_scans_best_pos)//2]
bcw_null_scans_best_pos = null_scans_best_pos[len(null_scans_best_pos)//2:]


db = {'scans_forth_pos':scans_forth_pos, 'scans_forth':scans_forth,
      'scans_back_pos':scans_back_pos, 'scans_back':scans_back,
        'null_scans_best_pos': null_scans_best_pos,
        'fwd_null_scans_best_pos': fwd_null_scans_best_pos,
        'bcw_null_scans_best_pos':bcw_null_scans_best_pos,        
            'fwd_to_null':[fwd_to_null_pos, fwd_to_null_flx],
                              'bcw_to_null':[bcw_to_null_pos, bcw_to_null_flx],
                              'fwd_histo_current_pos': fwd_histo_current_pos,
                              'bcw_histo_current_pos': bcw_histo_current_pos
                  }

save_path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/cophasing/'
name_file = 'mech_scans_direct_'+dl_name+'_speed_%s'%(speed)
save_data(db, save_path, name_file)

"""
This plot shows how repeatable a scan is
"""
colours = plt.rcParams['axes.prop_cycle'].by_key()['color']

fig3, (ax31, ax32) = plt.subplots(2, 1, figsize=(8,5)) # Display scan forth
ax31.set_title('Forward')
[ax31.plot(scans_forth_pos[i], scans_forth[i], c=colours[i]) for i in range(len(scans_forth))]
[ax31.axvline(null_scans_best_pos[::2][i], min(scans_forth[i]) - ymargin, max(scans_forth[i]) + ymargin, color=colours[i]) for i in range(len(scans_forth))]
[ax31.axvline(fwd_histo_current_pos[i], min(scans_forth[i]) - ymargin, max(scans_forth[i]) + ymargin, color=colours[i], ls='--') for i in range(len(scans_forth))]
ax31.grid()
ax31.set_xlabel('DL pos (um)')
ax31.set_ylabel('Flux (count)')
ax32.set_title('Backward')
[ax32.plot(scans_back_pos[i], scans_back[i]) for i in range(len(scans_back))]
[ax32.axvline(null_scans_best_pos[1::2][i], min(scans_back[i]) - ymargin, max(scans_back[i]) + ymargin, color=colours[i]) for i in range(len(scans_forth))]
[ax32.axvline(bcw_histo_current_pos[i], min(scans_forth[i]) - ymargin, max(scans_forth[i]) + ymargin, color=colours[i], ls='--') for i in range(len(scans_forth))]
ax32.grid()
ax32.set_xlabel('DL pos (um)')
ax32.set_ylabel('Flux (count)')
fig3.tight_layout()

print('TODO - Close the plot(s) to continue')
plt.ioff()
plt.show()