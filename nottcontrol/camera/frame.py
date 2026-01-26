# -*- coding: utf-8 -*-
"""
Created on Wed Jan 14 12:54:01 2026

@author: Thomas

This class defines a camera frame and ROIs.
Functionalities are provided to retrieve data of interest from the ROIs.

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
    roi_i = list(map(int,nott_config['CAMERA']['ROI '+str(i+1)].split(',')))
    if len(roi_i) != 4:
        raise Exception('Invalid ROI config')
    rois_cfg.append(Roi(roi_i[0],roi_i[1],roi_i[2],roi_i[3]))

class Frame():
    
    def __init__(self,id_,window_=window_cfg,rois_=rois_cfg):
        
        # Setting frame ID
        # Frame ID = String of Windows machine time in "Y%m%d_H%M%S" format, up to millisecond precision. Date and time are separated by an underscore.
        self.id = id_
        # Setting window
        self.window = window_
        # Fetch data from local machine
        Ymd,HMS = self.id.split(sep="_")[0],self.id.split(sep="_")[1]
        directory = Path(frame_directory).joinpath(Ymd)
        filename = HMS+'.png'
        img_path = str(Path.joinpath(directory,filename))
        img = Image.open(img_path)
        data_ =  np.asarray(img)
        self.data = data_
        self.width = data_.shape[1]
        self.height = data_.shape[0]
        # ROIs
        rois_crop_ = []
        rois_data_ = [] 
        for k in range(0,8):
            # ROI positions within windowed frame
            x,y,w,h = int(rois_[k].x-window_["x"]),int(rois_[k].y-window_["y"]),int(rois_[k].w),int(rois_[k].h)
            i1,i2,j1,j2 = y,y+h,x,x+w
            rois_crop_.append(Roi(x,y,w,h))
            rois_data_.append(data_[i1:i2+1,j1:j2+1])
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
        self.width = data_.shape[1]
        self.height = data_.shape[0]
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
            rois_data_.append(self.data[i1:i2+1,j1:j2+1])
        self.rois = rois_
        self.rois_crop = rois_crop_
        self.rois_data = rois_data_
        return
        
    def copy(self):
        frame_copy = Frame(self.id)
        return frame_copy
     
    def get_roi(self,idx):
        
        # Calculating min,max,mean,sum
        calc = BrightnessCalculator(self.rois_data)
        calc.run()
        
        return calc.results, rois_data
            
        

