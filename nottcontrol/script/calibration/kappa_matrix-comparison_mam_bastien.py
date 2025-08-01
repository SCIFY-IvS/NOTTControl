import sys

# Add the path to sys.path
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/lib/')
import redis
import time
from datetime import datetime, timedelta
from nott_control import shutter_close, shutter_open
import numpy as np
from nott_maintenance import startup, shutdown
from nott_acquisition import cophase, get_darks, get_flats
import os
from scipy.interpolate import interp1d
from nott_fringes import fringes, fringes_env, envelop_detector
from scipy.optimize import curve_fit
from nott_control import move_rel_dl, move_abs_dl, read_current_pos
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from numpy.polynomial import Polynomial

# Get epoch
epoch = datetime.utcfromtimestamp(0)

def unix_time_ms(time):
    return round((time - epoch).total_seconds() * 1000.0)
    # try:
    #     return round((time - epoch).total_seconds() * 1000.0)
    # except TypeError:
    #     return time


def define_time(delay):# Define time interval        
    end   = datetime.utcnow() # - timedelta(seconds=0.9) # There is a 0.9 sec delay with redis
    start = end - timedelta(seconds=delay) 

    end = unix_time_ms(end)
    start = unix_time_ms(start)
    return(start,end)

def get_field(field1, start, end):
    
    
    # Read data
    r = redis.from_url('redis://nott-server.ster.kuleuven.be:6379')

    # Extract data
    ts = r.ts()

     # Get ROI values
    # result1 = ts.range(field1, unix_time_ms(start), unix_time_ms(end))
    result1 = ts.range(field1, start, end)

    output1 = [(x[1]) for x in result1]

    #print( output1)
   
    
    # Return 
    return  output1
   

def get_mean_value(field, start, end):# Get the mean of field during delay seconds
    
    data=get_field(field, start, end)

    mean=sum(data)/len(data)
   
    return(mean)

'''
def remove_background(field,shift,start, end): #remove the backround of field and the shift

    value_i=get_mean_value(field, start, end)
    shift_i=get_mean_value(shift, start,end)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    start = datetime.utcnow() # - timedelta(seconds=0.9) # There is a 0.9 sec delay with redis

    time.sleep(1)

    end = datetime.utcnow() # - timedelta(seconds=0.9) # There is a 0.9 sec delay with redis

    value_f=get_mean_value(field, start,end)
    shift_f=get_mean_value(shift, start,end)

    
    shutter_open('1')
    shutter_open('2')
    shutter_open('3')
    shutter_open('4')

    return(value_i-shift_i-value_f+shift_f) '''

def get_position(DL,field, start,end): #return podition of Delay line 'DL' and the values of Roi 'Field' between start and end 

    
    # Read data
    r = redis.from_url('redis://nott-server.ster.kuleuven.be:6379')

    # Extract data
    ts = r.ts()

     # Get ROI values

    result1 = ts.range(field, unix_time_ms(start), unix_time_ms(end))
    output1 = [(x[1]) for x in result1]
    # Get DL position
    # temp   = ts.range('dl_pos_1', unix_time_ms(start), unix_time_ms(end))
    temp   = ts.range( DL, unix_time_ms(start), unix_time_ms(end))
    x_time = [(x[0] / 1000) for x in temp]
    x_pos0 = [(x[1]) for x in temp]
    # Interpolate DL position on ROIs time stamps
    vm = np.mean(x_pos0)
    f = interp1d(x_time, x_pos0, bounds_error=False, fill_value=vm, kind='cubic')
   
    # Convert to UTC time
    real_time1 = [(x[0] / 1000) for x in result1]
  
    # Re-order
    #print('Size camera output', len(real_time1))
    #print('Size DL output', len(x_pos0))

    # Get DL position at the same time
    x_pos = f(real_time1)
    #min_flx = np.min(x_pos)
    #min_pos = x_pos.argmin(min_flx)
    #print(len(x_pos))

    # Compute elasped time
    real_time1 -= np.min(real_time1)


    # Return 
    return x_pos, output1



