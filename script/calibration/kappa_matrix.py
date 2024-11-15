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

redis_url = 'redis://10.33.178.176:6379'
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
    r = redis.from_url(redis_url)

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


def get_position(DL,field, start,end): #return podition of Delay line 'DL' and the values of Roi 'Field' between start and end 

    
    # Read data
    r = redis.from_url(redis_url)

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

def get_field2(field, start, end, return_avg, lag=0, db_address='redis://10.33.179.167:6379'):
    """
    Get the data in the database of the required `field` in a time range limited by `start` and `end`.
    The returned object is a 2D-array which rows (1st axis) are the datapoints, the first column is the timestamp
    (in milliseconds) and the 2nd column is the value of `field`.

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
    lag: float
        Lag to add to the timeline, in millisecond. The default is 0.
    db_address : str, optional
        Address of the database. The default is 'redis://10.33.179.167:6379'.

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
    output[:,0] = output[:,0] + lag

    if return_avg:
        output = output.mean(0) # Average along the number of points axis

    return  output

    
def build_kappa_matrix(delay, shutter_radiation, n_aper, fields, return_throughput):
    """
    Build the kappa matrix.
    This matrix calculates the splitting ratios of the combiner.
    These ratios can be normalised by the flux of the incoming beam or the sum of all the outputs.
    The process consists of closing all the shutters and open them one by one while recording the flux in the outputs.

    The flux received is biased by:
        - ambient thermal background
        - the detector noise
        - thermal emission of the shutters
        
    The two first ones are acquired with a ROI located in a plain area on the detector.
    The last one must be measured separately.

    Parameters
    ----------
    delay : float
        Acquisition time during which the shutter is open, in second.
    shutter_radiation : array
        Thermal radiation of the shutters
    n_aper : int
        Number of apertures of the combiner
    fields : list
        Name of the ROI fields of the camera to grab from the database
    return_throughput : bool
        If `True`, normalise the column of the matrix by its sum, and it is the splitting ration. If `False`, it is normalised by the flux on the corresponding photometric output: it directly gives the contribution of a beam in a given output, knowing the flux in its photometric output.

    Returns
    -------
    kappa_mat : 2d-array
        Kappa matrix of the combiner

    Notes
    -----
    Estimator of the flux in the outputs :math:`O_i` given one beam injected :math:`I_A` :

    :math:`O_i = \kappa_{A,i} \times I_A + DetBg + \sum_{k ≠ A} Sh_{k, O_i}`

    where :
        - :math:`\kappa_{A,i}` is the kappa coefficient to determine
        - :math:`DetBg` is the sum of the detector noise and the thermal background, gotten from an ROI of the detector with no signal
        - :math:`Sh_{k, O_i}` is the thermal emission of the shutter `k` collected on the output :math:`O_i`. This bias is to determine and to be removed

    To remove the contribution of all the other shutters, we have to close all the shutters to get the flux in the outputs:

    :math:`O^c_i = DetBg^c + Sh_{A, O_i} + \sum_{k ≠ A} Sh_{k, O_i}`

    Thus:
    
    :math:`O_i = \kappa_{A,i} \times I_A + DetBg + O^c_i -  DetBg^c - Sh_{A, O_i}`

    with :math:`Sh_{A, O_i}` the thermal emission of the aperture `A` and :math:`O^c_i` the flux in the output `i` when all the shutters are closed.
    It is given by the function ``get_shutter_radiation``.

    Finally, the kappa coefficients is given by:

    :math:`\kappa_{A,i} \times I_A = O_i - DetBg - (O^c_i -  DetBg^c - Sh_{A, O_i})`, that has to be normalised by `I_A` (see top of the description).
    """

    # startend = time1
    
    kappa_mat = []
    beams_pos_in_output = [0, 1, 6, 7]

    for sh in range(n_aper):
        # Measure of the bias induced by the thermal emission of all shutters and measure the flux on the outputs of the chip
        nott_control.all_shutters_close(n_aper)

        time.sleep(delay)
        start, end = define_time2(delay)
        time.sleep(delay) # Wait for the lag between the camera and the database
        
        fluxes_shutters_closed = [get_field2(elt, start, end, True)[1] for elt in fields]
        fluxes_shutters_closed = np.array(fluxes_shutters_closed)

        detbg_shutters_closed = fluxes_shutters_closed[-1] # Ambient thermal background and detector noise
        fluxes_shutters_closed = fluxes_shutters_closed[:-1] # Flux at the outputs
        
        # Open one shutter and measure the flux on the outputs of the chip
        print('Open shutter', sh+1, '...')
        shutter_open(str(sh+1))
        time.sleep(delay)
        start, end = define_time2(delay)    
        time.sleep(delay) # Wait for the lag between the camera and the database

        fluxes = [get_field2(elt, start, end, True)[1] for elt in fields]
        fluxes = np.array(fluxes)

        detbg = fluxes[-1] # Ambient thermal background and detector noise
        fluxes = fluxes[:-1] # Flux at the outputs
        
        # Estimator of the kappa coefficients
        kappa_col = fluxes - detbg - (fluxes_shutters_closed - detbg_shutters_closed) + shutter_radiation[sh]
        
        # Normalisation of the kappa coefficients
        if return_throughput:
            kappa_col /= kappa_col.sum()
        else:
            kappa_col /= kappa_col[beams_pos_in_output[sh]]
            
        kappa_mat.append(kappa_col)

        shutter_close(str(sh+1))
        
    kappa_mat = np.array(kappa_mat)
    kappa_mat = kappa_mat.T
    
    return kappa_mat
        
def define_time2(delay):
    """
    Return the rounded timestamps of the start and end of period to grab from the database, in milliseconds.
    The `end` is the timestamp at which this function is called.
    The `start` is `delay` seconds before.
    The timestamps must be in the same timezone as the database.

    Parameters
    ----------
    delay: float
        Length of the timeserie to grab, in seconds.

    Returns
    -------
    start: int
        Rounded timestamp of the beginning of the timeserie to grab, in milliseconds
    end: int
        Rounded timestamp of the end of the timeserie to grab, in milliseconds
    """
    end = time.time()
    start = end - delay

    end = round(end * 1000)
    start = round(start * 1000)

    return start, end

def get_shutter_radiation(n_aper, delay, fields):
    """
    Measure the thermal radiation of the shutters, individually, in all the outputs.

    Parameters
    ----------
    n_aper: int
        Number of apertures
    delay: float
        Time range to grab, in second
    fields: list
        Name of the ROI to grab from the database.

    Returns
    -------
    shutter_rads: array
        Thermal emission of a given aperture (row) in all the outputs (columns)

    Notes
    -----
    Estimator of the thermal radiation of the shutter `A` in output `i`:

    :math:`Sh_{A,i} = O_{A,i} - detbg - (O^o_{A,i} - detbg^o)`

    with:
        - :math:`O_{A,i}` the flux in the output `i` when only the aperture `A` is closed
        - `detbg` the detector noise and ambient thermal background, measured in a ROI with no signal, when the aperture `A` is closed the others are closed
        - :math:`O^o_{A,i}` the flux in the output `i` when only the aperture `A` and the other ones are open
        - :math:`detbg^o` the detector noise and ambient thermal background, measured in a ROI with no signal, when the aperture `A` is open
    """

    shutter_rads = []

    nott_control.all_shutters_open(n_aper)
    for sh in range(n_aper):
        # Measure of the bias induced by the background and measure the flux on the outputs of the chip, when all the apertures are open

        time.sleep(delay)
        start, end = define_time2(delay)
        time.sleep(delay) # Wait for the lag between the camera and the database

        fluxes_bg = [get_field2(elt, start, end, True)[1] for elt in fields]
        fluxes_bg = np.array(fluxes_bg)        
        shift_bg = fluxes_bg[-1]
        fluxes_bg = fluxes_bg[:-1]
        
        # Close one shutter and measure the flux on the outputs of the chip
        print('Close shutter', sh+1, '...')
        shutter_close(str(sh+1))
        time.sleep(delay)
        start, end = define_time2(delay)    
        time.sleep(delay)    # Wait for the lag between the camera and the database     
        
        fluxes = [get_field2(elt, start, end, True)[1] for elt in fields]
        fluxes = np.array(fluxes)       
        detbg = fluxes[-1]
        fluxes = fluxes[:-1]

        
        shutter_rad = fluxes - detbg - (fluxes_bg - shift_bg)
        
        shutter_rads.append(shutter_rad)

        # Reopen the aperture
        shutter_open(str(sh+1))
        print('Done')
        
        
    shutter_rads = np.array(shutter_rads)
    
    return shutter_rads


P1='roi1_avg' # define all the ROI output
P2='roi2_avg'
I1='roi3_avg'
I2='roi4_avg'
I3='roi5_avg'
I4='roi6_avg'
P3='roi7_avg'
P4='roi8_avg'
detbg='roi9_avg'
fields = [P1, P2, I1, I2, I3, I4, P3, P4, detbg]

delay = 2
n_aper = 4
return_throughput = False

nott_control.all_shutters_open(n_aper)

# duration = 2.
# time.sleep(0.5)
# start, end = define_time2(duration)
# time.sleep(0.5)
# flux = get_field2(P1, start, end, False)

# print(flux)

# print('Block the source and press Enter to continue')
# input()
# print('NEW: Measuring shuter radiations')
# shutters_radiation = get_shutter_radiation(n_aper, delay, fields)
# print('Done')
# print('Unblock the source and press Enter to continue')
# input()
# print('NEW: Measuring kappa matrix')
# kappa = build_kappa_matrix(delay, shutters_radiation, n_aper, fields, return_throughput)
# print('Done')
# print(kappa.shape)
# np.save('kappa', kappa)
# print(kappa)

# print('THROUGHPUT')
# print('Block the source and press Enter to continue')
# input()
# print('NEW: Measuring shuter radiations')
# shutters_radiation = get_shutter_radiation(n_aper, delay, fields)
# print('Done')
# print('Unblock the source and press Enter to continue')
# input()
# print('NEW: Measuring kappa matrix')
# kappa = build_kappa_matrix(delay, shutters_radiation, n_aper, fields, True)
# print('Done')
# print(kappa.shape)
# np.save('kappa_throughput', kappa)
# print(kappa)

# print('Recup')
# import pickle
# import os

# def save_data(data, path, name):
#     print('MSG - Save data in:', path+name)
#     list_saved_files = [elt for elt in os.listdir(path) if name in elt]
#     count_file = len(list_saved_files) + 1
#     name_file = name+'_%03d.pkl'%(count_file)
#     dbfile = open(path + name_file, 'wb')
#     pickle.dump(data, dbfile)
#     dbfile.close()

# path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/calibration/'
# name = 'kappa_matrix_ts'
# start = datetime(2024, 9, 5, 12, 56, 00)
# end = datetime(2024, 9, 5, 12, 58, 30)

# start = round(start.timestamp()*1000)
# end = round(end.timestamp()*1000)

# dic_data = {}

# for f in fields:
#     out = get_field2(f, start, end, False)
#     dic_data[f] = out

# save_data(dic_data, path, name)