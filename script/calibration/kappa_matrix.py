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


def define_time(delay):# Define time interval        
    end   = datetime.utcnow() # - timedelta(seconds=0.9) # There is a 0.9 sec delay with redis
    start = end - timedelta(seconds=delay) 

    return(start,end)

def get_field(field1, start, end ):
    
    
    # Read data
    r = redis.from_url('redis://10.33.178.176:6379')

    # Extract data
    ts = r.ts()

     # Get ROI values
    result1 = ts.range(field1, unix_time_ms(start), unix_time_ms(end))

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
    r = redis.from_url('redis://10.33.178.176:6379')

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
    [start, end]=define_time(delay)

    Value_P1=get_mean_value(P1, start,end) #get the values of each output
    Value_I1=get_mean_value(I1, start,end)
    Value_I2=get_mean_value(I2, start,end)
    Value_I3=get_mean_value(I3, start,end)
    Value_I4=get_mean_value(I4, start,end)
    Value_Shift=get_mean_value(Shift, start,end)#get the first value of the shift

    shutter_close('1') #take the background
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P1_2=get_mean_value(P1, start,end)
    Value_I1_2=get_mean_value(I1, start,end)
    Value_I2_2=get_mean_value(I2, start,end)
    Value_I3_2=get_mean_value(I3, start,end)
    Value_I4_2=get_mean_value(I4, start,end)
    Value_Shift_2=get_mean_value(Shift, start,end) #get the second shift value

    P1_clean=Value_P1-Value_Shift-Value_P1_2+Value_Shift_2+shutter[0]# clean background and shift and shutter radiation for photometric output
   

    P1_coefficients=[Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[1],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[2],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[3],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[4] ]
    P1_coefficients=[x / P1_clean for x in P1_coefficients]   #put the four intensity value for interferometric output in a matrix and then divise by the photometric output (I1/P1,I2/P1,I3/P1,I4/P1)


    shutter_open('2') # Measure the beam 2's outputs
    shutter_close('1')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)

    [start, end]=define_time(delay)

    Value_P2=get_mean_value(P2, start,end)
    Value_I1=get_mean_value(I1, start,end)
    Value_I2=get_mean_value(I2, start,end)
    Value_I3=get_mean_value(I3, start,end)
    Value_I4=get_mean_value(I4, start,end)
    Value_Shift=get_mean_value(Shift, start,end)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')


    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P2_2=get_mean_value(P2, start,end)
    Value_I1_2=get_mean_value(I1, start,end)
    Value_I2_2=get_mean_value(I2, start,end)
    Value_I3_2=get_mean_value(I3, start,end)
    Value_I4_2=get_mean_value(I4, start,end)
    Value_Shift_2=get_mean_value(Shift, start,end)

    P2_clean=Value_P2-Value_Shift-Value_P2_2+Value_Shift_2+shutter[5]# clean background
    

    P2_coefficients=[Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[6],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[7],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[8],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[9] ]
   
    P2_coefficients=[x / P2_clean for x in P2_coefficients]
   

    shutter_open('3') # Measure the beam 3's outputs
    shutter_close('1')
    shutter_close('2')
    shutter_close('4')

    time.sleep(delay)

    [start, end]=define_time(delay)

    Value_P3=get_mean_value(P3, start,end)
    Value_I1=get_mean_value(I1, start,end)
    Value_I2=get_mean_value(I2, start,end)
    Value_I3=get_mean_value(I3, start,end)
    Value_I4=get_mean_value(I4, start,end)
    Value_Shift=get_mean_value(Shift, start,end)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P3_2=get_mean_value(P3, start,end)
    Value_I1_2=get_mean_value(I1, start,end)
    Value_I2_2=get_mean_value(I2, start,end)
    Value_I3_2=get_mean_value(I3, start,end)
    Value_I4_2=get_mean_value(I4, start,end)
    Value_Shift_2=get_mean_value(Shift, start,end)

    P3_clean=Value_P3-Value_Shift-Value_P3_2+Value_Shift_2+shutter[10]# clean background
   

    P3_coefficients=[Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[11],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[12],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[13],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[14] ]
    
    P3_coefficients=[x / P3_clean for x in P3_coefficients]
    

    shutter_open('4') # Measure the beam 4's outputs
    shutter_close('1')
    shutter_close('3')
    shutter_close('2')

    time.sleep(delay)

    [start, end]=define_time(delay)

    Value_P4=get_mean_value(P4, start,end)
    Value_I1=get_mean_value(I1, start,end)
    Value_I2=get_mean_value(I2, start,end)
    Value_I3=get_mean_value(I3, start,end)
    Value_I4=get_mean_value(I4, start,end)
    Value_Shift=get_mean_value(Shift, start,end)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P4_2=get_mean_value(P4, start,end)
    Value_I1_2=get_mean_value(I1, start,end)
    Value_I2_2=get_mean_value(I2, start,end)
    Value_I3_2=get_mean_value(I3, start,end)
    Value_I4_2=get_mean_value(I4, start,end)
    Value_Shift_2=get_mean_value(Shift, start,end)

    P4_clean=Value_P4-Value_Shift-Value_P4_2+Value_Shift_2+shutter[15]# clean background
    

    P4_coefficients=[Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[16],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[17],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[18],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[19] ]
    
    P4_coefficients=[x / P4_clean for x in P4_coefficients]
    
    

    shutdown()


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

    return(Kappa_matrix)
                                