def Kappa_matrix_measurement_1 (delay,shutter):# calculation of Kappa Matrix (Interferometric outputs depending of the photometric outputs )
                                     # delay define the time to take the measure and to do the mean
    global startend, time1
    global kmoni01, kmoni02
    global kmonitor11, kmonitor12, kmonitor21, kmonitor22, kmonitor31, kmonitor32, kmonitor41, kmonitor42


    # [(start11, end11, start12, end12), 
    #                 (start21, end21, start22, end22),
    #                 (start31, end31, start32, end32),
    #                 (start41, end41, start42, end42)] = time1
     
    P1='roi1_sum' # define all the ROI output
    P2='roi2_sum'
    I1='roi3_sum'
    I2='roi4_sum'
    I3='roi5_sum'
    I4='roi6_sum'
    P3='roi7_sum'
    P4='roi8_sum'
    Shift='roi9_sum'

    shutter_open('1') # Measure the beam 1's outputs
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    [start11, end11]=define_time(delay)
    time.sleep(delay)

    Value_P1=get_mean_value(P1, start11,end11) #get the values of each output
    Value_I1=get_mean_value(I1, start11,end11)
    Value_I2=get_mean_value(I2, start11,end11)
    Value_I3=get_mean_value(I3, start11,end11)
    Value_I4=get_mean_value(I4, start11,end11)
    Value_Shift=get_mean_value(Shift, start11,end11)#get the first value of the shift
    kmonitor11 = [Value_P1, Value_I1, Value_I2, Value_I3, Value_I4, Value_Shift]

    shutter_close('1') #take the background
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    [start12, end12]=define_time(delay)
    time.sleep(delay)

    Value_P1_2=get_mean_value(P1, start12,end12)
    Value_I1_2=get_mean_value(I1, start12,end12)
    Value_I2_2=get_mean_value(I2, start12,end12)
    Value_I3_2=get_mean_value(I3, start12,end12)
    Value_I4_2=get_mean_value(I4, start12,end12)
    Value_Shift_2=get_mean_value(Shift, start12,end12) #get the second shift value
    kmonitor12 = [Value_P1_2, Value_I1_2, Value_I2_2, Value_I3_2, Value_I4_2, Value_Shift_2]

    P1_clean=Value_P1-Value_Shift-Value_P1_2+Value_Shift_2+shutter[0]# clean background and shift and shutter radiation for photometric output
   

    P1_coefficients=[Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[1],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[2],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[3],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[4] ]
    P1_coefficients=[x / P1_clean for x in P1_coefficients]   #put the four intensity value for interferometric output in a matrix and then divise by the photometric output (I1/P1,I2/P1,I3/P1,I4/P1)


    shutter_open('2') # Measure the beam 2's outputs
    shutter_close('1')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    [start21, end21]=define_time(delay)
    time.sleep(delay)

    Value_P2=get_mean_value(P2, start21,end21)
    Value_I1=get_mean_value(I1, start21,end21)
    Value_I2=get_mean_value(I2, start21,end21)
    Value_I3=get_mean_value(I3, start21,end21)
    Value_I4=get_mean_value(I4, start21,end21)
    Value_Shift=get_mean_value(Shift, start21,end21)
    kmonitor21 = [Value_P2, Value_I1, Value_I2, Value_I3, Value_I4, Value_Shift]

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')


    time.sleep(delay)
    [start22, end22]=define_time(delay)
    time.sleep(delay)

    Value_P2_2=get_mean_value(P2, start22,end22)
    Value_I1_2=get_mean_value(I1, start22,end22)
    Value_I2_2=get_mean_value(I2, start22,end22)
    Value_I3_2=get_mean_value(I3, start22,end22)
    Value_I4_2=get_mean_value(I4, start22,end22)
    Value_Shift_2=get_mean_value(Shift, start22,end22)
    kmonitor22 = [Value_P2_2, Value_I1_2, Value_I2_2, Value_I3_2, Value_I4_2, Value_Shift_2]

    P2_clean=Value_P2-Value_Shift-Value_P2_2+Value_Shift_2+shutter[5]# clean background
    

    P2_coefficients=[Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[6],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[7],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[8],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[9] ]
   
    P2_coefficients=[x / P2_clean for x in P2_coefficients]
   

    shutter_open('3') # Measure the beam 3's outputs
    shutter_close('1')
    shutter_close('2')
    shutter_close('4')

    time.sleep(delay)

    [start31, end31]=define_time(delay)
    time.sleep(delay)

    Value_P3=get_mean_value(P3, start31,end31)
    Value_I1=get_mean_value(I1, start31,end31)
    Value_I2=get_mean_value(I2, start31,end31)
    Value_I3=get_mean_value(I3, start31,end31)
    Value_I4=get_mean_value(I4, start31,end31)
    Value_Shift=get_mean_value(Shift, start31,end31)
    kmonitor31 = [Value_P3, Value_I1, Value_I2, Value_I3, Value_I4, Value_Shift]

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    [start32, end32]=define_time(delay)
    time.sleep(delay)

    Value_P3_2=get_mean_value(P3, start32,end32)
    Value_I1_2=get_mean_value(I1, start32,end32)
    Value_I2_2=get_mean_value(I2, start32,end32)
    Value_I3_2=get_mean_value(I3, start32,end32)
    Value_I4_2=get_mean_value(I4, start32,end32)
    Value_Shift_2=get_mean_value(Shift, start32,end32)
    kmonitor32 = [Value_P3_2, Value_I1_2, Value_I2_2, Value_I3_2, Value_I4_2, Value_Shift_2]

    P3_clean=Value_P3-Value_Shift-Value_P3_2+Value_Shift_2+shutter[10]# clean background
   

    P3_coefficients=[Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[11],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[12],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[13],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[14] ]
    
    P3_coefficients=[x / P3_clean for x in P3_coefficients]
    

    shutter_open('4') # Measure the beam 4's outputs
    shutter_close('1')
    shutter_close('3')
    shutter_close('2')

    time.sleep(delay)
    [start41, end41]=define_time(delay)
    time.sleep(delay)

    Value_P4=get_mean_value(P4, start41,end41)
    Value_I1=get_mean_value(I1, start41,end41)
    Value_I2=get_mean_value(I2, start41,end41)
    Value_I3=get_mean_value(I3, start41,end41)
    Value_I4=get_mean_value(I4, start41,end41)
    Value_Shift=get_mean_value(Shift, start41,end41)
    kmonitor41 = [Value_P4, Value_I1, Value_I2, Value_I3, Value_I4, Value_Shift]

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    [start42, end42]=define_time(delay)
    time.sleep(delay)

    Value_P4_2=get_mean_value(P4, start42,end42)
    Value_I1_2=get_mean_value(I1, start42,end42)
    Value_I2_2=get_mean_value(I2, start42,end42)
    Value_I3_2=get_mean_value(I3, start42,end42)
    Value_I4_2=get_mean_value(I4, start42,end42)
    Value_Shift_2=get_mean_value(Shift, start42,end42)
    kmonitor42 = [Value_P4_2, Value_I1_2, Value_I2_2, Value_I3_2, Value_I4_2, Value_Shift_2]

    P4_clean=Value_P4-Value_Shift-Value_P4_2+Value_Shift_2+shutter[15]# clean background
    

    P4_coefficients=[Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[16],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[17],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[18],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[19] ]
    
    P4_coefficients=[x / P4_clean for x in P4_coefficients]
    
    

    shutdown()
    startend = [(start11, end11, start12, end12), 
                (start21, end21, start22, end22),
                (start31, end31, start32, end32),
                (start41, end41, start42, end42)]
    
    # startend = [[unix_time_ms(selt) for selt in elt] for elt in startend]

    

    P1_coefficients = np.array(P1_coefficients).reshape(-1, 1) #change line matrice into a column matrix
    P2_coefficients = np.array(P2_coefficients).reshape(-1, 1)
    P3_coefficients = np.array(P3_coefficients).reshape(-1, 1)
    P4_coefficients = np.array(P4_coefficients).reshape(-1, 1)

    Kappa_matrix = np.hstack((P1_coefficients, P2_coefficients, P3_coefficients, P4_coefficients)) #build kappa matrix

    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    folder_path = 'C:/Users/fys-lab-ivs/Desktop/monitoring/kappa matrice/Results/Kappa Matrix type 1'#save kappa matrix in a file

    os.makedirs(folder_path, exist_ok=True)

    filename = os.path.join(folder_path, f"Kappa_matrix_1_{current_time}.txt")

    with open(filename, 'w') as file:
        for row in Kappa_matrix:
            file.write(' '.join(map(str, row)) + '\n')

    kmoni01 = np.array([kmonitor11, kmonitor21, kmonitor31, kmonitor41])
    kmoni02 = np.array([kmonitor12, kmonitor22, kmonitor32, kmonitor42])

    return(Kappa_matrix)
                                
