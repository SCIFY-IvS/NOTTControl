# -*- coding: utf-8 -*-
"""
Created on Wed Jan 14 12:54:01 2026

@author: Thomas

This class provides retrieval and handling of sequences of infrared camera frames.

"""

import numpy as np
from PIL import Image
from nottcontrol.camera.roi import Roi
from nottcontrol.camera.brightness_calculator import BrightnessCalculator
from nottcontrol import config as nott_config
from pathlib import Path

# Loading from config.ini
frame_directory = str(nott_config['DEFAULT']['frame_directory'])
window_cfg = dict.fromkeys(["w","h","x","y"])
for key in window_cfg.keys():
    window_cfg[key] = int(nott_config['CAMERA']['window_'+key])
rois_cfg = []
for i in range(0,10):
    roi_i = nott_config.getarray('CAMERA','ROI '+str(i+1),np.int32)
    if len(roi_i) != 4:
        raise Exception('Invalid ROI config')
    rois_cfg.append(Roi(roi_i[0],roi_i[1],roi_i[2],roi_i[3]))

class Frame():
    # This class represents a sequence of frames, taken by the infrared camera.
    def __init__(self,id_,window_=window_cfg,rois_=rois_cfg):
        """
        Parameters
        ----------
        id_ : list of strings
            IDs of the constituent frames.
            Frame ID = Windows machine time in string "Y%m%d_H%M%S" format, up to millisecond precision. Date and time are separated by an underscore.
        """
        # Setting frame IDs
        self.id = id_
        # Setting window
        self.window = window_
        # Fetch data from local machine
        data_cube = []
        for frame_id in id_:
            Ymd,HMS = frame_id.split(sep="_")[0],frame_id.split(sep="_")[1]
            directory = Path(frame_directory).joinpath(Ymd)
            filename = HMS+'.png'
            img_path = str(Path.joinpath(directory,filename))
            img = Image.open(img_path)
            data_ =  np.asarray(img)
            data_cube.append(data_)
            
        self.data = np.array(data_cube)
        self.width = data_cube.shape[2]
        self.height = data_cube.shape[1]
        # ROIs
        rois_crop_ = []
        rois_data_ = [] 
        for k in range(0,8):
            # ROI positions within windowed frame
            x,y,w,h = int(rois_[k].x-window_["x"]),int(rois_[k].y-window_["y"]),int(rois_[k].w),int(rois_[k].h)
            i1,i2,j1,j2 = y,y+h,x,x+w
            rois_crop_.append(Roi(x,y,w,h))
            rois_data_.append(data_cube[:,i1:i2+1,j1:j2+1])
        self.rois = rois_
        self.rois_crop = rois_crop_
        self.rois_data = rois_data_
     
    def set_id(self,id_):
        self.id = id_
        return
    
    def set_window(self,window_):
        self.window = window_
        return
    
    def set_data(self,data_):
        self.data = data_
        self.width = data_.shape[2]
        self.height = data_.shape[1]
        self.set_rois(self.rois)
        return
     
    def set_rois(self,rois_):
        # ROIs
        rois_crop_ = []
        rois_data_ = []
        for k in range(0,8):
            # ROI positions within windowed frame
            x,y,w,h = int(rois_[k].x-self.window["x"]),int(rois_[k].y-self.window["y"]),int(rois_[k].w),int(rois_[k].h)
            i1,i2,j1,j2 = y,y+h,x,x+w
            rois_crop_.append(Roi(x,y,w,h))
            rois_data_.append(self.data[:,i1:i2+1,j1:j2+1])
        self.rois = rois_
        self.rois_crop = rois_crop_
        self.rois_data = rois_data_
        return
        
    def av_full(self):
        # Averaging the full frames, over all DITs
        return np.mean(self.data,axis=0)
        
    def av_rois(self):
        # Averaging the ROIs, over all DITs
        return np.mean(self.rois_data,axis=1)
    
    def std_full(self):
        # Calculating the standard deviation over all DITs, for the full frames
        return np.std(self.data,axis=0)
    
    def std_rois(self):
        # Calculating the standard deviation over all DITs, for the ROIs
        return np.std(self.rois_data,axis=1)
     
    def get_roi(self,idx):
        
        # Calculating min,max,mean,sum
        calc = BrightnessCalculator(self.rois_data)
        calc.run()
        
        return calc.results, self.rois_data
    
    def calib(self,dark,flat=None):
        # "dark" and "flat" denote series of dark (shutters closed) and flat (even illumination) frames, are both instance of the Frame class
        # ! Limiting calculations to data within the ROIs for efficiency
        
        # 1) Calibrated mean frame
        # Amount of frames
        N_sci = len(self.data)
        N_dark = len(dark.data)
        # Doing following calculations for full frames (i.e., for each pixel)
        # Calculating the mean over all frames = mean counts per DIT (detector integration time)
        sci_mean = self.av_rois()
        dark_mean = dark.av_rois()
        # Calculating the sample's standard deviation over all frames, dividing by nr. of frames to get the std on the mean.
        sci_mean_std = self.std_rois() / N_sci
        dark_mean_std = dark.std_rois() / N_dark
        # Calibrated master frame, corresponding to one DIT (FLAT TBD)
        cal_mean = sci_mean-dark_mean
        cal_std = np.sqrt(sci_mean_std**2+dark_mean_std**2)
        
        # 2) Calibrated sequence of frames
        cal_seq = np.subtract(self.rois_data,dark_mean)
        # SNR for individual frames TBD
        return cal_mean,cal_std,cal_seq
        