def Kappa_matrix_measurement_2(delay, shutter):# calculation of Kappa Matrix (Interferometric outputs depending of total beam outputs )
   
   
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
    [start, end]=define_time(delay)

    Value_P1=get_mean_value(P1, start,end)
    Value_I1=get_mean_value(I1, start,end)
    Value_I2=get_mean_value(I2, start,end)
    Value_I3=get_mean_value(I3, start,end)
    Value_I4=get_mean_value(I4, start,end)
    Value_Shift=get_mean_value(Shift, start,end)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P1_2=get_mean_value(P1, start,end)
    Value_I1_2=get_mean_value(I1, start,end)
    Value_I2_2=get_mean_value(I2, start,end)
    Value_I3_2=get_mean_value(I3, start,end)
    Value_I4_2=get_mean_value(I4, start,end)
    Value_Shift_2=get_mean_value(Shift, start,end)

    P1_clean=Value_P1-Value_Shift-Value_P1_2+Value_Shift_2+shutter[0]# clean background
   

    Sum1= P1_clean +Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+Value_I4-Value_Shift-Value_I4_2+Value_Shift_2 +shutter[1]+shutter[2]+shutter[3]+shutter[4]

    P1_coefficients=[P1_clean,0,Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[1],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[2],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[3],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2 +shutter[4],0,0]
   
    P1_coefficients=[x / Sum1 for x in P1_coefficients]
  

    shutter_open('2') # Measure the beam 2's outputs
    shutter_close('1')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)

    [start, end]=define_time(delay)

    Value_P2=get_mean_value(P2, start,end)
    Value_I1=get_mean_value(I1, start,end)
    Value_I2=get_mean_value(I2, start,end)
    Value_I3=get_mean_value(I3, start,end)
    Value_I4=get_mean_value(I4, start,end)
    Value_Shift=get_mean_value(Shift, start,end)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')


    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P2_2=get_mean_value(P2, start,end)
    Value_I1_2=get_mean_value(I1, start,end)
    Value_I2_2=get_mean_value(I2, start,end)
    Value_I3_2=get_mean_value(I3, start,end)
    Value_I4_2=get_mean_value(I4, start,end)
    Value_Shift_2=get_mean_value(Shift, start,end)

    P2_clean=Value_P2-Value_Shift-Value_P2_2+Value_Shift_2+shutter[5]# clean background
   
    Sum2= P2_clean + Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[6]+shutter[7]+shutter[8]+shutter[9]

    P2_coefficients=[0,P2_clean,Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[6],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[7],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[8],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2 +shutter[9],0,0]
    P2_coefficients=[x / Sum2 for x in P2_coefficients]
    

    shutter_open('3') # Measure the beam 3's outputs
    shutter_close('1')
    shutter_close('2')
    shutter_close('4')

    time.sleep(delay)

    [start, end]=define_time(delay)

    Value_P3=get_mean_value(P3, start,end)
    Value_I1=get_mean_value(I1, start,end)
    Value_I2=get_mean_value(I2, start,end)
    Value_I3=get_mean_value(I3, start,end)
    Value_I4=get_mean_value(I4, start,end)
    Value_Shift=get_mean_value(Shift, start,end)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P3_2=get_mean_value(P3, start,end)
    Value_I1_2=get_mean_value(I1, start,end)
    Value_I2_2=get_mean_value(I2, start,end)
    Value_I3_2=get_mean_value(I3, start,end)
    Value_I4_2=get_mean_value(I4, start,end)
    Value_Shift_2=get_mean_value(Shift, start,end)

    P3_clean=Value_P3-Value_Shift-Value_P3_2+Value_Shift_2+shutter[10]# clean background
    
    Sum3= P3_clean + Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[11]+shutter[12]+shutter[13]+shutter[14]

    P3_coefficients=[0,0,Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[11],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[12],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[13],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[14],P3_clean,0 ]
    
    P3_coefficients=[x / Sum3 for x in P3_coefficients]
   

    shutter_open('4') # Measure the beam 4's outputs
    shutter_close('1')
    shutter_close('3')
    shutter_close('2')

    time.sleep(delay)

    [start, end]=define_time(delay)

    Value_P4=get_mean_value(P4, start,end)
    Value_I1=get_mean_value(I1, start,end)
    Value_I2=get_mean_value(I2, start,end)
    Value_I3=get_mean_value(I3, start,end)
    Value_I4=get_mean_value(I4, start,end)
    Value_Shift=get_mean_value(Shift, start,end)

    shutter_close('1')
    shutter_close('2')
    shutter_close('3')
    shutter_close('4')

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P4_2=get_mean_value(P4, start,end)
    Value_I1_2=get_mean_value(I1, start,end)
    Value_I2_2=get_mean_value(I2, start,end)
    Value_I3_2=get_mean_value(I3, start,end)
    Value_I4_2=get_mean_value(I4, start,end)
    Value_Shift_2=get_mean_value(Shift, start,end)

    P4_clean=Value_P4-Value_Shift-Value_P4_2+Value_Shift_2+shutter[15]# clean background

    Sum4= P4_clean + Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+Value_I4-Value_Shift-Value_I4_2+Value_Shift_2  +shutter[16]+shutter[17]+shutter[18]+shutter[19] 

    P4_coefficients=[0,0,Value_I1-Value_Shift-Value_I1_2+Value_Shift_2+shutter[16],Value_I2-Value_Shift-Value_I2_2+Value_Shift_2+shutter[17],Value_I3-Value_Shift-Value_I3_2+Value_Shift_2+shutter[18],Value_I4-Value_Shift-Value_I4_2+Value_Shift_2+shutter[19],0,P4_clean ]
  
    P4_coefficients=[x / Sum4 for x in P4_coefficients]
   

    shutdown()


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

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P1_S1=get_mean_value(P1, start,end) #get values in each output of the shutter radiation
    Value_I1_S1=get_mean_value(I1, start,end)
    Value_I2_S1=get_mean_value(I2, start,end)
    Value_I3_S1=get_mean_value(I3, start,end)
    Value_I4_S1=get_mean_value(I4, start,end)
    Value_Shift=get_mean_value(Shift, start,end)

    shutter_open('1')

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P1_2_S1=get_mean_value(P1, start,end)#get background
    Value_I1_2_S1=get_mean_value(I1, start,end)
    Value_I2_2_S1=get_mean_value(I2, start,end)
    Value_I3_2_S1=get_mean_value(I3, start,end)
    Value_I4_2_S1=get_mean_value(I4, start,end)
    Value_Shift_2=get_mean_value(Shift, start,end)

    Shutter1=[Value_P1_S1-Value_Shift-Value_P1_2_S1+Value_Shift_2,Value_I1_S1-Value_Shift-Value_I1_2_S1+Value_Shift_2,Value_I2_S1-Value_Shift-Value_I2_2_S1+Value_Shift_2,Value_I3_S1-Value_Shift-Value_I3_2_S1+Value_Shift_2,Value_I4_S1-Value_Shift-Value_I4_2_S1+Value_Shift_2]
    #put values in a matrix [P1,I1,I2,I3,I4]

    shutter_close('2')# shutter 2 radiation

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P2_S2=get_mean_value(P2, start,end)
    Value_I1_S2=get_mean_value(I1, start,end)
    Value_I2_S2=get_mean_value(I2, start,end)
    Value_I3_S2=get_mean_value(I3, start,end)
    Value_I4_S2=get_mean_value(I4, start,end)
    Value_Shift=get_mean_value(Shift, start,end)

    shutter_open('2')

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P2_2_S2=get_mean_value(P2, start,end)
    Value_I1_2_S2=get_mean_value(I1, start,end)
    Value_I2_2_S2=get_mean_value(I2, start,end)
    Value_I3_2_S2=get_mean_value(I3, start,end)
    Value_I4_2_S2=get_mean_value(I4, start,end)
    Value_Shift_2=get_mean_value(Shift, start,end)

    Shutter2=[Value_P2_S2-Value_Shift-Value_P2_2_S2+Value_Shift_2,Value_I1_S2-Value_Shift-Value_I1_2_S2+Value_Shift_2,Value_I2_S2-Value_Shift-Value_I2_2_S2+Value_Shift_2,Value_I3_S2-Value_Shift-Value_I3_2_S2+Value_Shift_2,Value_I4_S2-Value_Shift-Value_I4_2_S2+Value_Shift_2]
    #[P2,I1,I2,I3,I4]
    shutter_close('3') #shutter 3 radiation

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P3_S3=get_mean_value(P3, start,end)
    Value_I1_S3=get_mean_value(I1, start,end)
    Value_I2_S3=get_mean_value(I2, start,end)
    Value_I3_S3=get_mean_value(I3, start,end)
    Value_I4_S3=get_mean_value(I4, start,end)
    Value_Shift=get_mean_value(Shift, start,end)

    shutter_open('3')

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P3_2_S3=get_mean_value(P3, start,end)
    Value_I1_2_S3=get_mean_value(I1, start,end)
    Value_I2_2_S3=get_mean_value(I2, start,end)
    Value_I3_2_S3=get_mean_value(I3, start,end)
    Value_I4_2_S3=get_mean_value(I4, start,end)
    Value_Shift_2=get_mean_value(Shift, start,end)

    Shutter3=[Value_P3_S3-Value_Shift-Value_P3_2_S3+Value_Shift_2,Value_I1_S3-Value_Shift-Value_I1_2_S3+Value_Shift_2,Value_I2_S3-Value_Shift-Value_I2_2_S3+Value_Shift_2,Value_I3_S3-Value_Shift-Value_I3_2_S3+Value_Shift_2,Value_I4_S3-Value_Shift-Value_I4_2_S3+Value_Shift_2]
    #[P3,I1,I2,I3,I4]

    shutter_close('4') #shutter 4 radiation

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P4_S4=get_mean_value(P4, start,end)
    Value_I1_S4=get_mean_value(I1, start,end)
    Value_I2_S4=get_mean_value(I2, start,end)
    Value_I3_S4=get_mean_value(I3, start,end)
    Value_I4_S4=get_mean_value(I4, start,end)
    Value_Shift=get_mean_value(Shift, start,end)

    shutter_open('4')

    time.sleep(delay)
    [start, end]=define_time(delay)

    Value_P4_2_S4=get_mean_value(P4, start,end)
    Value_I1_2_S4=get_mean_value(I1, start,end)
    Value_I2_2_S4=get_mean_value(I2, start,end)
    Value_I3_2_S4=get_mean_value(I3, start,end)
    Value_I4_2_S4=get_mean_value(I4, start,end)
    Value_Shift_2=get_mean_value(Shift, start,end)

    Shutter4=[Value_P4_S4-Value_Shift-Value_P4_2_S4+Value_Shift_2,Value_I1_S4-Value_Shift-Value_I1_2_S4+Value_Shift_2,Value_I2_S4-Value_Shift-Value_I2_2_S4+Value_Shift_2,Value_I3_S4-Value_Shift-Value_I3_2_S4+Value_Shift_2,Value_I4_S4-Value_Shift-Value_I4_2_S4+Value_Shift_2]
    #[P4,I1,I2,I3,I4]
    startup()
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