def Kappa_matrix_measurement_2(delay, shutter):# calculation of Kappa Matrix (Interferometric outputs depending of total beam outputs )
    global startend, time1
   
    P1='roi1_sum' # define all the ROI output
    P2='roi2_sum'
    I1='roi3_sum'
    I2='roi4_sum'
    I3='roi5_sum'
    I4='roi6_sum'
    P3='roi7_sum'
    P4='roi8_sum'
    Shift='roi9_sum'

    shutter_open('1') # Measure the beam 1's outputs
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    [(start11, end11, start12, end12), 
                    (start21, end21, start22, end22),
                    (start31, end31, start32, end32),
                    (start41, end41, start42, end42)] = time1
    
    time.sleep(delay)
    # [start11, end11]=define_time(delay)

    Value_P1=get_mean_value(P1, start11,end11)
    Value_I1=get_mean_value(I1, start11,end11)
    Value_I2=get_mean_value(I2, start11,end11)
    Value_I3=get_mean_value(I3, start11,end11)
    Value_I4=get_mean_value(I4, start11,end11)
    Value_Shift=get_mean_value(Shift, start11,end11)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    # [start12, end12]=define_time(delay)

    Value_P1_2=get_mean_value(P1, start12,end12)
    Value_I1_2=get_mean_value(I1, start12,end12)
    Value_I2_2=get_mean_value(I2, start12,end12)
    Value_I3_2=get_mean_value(I3, start12,end12)
    Value_I4_2=get_mean_value(I4, start12,end12)
    Value_Shift_2=get_mean_value(Shift, start12,end12)

    P1_clean=Value_P1-Value_Shift-Value_P1_2+Value_Shift_2+shutter[0]# clean background
   

    Sum1= P1_clean +Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+Value_I4-Value_Shift-Value_I4_2+Value_Shift_2 +shutter[1]+shutter[2]+shutter[3]+shutter[4]

    P1_coefficients=[P1_clean,0,Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[1],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[2],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[3],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2 +shutter[4],0,0]
   
    P1_coefficients=[x / Sum1 for x in P1_coefficients]
  

    shutter_open('2') # Measure the beam 2's outputs
    shutter_close('1')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)

    # [start21, end21]=define_time(delay)

    Value_P2=get_mean_value(P2, start21,end21)
    Value_I1=get_mean_value(I1, start21,end21)
    Value_I2=get_mean_value(I2, start21,end21)
    Value_I3=get_mean_value(I3, start21,end21)
    Value_I4=get_mean_value(I4, start21,end21)
    Value_Shift=get_mean_value(Shift, start21,end21)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')


    time.sleep(delay)
    # [start22, end22]=define_time(delay)

    Value_P2_2=get_mean_value(P2, start22,end22)
    Value_I1_2=get_mean_value(I1, start22,end22)
    Value_I2_2=get_mean_value(I2, start22,end22)
    Value_I3_2=get_mean_value(I3, start22,end22)
    Value_I4_2=get_mean_value(I4, start22,end22)
    Value_Shift_2=get_mean_value(Shift, start22,end22)

    P2_clean=Value_P2-Value_Shift-Value_P2_2+Value_Shift_2+shutter[5]# clean background
   
    Sum2= P2_clean + Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[6]+shutter[7]+shutter[8]+shutter[9]

    P2_coefficients=[0,P2_clean,Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[6],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[7],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[8],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2 +shutter[9],0,0]
    P2_coefficients=[x / Sum2 for x in P2_coefficients]
    

    shutter_open('3') # Measure the beam 3's outputs
    shutter_close('1')
    shutter_close('2')
    shutter_close('4')

    time.sleep(delay)

    # [start31, end31]=define_time(delay)

    Value_P3=get_mean_value(P3, start31,end31)
    Value_I1=get_mean_value(I1, start31,end31)
    Value_I2=get_mean_value(I2, start31,end31)
    Value_I3=get_mean_value(I3, start31,end31)
    Value_I4=get_mean_value(I4, start31,end31)
    Value_Shift=get_mean_value(Shift, start31,end31)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    # [start32, end32]=define_time(delay)

    Value_P3_2=get_mean_value(P3, start32,end32)
    Value_I1_2=get_mean_value(I1, start32,end32)
    Value_I2_2=get_mean_value(I2, start32,end32)
    Value_I3_2=get_mean_value(I3, start32,end32)
    Value_I4_2=get_mean_value(I4, start32,end32)
    Value_Shift_2=get_mean_value(Shift, start32,end32)

    P3_clean=Value_P3-Value_Shift-Value_P3_2+Value_Shift_2+shutter[10]# clean background
    
    Sum3= P3_clean + Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[11]+shutter[12]+shutter[13]+shutter[14]

    P3_coefficients=[0,0,Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[11],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[12],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[13],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[14],P3_clean,0 ]
    
    P3_coefficients=[x / Sum3 for x in P3_coefficients]
   

    shutter_open('4') # Measure the beam 4's outputs
    shutter_close('1')
    shutter_close('3')
    shutter_close('2')

    time.sleep(delay)

    # [start41, end41]=define_time(delay)

    Value_P4=get_mean_value(P4, start41,end41)
    Value_I1=get_mean_value(I1, start41,end41)
    Value_I2=get_mean_value(I2, start41,end41)
    Value_I3=get_mean_value(I3, start41,end41)
    Value_I4=get_mean_value(I4, start41,end41)
    Value_Shift=get_mean_value(Shift, start41,end41)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    # [start42, end42]=define_time(delay)

    Value_P4_2=get_mean_value(P4, start42,end42)
    Value_I1_2=get_mean_value(I1, start42,end42)
    Value_I2_2=get_mean_value(I2, start42,end42)
    Value_I3_2=get_mean_value(I3, start42,end42)
    Value_I4_2=get_mean_value(I4, start42,end42)
    Value_Shift_2=get_mean_value(Shift, start42,end42)

    P4_clean=Value_P4-Value_Shift-Value_P4_2+Value_Shift_2+shutter[15]# clean background

    Sum4= P4_clean + Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+Value_I4-Value_Shift-Value_I4_2+Value_Shift_2  +shutter[16]+shutter[17]+shutter[18]+shutter[19] 

    P4_coefficients=[0,0,Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[16],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[17],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[18],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[19],0,P4_clean ]
  
    P4_coefficients=[x / Sum4 for x in P4_coefficients]
   

    shutdown()
    
    startend = [(start11, end11, start12, end12), 
                (start21, end21, start22, end22),
                (start31, end31, start32, end32),
                (start41, end41, start42, end42)]
    startend = [(unix_time_ms(selt) for selt in elt) for elt in startend]



    P1_coefficients = np.array(P1_coefficients).reshape(-1, 1)
    P2_coefficients = np.array(P2_coefficients).reshape(-1, 1)
    P3_coefficients = np.array(P3_coefficients).reshape(-1, 1)
    P4_coefficients = np.array(P4_coefficients).reshape(-1, 1)

    Kappa_matrix = np.hstack((P1_coefficients, P2_coefficients, P3_coefficients, P4_coefficients))

    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    folder_path = 'C:/Users/fys-lab-ivs/Desktop/monitoring/kappa matrice/Results/Kappa Matrix type 2'

    os.makedirs(folder_path, exist_ok=True)

    filename = os.path.join(folder_path, f"Kappa_matrix_2_{current_time}.txt")

    with open(filename, 'w') as file:
        for row in Kappa_matrix:
            file.write(' '.join(map(str, row)) + '\n')

    return(Kappa_matrix)#, P1_clean/Sum1, P2_clean/Sum2, P3_clean/Sum3,P4_clean/Sum4)


