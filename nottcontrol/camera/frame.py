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
    window_cfg[key] = int(nott_config['CAMERA']['window_'+key]) # string to int
rois_cfg = []
for i in range(0,10):
    roi_i = nott_config.getarray('CAMERA','ROI '+str(i+1),np.int32)
    if len(roi_i) != 4:
        raise Exception('Invalid ROI config')
    rois_cfg.append(Roi(roi_i[0],roi_i[1],roi_i[2],roi_i[3]))

class Frame(object):
    # This class represents a sequence of frames, taken by the infrared camera.
    def __init__(self,ids,window=window_cfg,rois=rois_cfg):
        """
        Parameters
        ----------
        ids : list of strings
            IDs of the constituent frames.
            Frame ID = Windows machine time in string "Y%m%d_H%M%S" format, up to millisecond precision. Date and time are separated by an underscore.
        """
        # Setting frame IDs
        self.ids = ids
        # Setting window
        self.window = window
        # Fetch data from local machine
        data_cube = []
        for frame_id in ids:
            Ymd,HMS = frame_id.split(sep="_")[0],frame_id.split(sep="_")[1]
            directory = Path(frame_directory).joinpath(Ymd)
            filename = HMS+'.png'
            img_path = str(Path.joinpath(directory,filename))
            img = Image.open(img_path)
            data_slice =  np.asarray(img)
            data_cube.append(data_slice)
            
        self.data = np.array(data_cube)
        self.width = self.data.shape[2]
        self.height = self.data.shape[1]
        # ROIs
        rois_crop = []
        rois_data = [] 
        for k in range(0,8):
            # ROI positions within windowed frame
            x,y,w,h = int(round(rois[k].x-window["x"])),int(round(rois[k].y-window["y"])),int(round(rois[k].w)),int(round(rois[k].h))
            i1,i2,j1,j2 = y,y+h,x,x+w
            rois_crop.append(Roi(x,y,w,h))
            rois_data.append(self.data[:,i1:i2+1,j1:j2+1])
        self.rois = rois
        self.rois_crop = rois_crop
        self.rois_data = rois_data
     
    def set_ids(self,ids):
        self.ids = ids
        return
    
    def set_window(self,window):
        self.window = window
        return
    
    def set_data(self,data):
        self.data = data
        self.width = data.shape[2]
        self.height = data.shape[1]
        self.set_rois(self.rois)
        return
     
    def set_rois(self,rois):
        # ROIs
        rois_crop = []
        rois_data = []
        for k in range(0,8):
            # ROI positions within windowed frame
            x,y,w,h = int(round(rois[k].x-self.window["x"])),int(round(rois[k].y-self.window["y"])),int(round(rois[k].w)),int(round(rois[k].h))
            i1,i2,j1,j2 = y,y+h,x,x+w
            rois_crop.append(Roi(x,y,w,h))
            rois_data.append(self.data[:,i1:i2+1,j1:j2+1])
        self.rois = rois
        self.rois_crop = rois_crop
        self.rois_data = rois_data
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
        # Calculating the sample's standard deviation over all scientific frames
        sci_sample_std = self.std_rois()
        # Dividing by nr. of frames to get the std on the mean.
        sci_mean_std = sci_sample_std / np.sqrt(N_sci)
        dark_mean_std = dark.std_rois() / np.sqrt(N_dark)
        # Calibrated master frame, corresponding to one DIT (FLAT TBD)
        cal_mean = sci_mean-dark_mean
        cal_mean_std = np.sqrt(sci_mean_std**2+dark_mean_std**2)
        
        # 2) Calibrated sequence of frames
        cal_seq = np.subtract(np.transpose(self.rois_data,axes=[1,0,2,3]),dark_mean)
        cal_seq = np.transpose(cal_seq,axes=[1,0,2,3])
        cal_seq_std = np.sqrt(sci_sample_std**2+dark_mean_std**2)
        
        # SNR for individual frames TBD
        return cal_mean,cal_mean_std,cal_seq,cal_seq_std
        