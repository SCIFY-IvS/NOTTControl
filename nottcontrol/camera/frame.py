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

# Location of frames on the machine
frame_directory = str(nott_config['DEFAULT']['frame_directory'])

# Camera window position and size (dictionary format)
window_cfg = dict.fromkeys(["w","h","x","y"])
for key in window_cfg.keys():
    window_cfg[key] = int(nott_config['CAMERA']['window_'+key]) # string to int
    
# Camera ROIs' positions and sizes : not linked to outputs (list format)
rois_cfg = []
rois_w = set() # sets to contain ROIs widths and heights
rois_h = set()
roi_index = 1
stop = False
while not stop:
    try:
        roi = nott_config.getarray('CAMERA', 'ROI '+str(roi_index),np.float32) # np array of floats
    except:
        stop = True
    else:
        if len(roi) != 4:
            raise Exception('Invalid ROI configuration, please check the configuration file for correct x,y,w,h assignments.')
        # Checking whether all ROIs have the same dimension. Throwing exception if not the case.
        rois_w.add(int(round(roi[2])))
        rois_h.add(int(round(roi[3])))
        if len(rois_w) != 1 or len(rois_h) != 1:
            raise Exception('Invalid ROI configuration, please check that all ROIs have the same dimensions in the configuration file.')
        # Storing roi
        rois_cfg.append(Roi(roi[0],roi[1],roi[2],roi[3],roi_index))
        roi_index += 1    

