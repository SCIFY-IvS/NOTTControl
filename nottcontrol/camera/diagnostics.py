# -*- coding: utf-8 -*-
"""
Created on Wed Jan 14 11:45:30 2026

@author: Thomas

This class bundles functionalities for
- retrieving frames from the infrared camera
- calculating diagnostics of the dispersed chip outputs in those exchanged frames
- providing visual feedback on the calculated diagnostics

"""

import numpy as np
import matplotlib.pyplot as plt
from nottcontrol import config as nott_config
from nottcontrol.camera.infratec_interface import InfratecInterface
import nottcontrol.components.pypiezo as pypiezo
import nottcontrol.components.human_interface as human_interface
from nottcontrol import redisclient

pix_to_lamb = list(map(float,nott_config['CAMERA']['pix_to_lamb'].split(',')))

class Diagnostics():

    def __init__(self,snr_thresh=5):    
        
        # Camera interface
        infra_interf_ = InfratecInterface()
        framerate_ = infra_interf_.getparam_single(240)
        integtime_ = infra_interf_.getparam_idx_int32(262)
        self.infra_interf = infra_interf_
        self.framerate = framerate_       # in Hz
        self.integtime = 10**6*integtime_ # in seconds
        # Piezo interface
        piezo_interf_ = pypiezo.piezointerface()
        self.piezo_interf = piezo_interf_
        # Redis client
        redis_client_ = redisclient.RedisClient(human_interface.dburl)
        self.redis_client = redis_client_
        # Human interface
        human_interf_ = human_interface.HumInt(interf=piezo_interf_,db_server=redis_client_,pad=0.08,offset=5.0)
        self.human_interf = human_interf_
        
        # Determine pixels corresponding to outputs
        # To Do: Guarantee that this function is called when not in a null state.
        #        Otherwise, the simple SNR criterion used will not pick up the output positions of the two dark outputs.
        exptime = 100*self.integtime
        # Fetch a science frame
        master_sci_ = human_interf.science_frame_sequence(exptime)        
        # Fetch a master dark
        master_dark_,bg_noise_ = human_interf.dark_frame_sequence(exptime)
        # Fetch a master flat (TBD)
        master_flat_ = master_dark_.copy()
        master_flat_.set_data(np.ones_like(master_dark_.data))
        # Calibrate science frame 
        master_sci_cal,master_sci_cal_snr = human_interf.calib_frame(master_sci_,master_dark_,master_flat_,bg_noise_)
        # Identify outputs
        outputs_mask_ = human_interf.identify_outputs(master_sci_cal_snr,snr_thresh)
        
        self.master_dark = master_dark_
        self.master_flat = master_flat_
        self.bg_noise = bg_noise_
        self.outputs_mask = outputs_mask_

    def set_cam_framerate(self,framerate):
        framerate_64 = np.array([framerate],dtype=np.float64)
        framerate_32 = framerate_64.astype(np.float32)[0]
        self.infra_interf.setparam_single(240,framerate_32)
        return
    
    def set_cam_integtime(self,integtime):
        integtime_64 = np.array([integtime],dtype=np.int64)
        integtime_32 = integtime_64.astype(np.int32)[0]
        # Using index 0 as camera is in Single Integration Mode
        self.infra_interf.setparam_idx_int32(262,0,integtime_32)
        return

    # Upper-level: Data exchange and synchronization + calculating diagnostics for a demanded time series
    def diagnose(self,dt,visual_feedback):
    
        # For each stamp in given time series (now, now+dt):
        # Fetch frame data from local storage, corresponding to given timestamp
        # Instantiate frame data as a Frame object
        
        # Perform diagnostic function on each single frame
        
        # Use above outputs to calculate the final diagnostic series
    
        # Provide the necessary visual feedback
    
    # Lower-level: Calculating diagnostics for a single camera frame
    def diagnose_frame(self,frame,master_dark=self.master_dark,master_flat=self.master_flat,bg_noise=self.bg_noise,visual_feedback=False):
        '''
        Parameters
        ----------
        frame : Instance of the Frame class
            Infrared camera frame  
        master_dark : Instance of the Frame class
            Master dark frame
        master_flat : Instance of the Frame class
            Master flat frame
        bg_noise : Instance of the Frame class
            Background noise frame
        visual_feedback : boolean
            True is visual feedback is desired.
        '''
        
        # TO BE CHECKED
        
        # Calibrating frame
        frame_cal,frame_cal_snr = self.human_interf.calib_frame(frame,master_dark,master_flat,bg_noise)
        # Fetching signal and signal-to-noise ratios
        rois_s = frame_cal.rois_data
        rois_snr = frame_cal_snr.rois_data
        rois_outputs = self.outputs_mask.rois_data
        # Amount of ROIs
        Nroi = len(rois_s)
        # ind_outputs : 1st index - N total output px (over all rois)
        #               2nd index - roi number of the output px
        #               3rd,4th index - index within roi of the output px
        ind_outputs = np.argwhere(rois_outputs)
        # Sorting by rois
        ind_outputs_sorted = [[]]*Nroi
        for px in ind_outputs:
            ind_outputs_sorted[px[0]].append(px[1:3])
        # Computing top and height of outputs (amount of pxs)
        ind_outputs_vertical = [[]]*Nroi
        for i in range(0,Nroi):
            ind_vertical = np.transpose(ind_outputs_sorted[i])[0]
            top_index = np.min(ind_vertical)
            height = np.max(ind_vertical)-top_index
            ind_outputs_vertical.append([top_index,height])
        # Gathering fluxes,snr
        flux = [np.zeros(ind_outputs_vertical[roi_ind][1]) for roi_ind in range(0,Nroi)]*Nroi
        snr = flux
        for j in range(0,Nroi):
            px_outputs = ind_outputs_sorted[j]
            top_index = ind_outputs_vertical[j][0]
            for px in px_outputs:
                idx = px[0]-top_index
                k,l = px[0],px[1]
                flux_px = rois_s[j][k,l]
                snr_px = rois_snr[j][k,l]
                flux[j][idx] += flux_px
                snr[j][idx] += snr_px
        
        # Flux, snr now contain flux & snr values for each output pixel row, summed over all columns of the output in that row
        # 1st index : roi index (0 ... 9)
        # 2nd index : output pixel row 
        
        return flux,snr
        
        
        