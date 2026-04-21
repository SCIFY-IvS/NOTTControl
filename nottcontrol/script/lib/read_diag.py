import sys
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/')
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit
import os
import pickle


def loadData(file_name):
    # for reading also binary mode is important
    dbfile = open(file_name, 'rb')    
    db = pickle.load(dbfile)
    dbfile.close()

    return db

dl_id = 2
speed = 0.05 #mm/s
wait_time = 0.08 / speed * 2.5 # Time in sec to scan X times the coherent envelope
grab_range = 0.08 / speed * 5 # Time in sec to scan X times the coherent envelope

if dl_id == 2:
    opcua_motor = 'DL_2'
    dl_name = 'DL_2_Newport_pos'
    dl_start = 1. # mm
    dl_end   = 1.3 # mm
    dl_init_pos1 = 1.1 # mm
else:
    opcua_motor = 'DL_Servo_1'
    dl_name = 'DL_Servo_1_pos'
    dl_start = 1.1 # mm
    dl_end   = 1.4 # mm
    dl_init_pos2  = 1.3 # mm

path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/scipt/diagnostics/'
file_name = 'null_scans_'+opcua_motor+'_speed_%s_001.pkl'%(speed)

db = loadData(path+file_name)

# plt.figure(figsize=(10, 5))
# plt.subplot(131)
# plt.plot(db['to_null'][0])
# plt.grid()
# plt.subplot(132)
# plt.plot(db['to_null'][1])
# plt.grid()
# plt.subplot(133)
# plt.plot(db['to_null'][2])
# plt.grid()

# plt.figure()
# plt.subplot(131)
# plt.plot(db['to_null_avg'][0])
# plt.grid()
# plt.subplot(132)
# plt.plot(db['to_null_avg'][1])
# plt.grid()
# plt.subplot(133)
# plt.plot(db['to_null_avg'][2])
# plt.grid()

# plt.figure()
# plt.plot(db['scans_forth_pos'][0], db['scans_forth'][0])

# plt.show()

db = loadData(path+'null_repeat_'+opcua_motor+'_speed_%s_001.pkl'%(speed))

print(len(db['gd_params']), db['gd_params'])
print('*****')
print(db['targeted_pos'])
print('*****')
print(len(db['repeat_reached_pos']), db['repeat_reached_pos'])