class Frame(object):
    # This class represents a sequence of frames, taken by the infrared camera.
    def __init__(self,ids,integtimes=[],window=window_cfg,rois=rois_cfg):
        """
        Parameters
        ----------
        ids : list of strings
            IDs of the constituent frames.
            Frame ID = Windows machine time in string "Y%m%d_H%M%S" format, up to millisecond precision. Date and time are separated by an underscore.
        integtimes : list of floats
            Integration times of the constituent frames.
        window : dictionary (keys: string, values: int)
            Contains the infrared camera window's position and size, as integers (px), respectively under keys "x"&"y" (column,row of top-left corner) and "w"&"h" (width,height).
        rois : list (list index : ROI index - 1, values : objects of ROI class)
            Contains the infrared camera regions of interest's positions and sizes, as ROI objects. 
        
        Fields
        ------
        rois_crop : list (list index : ROI index - 1, values : objects of ROI class)
            Same as "rois", but with the ROI positions adjusted to the camera window (instead of defined wrt the full frame)
        rois_data : numpy array (array index : ROI index - 1, values : numpy arrays)
            Contains the data, of all recorded frames, within each ROI. Obtained by slicing the loaded data cube. 
            Note: As this field contains data, it is a numpy array - and not a list - to promote efficiency of data handling.
        """
        # Setting frame IDs
        self.ids = ids
        # Setting frame integration times
        self.integtimes = integtimes
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
        for roi in rois:
            # ROI positions within windowed frame
            x,y,w,h = int(round(roi.x-window["x"])),int(round(roi.y-window["y"])),int(round(roi.w)),int(round(roi.h))
            i1,i2,j1,j2 = y,y+h,x,x+w
            rois_crop.append(Roi(x,y,w,h,roi.idx))
            rois_data.append(self.data[:,i1:i2+1,j1:j2+1])
        self.rois = rois
        self.rois_crop = rois_crop
        self.rois_data = np.array(rois_data)
     
    def set_ids(self,ids):
        self.ids = ids
        return
    
    def set_window(self,window):
        self.window = window
        return
    
    @property 
    def link_to_channels(self):
        """
        Description
        -----------
        Use the link between channels (photo,bright,dark,background) and matching ROIs (as specified in config.ini)
        to associate camera data (captured within the matching ROI) to each channel.
        
        Returns
        -------
        (1) channels_roi : "rois" as a dictionary (instead of a list)
        (2) channels_data : "rois_data" as a dictionary (instead of a numpy array).
        Dictionary key : channel name (string)
        Dictionary value : (1) ROI Object 
                           (2) data registered in matching ROI (numpy array)
        """
        # Camera ROIs' positions and sizes : matched to outputs (dictionary format)
        channel_labels = nott_config.getarray('CAMERA', 'channel_labels', str) # np array of strings
        roi_indices = nott_config.getarray('CAMERA', 'roi_indices', np.int32) # np array of ints
        channels_roi = dict.fromkeys(channel_labels)
        channels_data = dict.fromkeys(channel_labels)
        for i,channel_label in enumerate(channels_data):
            roi_index = roi_indices[i]
            channels_roi[channel_label] = self.rois[roi_index-1]
            channels_data[channel_label] = self.rois_data[roi_index-1]
        return channels_roi,channels_data
    
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
        for roi in rois:
            # ROI positions within windowed frame
            x,y,w,h = int(round(roi.x-self.window["x"])),int(round(roi.y-self.window["y"])),int(round(roi.w)),int(round(roi.h))
            i1,i2,j1,j2 = y,y+h,x,x+w
            rois_crop.append(Roi(x,y,w,h,roi.idx))
            rois_data.append(self.data[:,i1:i2+1,j1:j2+1])
        self.rois = rois
        self.rois_crop = rois_crop
        self.rois_data = np.array(rois_data)
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
    
    @property
    def master_full(self):
        # Calculates a master frame (=mean counts per DIT; detector integration time) and the corresponding std map
        # Does so for the full camera frame

        # Amount of frames
        N = len(self.data)
        # Calculating the master frame from the individual frames
        master_frame = self.av_full()
        # Dividing sample std by nr. of frames to get the std on the mean
        master_frame_std = self.std_full() / np.sqrt(N)
    
        return master_frame,master_frame_std
    
    @property
    def master_rois(self):
        # Calculates a master frame (= mean counts per DIT; detector integration time) and the corresponding std map
        # ! Limiting calculations to data within the ROIs for efficiency
        
        # Amount of frames
        N = len(self.data)
        # Calculating the master frame from the individual frames
        master_frame = self.av_rois()
        # Dividing sample std by nr. of frames to get the std on the mean
        master_frame_std = self.std_rois() / np.sqrt(N)
    
        return master_frame,master_frame_std
      
     def calib_seq(self,dark,flat=None,full=False,dark_mean=None,dark_mean_std=None):
        # Compute a sequence of calibrated individual frames and calculate the corresponding std map for each
        # "dark" and "flat" denote series of dark (shutters closed) and flat (even illumination) frames, are both instances of the Frame class
        
        # Mean dark frame and corresponding std frame (only calculated if not provided)
        if dark_mean is None or dark_mean_std is None:
            if not full:
                dark_mean,dark_mean_std = dark.master_rois
            else:
                dark_mean,dark_mean_std = dark.master_full
        
        if not full:
            # Calibrate the sequence of frames (= one DIT each; detector integration time), calculate total std (science sample std + dark mean std)
            cal_seq = self.rois_data - dark_mean[:, np.newaxis, :, :]
            cal_seq_std = np.sqrt(self.std_rois()**2+dark_mean_std**2)
        else:
            # Calibrate the sequence of frames (= one DIT each; detector integration time), calculate total std (science sample std + dark mean std)
            cal_seq = self.data - dark_mean[np.newaxis, :, :]
            cal_seq_std = np.sqrt(self.std_full()**2+dark_mean_std**2)
            
        return cal_seq,cal_seq_std
        
    def calib_master(self,dark,flat=None,full=False,dark_mean=None,dark_mean_std=None):
        # Compute the calibrated master frame and calculate the corresponding std map
        # "dark" and "flat" denote series of dark (shutters closed) and flat (even illumination) frames, are both instances of the Frame class
        
        # Mean dark frame and corresponding std frame (only calculated if not provided)
        if dark_mean is None or dark_mean_std is None:
            if not full:
                dark_mean,dark_mean_std = dark.master_rois
            else:
                dark_mean,dark_mean_std = dark.master_full
        
        if not full:
            # Mean science and dark frames and corresponding std frames
            sci_mean,sci_mean_std = self.master_rois
            # Calibrate the master science frame (= one DIT; detector integration time), calculate total std (science mean std + dark mean std)
            cal_mean = sci_mean-dark_mean
            cal_mean_std = np.sqrt(sci_mean_std**2+dark_mean_std**2)
        else:
            # Mean science and dark frames and corresponding std frames
            sci_mean,sci_mean_std = self.master_full
            # Calibrate the master science frame (= one DIT; detector integration time), calculate total std (science mean std + dark mean std)
            cal_mean = sci_mean-dark_mean
            cal_mean_std = np.sqrt(sci_mean_std**2+dark_mean_std**2)
            
        return cal_mean,cal_mean_std
    
    def calib(self,dark,flat=None,full=False):
        # Function that combines above two into one.
        
        if not full:
            dark_mean,dark_mean_std = dark.master_rois
        else:
            dark_mean,dark_mean_std = dark.master_full
        
        cal_mean,cal_mean_std = self.calib_master(dark,flat,full,dark_mean,dark_mean_std)
        cal_seq,cal_seq_std = self.calib_seq(dark,flat,full,dark_mean,dark_mean_std)
            
        return cal_mean,cal_mean_std,cal_seq,cal_seq_std  
      
        