def measure_visibility(n, shutter): # measure visibility: n= nuller number, shutter= shutter radiation

    min1=1000 #um #define range for each delay line
    max1=6000
    min2=1000
    max2=3000
    min3=1000
    max3=5000
    min4=1000
    max4=9000

    startup()#Open shutters
 
    speed =100 #um/s #define speed of delay lines 

    if n==1:#nuller 1 # interferences between beam 1 and 2


        ini_pos_1=read_current_pos('nott_ics.Delay_Lines.NDL1')#um
        ini_pos_2=read_current_pos('nott_ics.Delay_Lines.NDL2')

        move_abs_dl((ini_pos_1+min1)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL1') #move dl to the min position #travel decomposed in two time bc if it is too long there are errors on the final position and can block the porgram bc it never detects that the dl is at the target position
        time.sleep(0.1)
        move_abs_dl( (min1)*0.001,speed*0.001,'nott_ics.Delay_Lines.NDL1')
        time.sleep(0.1)
        move_abs_dl((ini_pos_2+min2)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL2')
        time.sleep(0.1)
        move_abs_dl( (min2)*0.001,speed*0.001,'nott_ics.Delay_Lines.NDL2')
      

        time.sleep(0.1)
    
        move_abs_dl((max1+min1)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL1') #scan all the range for the first Dl
        time.sleep(0.1)
        move_abs_dl(max1*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL1')

        [start,end]=define_time((max1-min1)/speed+10) #define the period during the scan
        

        [position, Values]=get_position('DL_1_pos', 'roi3_max', start, end) #Get values and DL position during the scan
        [position_2,shift]= get_position('DL_1_pos', 'roi9_avg', start, end) #get shift value #background from other roi (ambient drift)
        Values=np.array(Values)
        shift=np.array(shift)
        Values=Values[5:]
        shift=shift[5:]
        Values_corrected=np.array(Values)#values corrected of shift and the loss of flux bc of misalignment when the Dl are moving to detect fringes
        position=np.array(position)
        position_2=np.array(position_2)
        position=position[5:]
        position_2=position_2[5:]
   

        DL=1 #define that is Dl1 wich has travelled 

        model = LinearRegression() #fit the shift to a linear fonction ax+b
        model.fit(position_2.reshape(-1, 1), shift)
        shift = model.predict(position_2.reshape(-1, 1)) 

        for i in range(len(Values)): #remove the shift to the flux measures
            Values_corrected[i]=Values[i]-shift[i]+shift[0]

        p = np.polyfit(position, Values_corrected, 3) #fit the loss of flux bc of misalignment when the Dl are moving to a polynomial function third degrees 
        align = np.polyval(p, position)

        for i in range(len(Values)): #remove the loss of flux bc of misalignment
            Values_corrected[i]=Values_corrected[i]/align[i]


        idx_min= np.argmin(Values_corrected) #get the index of Imax in fringes
        idx_max= np.argmax(Values_corrected) #get the index of Imin in fringes

        Imax=Values[idx_max] #recup Imax value, Imin value and position of Imin
        Imin=Values[idx_min]
        pos_min=position[idx_min]
        pos_max=position[idx_max]


        if abs(pos_max-pos_min)>100:#if envelope not detected it does the same thing for the other dl

            ini_pos_1=read_current_pos('nott_ics.Delay_Lines.NDL1')#um
            ini_pos_2=read_current_pos('nott_ics.Delay_Lines.NDL2')

            move_abs_dl((ini_pos_1+min1)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL1') #move dl to the min position #travel decomposed in two time bc if it is too long there are errors on the final position and can block the porgram bc it never detects that the dl is at the target position
            time.sleep(0.1)
            move_abs_dl( (min1)*0.001,speed*0.001,'nott_ics.Delay_Lines.NDL1')
            time.sleep(0.1)
            move_abs_dl((ini_pos_2+min2)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL2')
            time.sleep(0.1)
            move_abs_dl( (min2)*0.001,speed*0.001,'nott_ics.Delay_Lines.NDL2')
            
            time.sleep(0.1)

            move_abs_dl((max2+min2)*0.001/4, speed*0.001,'nott_ics.Delay_Lines.NDL2')#scan all the range
            time.sleep(0.1)
            move_abs_dl((max2+min2)*0.001/2,speed*0.001,'nott_ics.Delay_Lines.NDL2')
            time.sleep(0.1)
            move_abs_dl((max2+min2)*0.001*3/4, speed*0.001,'nott_ics.Delay_Lines.NDL2')
            time.sleep(0.1)
            move_abs_dl(max2*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL2')

            [start,end]=define_time((max2-min2)/speed)

            [position, Values]=get_position('DL_2_pos', 'roi3_max', start, end) #Get values and DL position during the scan
            [position_2,shift]= get_position('DL_2_pos', 'roi9_avg', start, end) #get shift value
            Values=np.array(Values)
            shift=np.array(shift)
            Values=Values[5:]
            shift=shift[5:]
            Values_corrected=np.array(Values)
            position=np.array(position)
            position_2=np.array(position_2)
            position=position[5:]
            position_2=position_2[5:]

            DL=2


            model = LinearRegression()
            model.fit(position_2.reshape(-1, 1), shift)
            shift = model.predict(position_2.reshape(-1, 1))

            for i in range(len(Values)):
                Values_corrected[i]=Values[i]-shift[i]+shift[0]

            p = np.polyfit(position, Values_corrected, 3)
            align = np.polyval(p, position)

            for i in range(len(Values)):
                Values_corrected[i]=Values_corrected[i]/align[i]


            idx_min= np.argmin(Values_corrected)
            idx_max= np.argmax(Values_corrected)

            Imax=Values[idx_max] #recup Imax value, Imin value and position of Imin
            Imin=Values[idx_min]

            pos_min=position[idx_min]
            pos_max=position[idx_max]

       
        

        shutdown() #close shutters to take background

        delay=2
        time.sleep(delay)
        [start,end]=define_time(delay)

        background=get_mean_value('roi3_avg', start, end)#take background, ie mean of pixel values and mean of this value during delay
        shift_2=get_mean_value('roi9_avg', start, end)#get shift value when the background is taken
    
        startup()#Open shutters

        Imax=Imax-background+shift_2-shift[idx_max]+shutter[1]+shutter[6]#remove background and shift and shutter radiation
        Imin=Imin-background+shift_2-shift[idx_min]+shutter[1]+shutter[6]


        Visibility=(Imax-Imin)/(Imax+Imin) #calcul visibility

        max=read_current_pos(f'nott_ics.Delay_Lines.NDL{DL}')
        move_abs_dl(((max+pos_max))*0.001/2, speed*0.001,f'nott_ics.Delay_Lines.NDL{DL}') #Go to the fringes positions
        time.sleep(0.1)
        move_abs_dl(pos_max*0.001, speed*0.001,f'nott_ics.Delay_Lines.NDL{DL}') #Go to the fringes positions



    elif n==2: #same as for nuller 1 but for nuller2 #between beam 3 and 4

        ini_pos_1=read_current_pos('nott_ics.Delay_Lines.NDL3')#um
        ini_pos_2=read_current_pos('nott_ics.Delay_Lines.NDL4')

    
        move_abs_dl((ini_pos_1+min3)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL3')
        time.sleep(0.1)
        move_abs_dl( min3*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL3')
        time.sleep(0.1)
        move_abs_dl((ini_pos_2+min4)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL4')
        time.sleep(0.1)
        move_abs_dl(min4*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL4')
            
        time.sleep(0.1)
        
        move_abs_dl((max3+min3)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL3')
        move_abs_dl(max3*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL3')

        [start,end]=define_time((max3-min3)/speed)


        [position, Values]=get_position('DL_3_pos', 'roi6_max', start, end) #Get values and DL position during the scan
        [position_2,shift]= get_position('DL_3_pos', 'roi9_avg', start, end) #get shift value
        Values=np.array(Values)
        shift=np.array(shift)
        Values=Values[5:]
        shift=shift[5:]
        Values_corrected=np.array(Values)
        position=np.array(position)
        position_2=np.array(position_2)
        position=position[5:]
        position_2=position_2[5:]
        DL=3

        idx_min= np.argmin(Values)
        idx_max= np.argmax(Values)

        model = LinearRegression()
        model.fit(position_2.reshape(-1, 1), shift)
        shift = model.predict(position_2.reshape(-1, 1))

        for i in range(len(Values)):
            Values_corrected[i]=Values[i]-shift[i]+shift[0]


        p = np.polyfit(position, Values_corrected, 3)
        align = np.polyval(p, position)

        for i in range(len(Values)):
            Values_corrected[i]=Values_corrected[i]/align[i]


        idx_min= np.argmin(Values_corrected)
        idx_max= np.argmax(Values_corrected)

        Imax=Values[idx_max] #recup Imax value, Imin value and position of Imin
        Imin=Values[idx_min]

        pos_min=position[idx_min]
        pos_max=position[idx_max]


        if abs(pos_max-pos_min)>100:#if envelope not detected 

            ini_pos_1=read_current_pos('nott_ics.Delay_Lines.NDL3')#um
            ini_pos_2=read_current_pos('nott_ics.Delay_Lines.NDL4')

            move_abs_dl((ini_pos_1+min3)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL3')
            time.sleep(0.1)
            move_abs_dl( min3*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL3')
            time.sleep(0.1)
            move_abs_dl((ini_pos_2+min4)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL4')
            time.sleep(0.1)
            move_abs_dl(min4*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL4')
                
            time.sleep(0.1)
            
            move_abs_dl((max4+min4)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL4')
            time.sleep(0.1)
            move_abs_dl(max4*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL4')


            [start,end]=define_time((max4-min4)/speed)


            [position, Values]=get_position('DL_4_pos', 'roi6_max', start, end) #Get values and DL position during the scan
            [position_2,shift]= get_position('DL_4_pos', 'roi9_avg', start, end) #get shift value
            Values=np.array(Values)
            shift=np.array(shift)
            Values=Values[5:]
            shift=shift[5:]
            Values_corrected=np.array(Values)
            position=np.array(position)
            position_2=np.array(position_2)
            position=position[5:]
            position_2=position_2[5:]
            DL=4

            model = LinearRegression()
            model.fit(position_2.reshape(-1, 1), shift)
            shift = model.predict(position_2.reshape(-1, 1))

            for i in range(len(Values)):
                Values_corrected[i]=Values[i]-shift[i]+shift[0]

            p = np.polyfit(position, Values_corrected, 3)
            align = np.polyval(p, position)

            for i in range(len(Values)):
                Values_corrected[i]=Values_corrected[i]/align[i]


            idx_min= np.argmin(Values_corrected)
            idx_max= np.argmax(Values_corrected)

            Imax=Values[idx_max] #recup Imax value, Imin value and position of Imin
            Imin=Values[idx_min]

            pos_min=position[idx_min]
            pos_max=position[idx_max]

        shutdown() #close shutters to take background

        delay=2
        time.sleep(delay)
        [start,end]=define_time(delay)

        background=get_mean_value('roi6_avg', start, end)#take background, ie mean of pixel values and mean of this value during delay
        shift_2=get_mean_value('roi9_avg', start, end)#get shift value
    
        startup()#Open shutters

        Imax=Imax-background+shift_2-shift[idx_max]+shutter[14]+shutter[19]#remove background, shift and shutter's radiation
        Imin=Imin-background+shift_2-shift[idx_min]+shutter[14]+shutter[19]


        Visibility=(Imax-Imin)/(Imax+Imin) #calcul visibility

        max=read_current_pos(f'nott_ics.Delay_Lines.NDL{DL}')
        move_abs_dl((max+pos_max)*0.001/2, speed*0.001,f'nott_ics.Delay_Lines.NDL{DL}') #Go at the fringes positions
        time.sleep(0.1)
        move_abs_dl(pos_max*0.001, speed*0.001,f'nott_ics.Delay_Lines.NDL{DL}') #Go at the fringes positions
 
 

    elif n==3: #measure vivibility for the third nuller (between beam 2 and 3) and go to the null #need to be at the null position for the first and second nuller

        shutter_close('1') #close beam 1 and 4 to not have interferences in the forst and second nuller
        shutter_close('4')

        ini_pos_1=read_current_pos('nott_ics.Delay_Lines.NDL1')#um #get the initial position where we have fringes for the first and second nuller
        ini_pos_2=read_current_pos('nott_ics.Delay_Lines.NDL2')
        ini_pos_3=read_current_pos('nott_ics.Delay_Lines.NDL3')
        ini_pos_4=read_current_pos('nott_ics.Delay_Lines.NDL4')

        diff_1=ini_pos_1-ini_pos_2 #save difference between beams to have fringes
        diff_2=ini_pos_4-ini_pos_3

    
        move_abs_dl((ini_pos_2+min2)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL2')#go to the min position for the two delay lines
        time.sleep(0.1)
        move_abs_dl( min2*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL2')
        time.sleep(0.1)
        move_abs_dl((ini_pos_3+min3)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL3')
        time.sleep(0.1)
        move_abs_dl(min3*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL3')
    
        time.sleep(0.1)
            
        move_abs_dl((max2+min2)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL2')#scan for one dl
        time.sleep(0.1)
        move_abs_dl(max2*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL2')

        [start,end]=define_time((max2-min2)/speed+10)


        [position, Values]=get_position('DL_2_pos', 'roi4_max', start, end) #Get values and DL position during the scan
        [position_2,shift]= get_position('DL_2_pos', 'roi9_avg', start, end) #get shift value
        Values=np.array(Values)
        shift=np.array(shift)
        Values=Values[5:]
        shift=shift[5:]
        Values_corrected=np.array(Values)
        position=np.array(position)
        position_2=np.array(position_2)
        position=position[5:]
        position_2=position_2[5:]

        DL=2 #set the delay line which have travelled

        model = LinearRegression()
        model.fit(position_2.reshape(-1, 1), shift)
        shift = model.predict(position_2.reshape(-1, 1))

        for i in range(len(Values)):
            Values_corrected[i]=Values[i]-shift[i]+shift[0]

        p = np.polyfit(position, Values_corrected, 3)
        align = np.polyval(p, position)

        for i in range(len(Values)):
            Values_corrected[i]=Values_corrected[i]/align[i]


        idx_min= np.argmin(Values_corrected)
        idx_max= np.argmax(Values_corrected)

        Imax=Values[idx_max] #recup Imax value, Imin value and position of Imin
        Imin=Values[idx_min]

        pos_min=position[idx_min]
        pos_max=position[idx_max]

        if abs(pos_max-pos_min)>100:#if envelope not detected it does the same for the other dl
            
            shutter_close('1') #close beam 1 and 4 to not have interferences in the forst and second nuller
            shutter_close('4')

            ini_pos_2=read_current_pos('nott_ics.Delay_Lines.NDL2')#um
            ini_pos_3=read_current_pos('nott_ics.Delay_Lines.NDL3')
        
            move_abs_dl((ini_pos_2+min2)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL2')
            time.sleep(0.1)
            move_abs_dl( min2*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL2')
            time.sleep(0.1)
            move_abs_dl((ini_pos_3+min3)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL3')
            time.sleep(0.1)
            move_abs_dl(min3*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL3')
        
            time.sleep(0.1)
                
            move_abs_dl((max3+min3)*0.001/2, speed*0.001,'nott_ics.Delay_Lines.NDL3')
            time.sleep(0.1)
            move_abs_dl(max3*0.001, speed*0.001,'nott_ics.Delay_Lines.NDL3')

            [start,end]=define_time((max3-min3)/speed+10)


            [position, Values]=get_position('DL_3_pos', 'roi4_max', start, end) #Get values and DL position during the scan
            [position_2,shift]= get_position('DL_3_pos', 'roi9_avg', start, end) #get shift value
            Values=np.array(Values)
            shift=np.array(shift)
            Values=Values[5:]
            shift=shift[5:]
            Values_corrected=np.array(Values)
            position=np.array(position)
            position_2=np.array(position_2)
            position=position[5:]
            position_2=position_2[5:]

            
            position=np.array(position)
            DL=3

            model = LinearRegression()
            model.fit(position_2.reshape(-1, 1), shift)
            shift = model.predict(position_2.reshape(-1, 1))

            for i in range(len(Values)):
                Values_corrected[i]=Values[i]-shift[i]+shift[0]

            p = np.polyfit(position, Values_corrected, 3)
            align = np.polyval(p, position)

            for i in range(len(Values)):
                Values_corrected[i]=Values_corrected[i]/align[i]


            idx_min= np.argmin(Values_corrected)
            idx_max= np.argmax(Values_corrected)

            Imax=Values[idx_max] #recup Imax value, Imin value and position of Imin
            Imin=Values[idx_min]

            pos_min=position[idx_min]
            pos_max=position[idx_max] 

        shutdown() #close shutters to take background

        delay=2
        time.sleep(delay)
        [start,end]=define_time(delay)

        background=get_mean_value('roi4_avg', start, end)#take background, ie mean of pixel values and mean of this value during delay
        shift_2=get_mean_value('roi9_avg', start, end)#get shift value
    
        startup()#Open shutters

        if DL==2:#get difference between dl 1 and dl2 to have fringes
            diff_3=pos_min-min3
        else:
            diff_3=min2-pos_min

        Imax=Imax-background+shift_2-shift[idx_max]+shutter[2]+shutter[7]+shutter[12]+shutter[17]#remove background, shift and shutter's radiation
        Imin=Imin-background+shift_2-shift[idx_min]+shutter[2]+shutter[7]+shutter[12]+shutter[17]


        Visibility=(Imax-Imin)/(Imax+Imin) #calcul visibility

        move_abs_dl(1000*0.001, speed*0.001,f'nott_ics.Delay_Lines.NDL2') #Go at the midle of the range to be free to move the other delay lines around this position to have interferences
        time.sleep(0.1)

        if min3<(max2+min2)/2-diff_3<max3: #if fringes position is in the range of the dl
            move_abs_dl((max2+min2)*0.001/2-diff_3*0.001, speed*0.001,f'nott_ics.Delay_Lines.NDL3') #Go to the fringes positions
        else:
            plt.figure(figsize=(10, 6))
            plt.plot(position, Values, label='values')
            plt.scatter(pos_min, Values[idx_min])
            plt.scatter(pos_max, Values[idx_max])
            plt.legend()
            plt.show()
            return(f'Out of range for DL3: {(max2+min2)/2-diff_3}')
  
        time.sleep(0.1)
        
        fringes_1=read_current_pos('nott_ics.Delay_Lines.NDL2')+diff_1 #define position for DL1 and dl4 to have fringes in the two first nuller
        fringes_2=read_current_pos('nott_ics.Delay_Lines.NDL3')+diff_2

        if min1<=fringes_1<=max1 and min4<=fringes_2<=max4 :#if fringes positions are in the range of the dl
            move_abs_dl(fringes_1*0.001, speed*0.001,f'nott_ics.Delay_Lines.NDL1') #Go at the fringes positions for the firsl nuller
            move_abs_dl(fringes_2*0.001, speed*0.001,f'nott_ics.Delay_Lines.NDL4') #Go at the fringes positions for the second nuller
        else:
            plt.figure(figsize=(10, 6))
            plt.plot(position, Values, label='values')
            plt.scatter(pos_min, Values[idx_min])
            plt.scatter(pos_max, Values[idx_max])
            plt.legend()
            plt.show()
            return(f'Out of range for DL1: {fringes_1} or DL2:{fringes_2}')

    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    folder_path = 'C:/Users/fys-lab-ivs/Desktop/monitoring/fringes position' #save visibility and dl position in a file

    os.makedirs(folder_path, exist_ok=True)

    filename = os.path.join(folder_path, f"Fringes_position_{n}_{current_time}.txt")

    with open(filename, 'w') as file:
        file.write(f"nuller {n}\n")

    with open(filename, 'a') as file:
        file.write("Delay line 1\n")
        
    with open(filename, 'a') as file:
        file.write(f"position[um] {read_current_pos('nott_ics.Delay_Lines.NDL1')}\n")

    with open(filename, 'a') as file:
        file.write("Delay line 2\n")

    with open(filename, 'a') as file:
        file.write(f"position[um] {read_current_pos('nott_ics.Delay_Lines.NDL2')}\n")

    with open(filename, 'a') as file:
        file.write("Delay line 3\n")

    with open(filename, 'a') as file:
        file.write(f"position[um] {read_current_pos('nott_ics.Delay_Lines.NDL3')}\n")

    with open(filename, 'a') as file:
        file.write("Delay line 4\n")

    with open(filename, 'a') as file:
        file.write(f"position[um] {read_current_pos('nott_ics.Delay_Lines.NDL4')}\n")

    with open(filename, 'a') as file:
        file.write(f"Visibility {str(Visibility)}\n")

    plt.figure(figsize=(10, 6))
    plt.plot(position, Values, label='values')
    #plt.plot(position, Values_corrected, label='values corrected')
    plt.scatter(pos_min, Values[idx_min])
    plt.scatter(pos_max, Values[idx_max])
    plt.legend()
    plt.show()

    return(Visibility)


def shutter_radiation(delay): #measure shutter radiation. You must not have light from source
    global startend_shutter
    global monitor11, monitor12, monitor21, monitor22, monitor31, monitor32, monitor41, monitor42
    global moni01, moni02
    global time2
    global zorg

    P1='roi1_sum' # define all the ROI output
    P2='roi2_sum'
    I1='roi3_sum'
    I2='roi4_sum'
    I3='roi5_sum'
    I4='roi6_sum'
    P3='roi7_sum'
    P4='roi8_sum'
    Shift='roi9_sum'

    startup()
    time.sleep(0.1)
    shutter_close('1') #measure shutter 1 radiation

    # [(start11, end11, start12, end12), 
    # (start21, end21, start22, end22),
    # (start31, end31, start32, end32),
    # (start41, end41, start42, end42)] = time2

    time.sleep(delay)
    [start11, end11]=define_time(delay)
    time.sleep(delay)

    Value_P1_S1=get_mean_value(P1, start11,end11) #get values in each output of the shutter radiation
    Value_I1_S1=get_mean_value(I1, start11,end11)
    Value_I2_S1=get_mean_value(I2, start11,end11)
    Value_I3_S1=get_mean_value(I3, start11,end11)
    Value_I4_S1=get_mean_value(I4, start11,end11)
    Value_Shift=get_mean_value(Shift, start11,end11)

    monitor11 = [Value_P1_S1, Value_I1_S1, Value_I2_S1, Value_I3_S1, Value_I4_S1, Value_Shift]

    shutter_open('1')
    time.sleep(delay)
    [start12, end12]=define_time(delay)
    time.sleep(delay)

    Value_P1_2_S1=get_mean_value(P1, start12,end12)#get background
    Value_I1_2_S1=get_mean_value(I1, start12,end12)
    Value_I2_2_S1=get_mean_value(I2, start12,end12)
    Value_I3_2_S1=get_mean_value(I3, start12,end12)
    Value_I4_2_S1=get_mean_value(I4, start12,end12)
    Value_Shift_2=get_mean_value(Shift, start12,end12)

    output1 = get_field(P1, start12,end12)
    plaf = sum(output1) / len(output1)
    output2 = get_field(P1, start12,end12)
    plaf2 = sum(output2) / len(output2)

    print('!!!!!! Shutter 1 bckg P1', datetime.fromtimestamp(start12/1000), start12, end12, Value_P1_2_S1, plaf, plaf2)
    zorg = [P1, start12,end12, Value_P1_2_S1]

    monitor12 = [Value_P1_2_S1, Value_I1_2_S1, Value_I2_2_S1, Value_I3_2_S1, Value_I4_2_S1, Value_Shift_2]

    Shutter1=[Value_P1_S1-Value_Shift-Value_P1_2_S1+Value_Shift_2,Value_I1_S1-Value_Shift-Value_I1_2_S1+Value_Shift_2,Value_I2_S1-Value_Shift-Value_I2_2_S1+Value_Shift_2,Value_I3_S1-Value_Shift-Value_I3_2_S1+Value_Shift_2,Value_I4_S1-Value_Shift-Value_I4_2_S1+Value_Shift_2]
    #put values in a matrix [P1,I1,I2,I3,I4]

    shutter_close('2')# shutter 2 radiation

    time.sleep(delay)
    [start21, end21]=define_time(delay)
    time.sleep(delay)

    Value_P2_S2=get_mean_value(P2, start21,end21)
    Value_I1_S2=get_mean_value(I1, start21,end21)
    Value_I2_S2=get_mean_value(I2, start21,end21)
    Value_I3_S2=get_mean_value(I3, start21,end21)
    Value_I4_S2=get_mean_value(I4, start21,end21)
    Value_Shift=get_mean_value(Shift, start21,end21)
    monitor21 = [Value_P2_S2, Value_I1_S2, Value_I2_S2, Value_I3_S2, Value_I4_S2, Value_Shift]

    shutter_open('2')

    time.sleep(delay)
    [start22, end22]=define_time(delay)
    time.sleep(delay)

    Value_P2_2_S2=get_mean_value(P2, start22,end22)
    Value_I1_2_S2=get_mean_value(I1, start22,end22)
    Value_I2_2_S2=get_mean_value(I2, start22,end22)
    Value_I3_2_S2=get_mean_value(I3, start22,end22)
    Value_I4_2_S2=get_mean_value(I4, start22,end22)
    Value_Shift_2=get_mean_value(Shift, start22,end22)
    monitor22 = [Value_P2_2_S2, Value_I1_2_S2, Value_I2_2_S2, Value_I3_2_S2, Value_I4_2_S2, Value_Shift_2]

    Shutter2=[Value_P2_S2-Value_Shift-Value_P2_2_S2+Value_Shift_2,Value_I1_S2-Value_Shift-Value_I1_2_S2+Value_Shift_2,Value_I2_S2-Value_Shift-Value_I2_2_S2+Value_Shift_2,Value_I3_S2-Value_Shift-Value_I3_2_S2+Value_Shift_2,Value_I4_S2-Value_Shift-Value_I4_2_S2+Value_Shift_2]
    #[P2,I1,I2,I3,I4]
    shutter_close('3') #shutter 3 radiation

    time.sleep(delay)
    [start31, end31]=define_time(delay)
    time.sleep(delay)

    Value_P3_S3=get_mean_value(P3, start31,end31)
    Value_I1_S3=get_mean_value(I1, start31,end31)
    Value_I2_S3=get_mean_value(I2, start31,end31)
    Value_I3_S3=get_mean_value(I3, start31,end31)
    Value_I4_S3=get_mean_value(I4, start31,end31)
    Value_Shift=get_mean_value(Shift, start31,end31)
    monitor31 = [Value_P3_S3, Value_I1_S3, Value_I2_S3, Value_I3_S3, Value_I4_S3, Value_Shift]

    shutter_open('3')

    time.sleep(delay)
    [start32, end32]=define_time(delay)
    time.sleep(delay)

    Value_P3_2_S3=get_mean_value(P3, start32,end32)
    Value_I1_2_S3=get_mean_value(I1, start32,end32)
    Value_I2_2_S3=get_mean_value(I2, start32,end32)
    Value_I3_2_S3=get_mean_value(I3, start32,end32)
    Value_I4_2_S3=get_mean_value(I4, start32,end32)
    Value_Shift_2=get_mean_value(Shift, start32,end32)
    monitor32 = [Value_P3_2_S3, Value_I1_2_S3, Value_I2_2_S3, Value_I3_2_S3, Value_I4_2_S3, Value_Shift_2]

    Shutter3=[Value_P3_S3-Value_Shift-Value_P3_2_S3+Value_Shift_2,Value_I1_S3-Value_Shift-Value_I1_2_S3+Value_Shift_2,Value_I2_S3-Value_Shift-Value_I2_2_S3+Value_Shift_2,Value_I3_S3-Value_Shift-Value_I3_2_S3+Value_Shift_2,Value_I4_S3-Value_Shift-Value_I4_2_S3+Value_Shift_2]
    #[P3,I1,I2,I3,I4]

    shutter_close('4') #shutter 4 radiation

    time.sleep(delay)
    [start41, end41]=define_time(delay)
    time.sleep(delay)

    Value_P4_S4=get_mean_value(P4, start41,end41)
    Value_I1_S4=get_mean_value(I1, start41,end41)
    Value_I2_S4=get_mean_value(I2, start41,end41)
    Value_I3_S4=get_mean_value(I3, start41,end41)
    Value_I4_S4=get_mean_value(I4, start41,end41)
    Value_Shift=get_mean_value(Shift, start41,end41)
    monitor41 = [Value_P4_S4, Value_I1_S4, Value_I2_S4, Value_I3_S4, Value_I4_S4, Value_Shift]

    shutter_open('4')

    time.sleep(delay)
    [start42, end42]=define_time(delay)
    time.sleep(delay)

    Value_P4_2_S4=get_mean_value(P4, start42,end42)
    Value_I1_2_S4=get_mean_value(I1, start42,end42)
    Value_I2_2_S4=get_mean_value(I2, start42,end42)
    Value_I3_2_S4=get_mean_value(I3, start42,end42)
    Value_I4_2_S4=get_mean_value(I4, start42,end42)
    Value_Shift_2=get_mean_value(Shift, start42,end42)
    monitor42 = [Value_P4_2_S4, Value_I1_2_S4, Value_I2_2_S4, Value_I3_2_S4, Value_I4_2_S4, Value_Shift_2]

    Shutter4=[Value_P4_S4-Value_Shift-Value_P4_2_S4+Value_Shift_2,Value_I1_S4-Value_Shift-Value_I1_2_S4+Value_Shift_2,Value_I2_S4-Value_Shift-Value_I2_2_S4+Value_Shift_2,Value_I3_S4-Value_Shift-Value_I3_2_S4+Value_Shift_2,Value_I4_S4-Value_Shift-Value_I4_2_S4+Value_Shift_2]
    #[P4,I1,I2,I3,I4]
    
    startend_shutter = [(start11, end11, start12, end12), 
                        (start21, end21, start22, end22),
                        (start31, end31, start32, end32),
                        (start41, end41, start42, end42)]
    
    startup()
    
    moni01 = np.array([monitor11, monitor21, monitor31, monitor41])
    moni02 = np.array([monitor12, monitor22, monitor32, monitor42])
    
    return (Shutter1+ Shutter2+ Shutter3+ Shutter4) #return [P1,I1,I2,I3,I4,P2,I1,I2,I3,I4,P3,I1,I2,I3,I4,P4,I1,I2,I3,I4]



#Variance Kappa Matrix
'''
shutter=shutter_radiation(2)
print(shutter)
time.sleep(15)
a=Kappa_matrix_measurement_2(2,shutter)
b=Kappa_matrix_measurement_2(2,shutter)
c=Kappa_matrix_measurement_2(2,shutter)
d=Kappa_matrix_measurement_2(2,shutter)
e=Kappa_matrix_measurement_2(2,shutter)

matrice_v = [[0 for _ in range(4)] for _ in range(8)]
matrice_m = [[0 for _ in range(4)] for _ in range(8)]

for i in range (8):
    for j in range (4):
        scalars = np.array([a[i][j], b[i][j], c[i][j], d[i][j],e[i][j]])
        variance = np.var(scalars)
        mean=np.mean(scalars)
        matrice_v[i] [j] = variance
        matrice_m[i] [j] = mean
        

print("Kappa Matrice mean",matrice_m)
print('Kappa Matrice var', matrice_v)
'''

#measure vivibility
'''
n=3
delay=2
shutter=shutter_radiation(delay)
print(shutter)
time.sleep(15) #15 to reopen the source
print(measure_visibility(n, shutter))
'''

#startup()   #Open all shutters
#shutdown()  #Close all shutters
#time.sleep(0.1)
#shutter_open('2') # Measure the beam 1's outputs
#shutter_close('2')

# =============================================================================
# MAM
# =============================================================================
import time
from datetime import datetime, timedelta
import nott_control

def get_field2(field, start, end, return_avg, db_address='redis://nott-server.ster.kuleuven.be:6379'):
    """
    Get the data in the database of the required `field` in a time range limited by `start` and `end`.
    The returned object is a 2D-array which rows are the datapoints, the first column is the timestamp
    and the 2nd column is the value of `field`.

    Parameters
    ----------
    field : str
        Field of the database to colect.
    start : int
        start timestamp in milliseconds. The timezone must be the one of the server.
    end : int
        end timestamp in milliseconds. The timezone must be the one of the server.
    return_avg: bool
        Return the average value on the number of points.
    db_address : str, optional
        Address of the database. The default is 'redis://nott-server.ster.kuleuven.be:6379'.

    Returns
    -------
    output : 2d-array
        Output of the required field from the database.

    """
    # Read data
    r = redis.from_url(db_address)

    # Extract data
    ts = r.ts()

     # Get ROI values
    output = ts.range(field, start, end) # This function returns a list of tuples
    output = np.array(output) # Array

    if return_avg:
        output = output.mean(0) # Average along the number of points axis

    return  output

    
def build_kappa_matrix(delay, shutter_radiation, n_aper, fields, return_throughput):
    global time1, startend
    global kmonitor01, kmonitor02

    # startend = time1
    
    kappa_mat = []
    beams_pos_in_output = [0, 1, 6, 7]
    kmonitor01 = []
    kmonitor02 = []

    for sh in range(n_aper):
        # Measure of the bias induced by the shutters and measure the flux on the outputs of the chip
        nott_control.all_shutters_close(n_aper)

        time.sleep(delay)
        # end = datetime.fromtimestamp(time.time())
        # start = end - timedelta(seconds=delay)
        time.sleep(delay)
        
        start = startend[sh][2]
        end = startend[sh][3]
        
        fluxes_shutters_closed = [get_field2(elt, start, end, True)[1] for elt in fields]
        fluxes_shutters_closed = np.array(fluxes_shutters_closed)

        kmonitor02.append(fluxes_shutters_closed[[beams_pos_in_output[sh], 2, 3, 4, 5, -1]])


        shift_shutters_closed = fluxes_shutters_closed[-1]
        fluxes_shutters_closed = fluxes_shutters_closed[:-1]
        
        # Open one shutter and measure the flux on the outputs of the chip
        print('Open shutter', sh+1, '...')
        shutter_open(str(sh+1))
        time.sleep(delay)
        # end = datetime.fromtimestamp(time.time())
        # start = end - timedelta(seconds=delay)        
        start = startend[sh][0]
        end = startend[sh][1]      
        time.sleep(delay)

        fluxes = [get_field2(elt, start, end, True)[1] for elt in fields]
        fluxes = np.array(fluxes)

        kmonitor01.append(fluxes[[beams_pos_in_output[sh], 2, 3, 4, 5, -1]])

        shift = fluxes[-1]
        fluxes = fluxes[:-1]
        
        kappa_col = fluxes - shift - (fluxes_shutters_closed - shift_shutters_closed) + shutter_radiation[sh]
        
        if return_throughput:
            kappa_col /= kappa_col.sum()
        else:
            kappa_col /= kappa_col[beams_pos_in_output[sh]]
            
        kappa_mat.append(kappa_col)
        
    kappa_mat = np.array(kappa_mat)
    kappa_mat = kappa_mat.T
    
    nott_control.all_shutters_close(n_aper)

    kmonitor01 = np.array(kmonitor01)
    kmonitor02 = np.array(kmonitor02)
    
    return kappa_mat
        
def get_shutter_radiation(n_aper, delay, fields):
    global monitor01, monitor02
    global time2, startend_shutter
    shutter_rads = []
    monitor01 = []
    monitor02 = []
    beams_pos_in_output = [0, 1, 6, 7]

    nott_control.all_shutters_open(n_aper)
    for sh in range(n_aper):
        # Measure of the bias induced by the background and measure the flux on the outputs of the chip

        time.sleep(delay)
        # end = datetime.fromtimestamp(time.time())
        # start = end - timedelta(seconds=delay)
        time.sleep(delay)

        start = startend_shutter[sh][2]
        end = startend_shutter[sh][3]
        fluxes_bg = [get_field2(elt, start, end, True)[1] for elt in fields]
        fluxes_bg = np.array(fluxes_bg)

        plaf = get_field2(zorg[0], zorg[1], zorg[2], True)[1]
        if sh == 0:
            print('**** Shutter 1 radiation P1', datetime.fromtimestamp(start/1000.), start, end, fluxes_bg[beams_pos_in_output[sh]], zorg, plaf)

        monitor02.append(fluxes_bg[[beams_pos_in_output[sh], 2, 3, 4, 5, -1]])
        
        shift_bg = fluxes_bg[-1]
        fluxes_bg = fluxes_bg[:-1]
        
        # Close one shutter and measure the flux on the outputs of the chip
        print('Close shutter', sh+1, '...')
        shutter_close(str(sh+1))
        time.sleep(delay)
        # end = datetime.fromtimestamp(time.time())
        # start = end - timedelta(seconds=delay)
        
        start = startend_shutter[sh][0]
        end = startend_shutter[sh][1]      
        
        fluxes = [get_field2(elt, start, end, True)[1] for elt in fields]
        fluxes = np.array(fluxes)
        
        monitor01.append(fluxes[[beams_pos_in_output[sh], 2, 3, 4, 5, -1]])
        
        shift = fluxes[-1]
        fluxes = fluxes[:-1]

        
        shutter_rad = fluxes - shift - (fluxes_bg - shift_bg)
        
        shutter_rads.append(shutter_rad)

        shutter_open(str(sh+1))
        print('Done')
        
        
    shutter_rads = np.array(shutter_rads)
    
    monitor01 = np.array(monitor01)
    monitor02 = np.array(monitor02)
    
    return shutter_rads

# kappa matrix times
time1 = [[1725376729947, 1725376731947, 1725376731997, 1725376733997], [1725376734047, 1725376736047, 1725376736096, 1725376738096], [1725376738148, 1725376740148, 1725376740202, 1725376742202], [1725376742257, 1725376744257, 1725376744305, 1725376746305]]
# shutter times
time2 = [[1725376709766, 1725376711766, 1725376711797, 1725376713797], [1725376713819, 1725376715819, 1725376715842, 1725376717842], [1725376717864, 1725376719864, 1725376719886, 1725376721886], [1725376721907, 1725376723907, 1725376723930, 1725376725930]]
# time2 = [[1725447152180, 1725447154180, 1725447154211, 1725447156211], [1725447156233, 1725447158233, 1725447158256, 1725447160256], [1725447160278, 1725447162278, 1725447162300, 1725447164300], [1725447164324, 1725447166324, 1725447166347, 1725447168347]]
P1='roi1_sum' # define all the ROI output
P2='roi2_sum'
I1='roi3_sum'
I2='roi4_sum'
I3='roi5_sum'
I4='roi6_sum'
P3='roi7_sum'
P4='roi8_sum'
Shift='roi9_sum'
fields = [P1, P2, I1, I2, I3, I4, P3, P4, Shift]

delay = 2
n_aper = 4
return_throughput = True

# nott_control.all_shutters_close(n_aper)
# for sh in range(1, 5):
#     print(sh)
#     shutter_close(str(sh))
#     time.sleep(6)
#     shutter_open(str(sh))
#     time.sleep(1)

nott_control.all_shutters_open(n_aper)
# nott_control.all_shutters_close(n_aper)

print('Block the source and press Enter to continue')
input()
print('Measuring shuter radiations')
shutter=shutter_radiation(delay)
print('Done')
print('Unblock the source and press Enter to continue')
input()
print('Measuring kappa matrix')
a=Kappa_matrix_measurement_1(delay,shutter)
print(a.shape)
np.save('bastien_kappa', a)
print('Done')
print(startend)
print(startend_shutter)
print('----')
print('KAPPA MAM')
nott_control.all_shutters_open(n_aper)
print('Block the source and press Enter to continue')
input()
print('NEW: Measuring shuter radiations')
shutters_radiation = get_shutter_radiation(n_aper, delay, fields)
print('Done')
print('Unblock the source and press Enter to continue')
input()
print('NEW: Measuring kappa matrix')
kappa = build_kappa_matrix(delay, shutters_radiation, n_aper, fields, return_throughput)
print('Done')
print(kappa.shape)
np.save('mam_kappa', kappa)

print('Identical shutters?')
shutter = np.array(shutter)
shutter = shutter.reshape((4,5))
shutters_radiation0 = shutters_radiation[0, [0, 2, 3, 4, 5]]
print(np.all(shutter[0] == shutters_radiation0))

shutters_radiation1 = shutters_radiation[1, [1, 2, 3, 4, 5]]
print(np.all(shutter[1] == shutters_radiation1))

shutters_radiation2 = shutters_radiation[2, [6, 2, 3, 4, 5]]
print(np.all(shutter[2] == shutters_radiation2))

shutters_radiation3 = shutters_radiation[3, [7, 2, 3, 4, 5]]
print(np.all(shutter[3] == shutters_radiation3))

print('Identical shutter flux?')
print(np.all(monitor01 == moni01))
print(np.all(monitor02 == moni02))

print('Identical kappa fluxes?')
print(np.all(kmonitor01 == kmoni01))
print(np.all(kmonitor02 == kmoni02))

print('Identical kappa matrices?')
print(np.all(a[:,0] == kappa[2:6, 0]))
print(np.all(a[:,1] == kappa[2:6, 1]))
print(np.all(a[:,2] == kappa[2:6, 2]))
print(np.all(a[:,3] == kappa[2:6, 3]))
print(' ')
print(a)
print(kappa[2:6])
