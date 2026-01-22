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
from time import sleep,time
from nottcontrol import config as nott_config
from nottcontrol.script.lib.nott_database import get_field
from nottcontrol.camera.infratec_interface import InfratecInterface
import nottcontrol.components.pypiezo as pypiezo
import nottcontrol.components.human_interface as human_interface
from nottcontrol import redisclient

pix_to_lamb = list(map(float,nott_config['CAMERA']['pix_to_lamb'].split(',')))
low_lamb = float(nott_config['CAMERA']['low_lamb'])
up_lamb = float(nott_config['CAMERA']['up_lamb'])

class Diagnostics():

    def __init__(self,snr_thresh=5):    
        
        # Camera interface
        infra_interf_ = InfratecInterface()
        framerate_ = infra_interf_.getparam_single(240)
        integtime_ = infra_interf_.getparam_idx_int32(262,0)
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
        dt = 50*(1/self.framerate)
        # Fetch a science frame
        master_sci_ = human_interf.science_frame_sequence(dt)        
        # Fetch a master dark
        master_dark_,bg_noise_ = human_interf.dark_frame_sequence(dt)
        # Fetch a master flat (TBD)
        master_flat_ = master_dark_.copy()
        master_flat_.set_data(np.ones_like(master_dark_.data))
        self.master_dark = master_dark_
        self.master_flat = master_flat_
        self.bg_noise = bg_noise_
        
        # Calibrate science frame 
        master_sci_cal,master_sci_cal_snr = human_interf.calib_frame(master_sci_,master_dark_,master_flat_,bg_noise_)
        # Identify outputs
        outputs_mask_ = human_interf.identify_outputs(master_sci_cal_snr,snr_thresh)
        self.outputs_mask = outputs_mask_
        
        # Identify output dimensions
        
        # Amount of relevant ROIs (=chip outputs)
        Nroi = len(self.outputs_mask.rois_data)
        # ind_outputs : 1st index - N total output px (over all rois)
        #               2nd index - nr. of the ROI the output px is in
        #               3rd,4th index - position within the ROI of the output px
        ind_outputs = np.argwhere(self.outputs_mask.rois_data)
        # Sorting by ROIs
        ind_outputs_sorted_ = [[]]*Nroi
        for px in ind_outputs:
            ind_outputs_sorted_[px[0]].append(px[1:3])
        self.ind_outputs_sorted = ind_outputs_sorted_
        # Determining the top index and height of the outputs from the photometric channels
        ind_outputs_sorted_photo = ind_outputs_sorted_[[0,1,Nroi-2,Nroi-1]]
        output_row_min = np.zeros(4)
        output_row_max = np.zeros(4)
        for i in range(0,4):
            output_row = np.transpose(ind_outputs_sorted_photo[i])[0]
            output_row_min[i] = np.min(output_row)
            output_row_max[i] = np.max(output_row)
        
        self.output_top_idx = np.min(output_row_min)
        self.output_height = np.max(output_row_max) - self.output_top_idx 

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

    def diagnose(self,dt,visual_feedback=True,custom_lambs=False):
    
        if custom_lambs:
            lambs = pix_to_lamb
        else:
            lambs = np.linspace(low_lamb,up_lamb,self.output_height)
    
        # Fetching master science frame and time series of broadband flux/snr in constituent frames
        master_sci_frame,flux_broad,snr_broad = self.human_interf.science_frame_sequence(dt)
        # Dispersed flux,snr of chip outputs in master science frame
        _,_,flux_disp,snr_disp = self.diagnose_frame(master_sci_frame,broadband=False)
        # Timestamps of individual frames
        stamps = master_sci_frame.id
        
        if visual_feedback:
            fig,axs = plt.subplots(4)
            fig.suptitle("Diagnostics of chip outputs in time frame "+str([np.min(stamps),np.max(stamps)]+" (ms)"))
            colors = ['gray','brown','blue','red','black','green','purple','orange']
            markers = ['o','o','x','^','^','x','o','o']            
            for i in range(0,8):
                axs[0].scatter(stamps,flux_broad[i],color=colors[i],marker=markers[i],label="ROI"+str(i+1))
                axs[1].scatter(stamps,snr_broad[i],color=colors[i],marker=markers[i],label="ROI"+str(i+1))
            for i in range(2,6):
                axs[2].scatter(lambs,flux_disp[i],color=colors[i],marker=markers[i],label="ROI"+str(i+1))
                axs[3].scatter(lambs,snr_disp[i],color=colors[i],marker=markers[i],label="ROI"+str(i+1))
            # Differential null
            axs[2].scatter(lambs,flux_disp[4]-flux_disp[3],color=colors[7],marker=markers[7],label="Diff. null")
            axs[3].scatter(lambs,snr_disp[4]-snr_disp[3],color=colors[7],marker=markers[7],label="Diff. null")

            axs[0].set_xlabel("Time (ms)")
            axs[1].set_xlabel("Time (ms)")
            axs[2].set_xlabel("Wavelength (micron)")
            axs[3].set_xlabel("Wavelength (micron)")
            axs[0].set_ylabel("Flux sum (counts)")
            axs[1].set_ylabel("SNR")
            axs[2].set_ylabel("Flux sum (counts)")
            axs[3].set_ylabel("SNR")
    
            axs[0].title.set_text("Broadband Flux")
            axs[1].title_set_text("Broadband SNR")
            axs[1].title_set_text("Dispersed Flux")
            axs[2].title_set_text("Dispersed SNR")
    
            for i in range(0,4):
                axs[i].legend(loc="upper right")
    
            plt.tight_layout()
            # Showing
            fig.canvas.draw()
            fig.canvas.flush_events()
    
        return stamps,flux_broad,snr_broad,flux_disp,snr_disp
    
    # Lower-level: Calculating diagnostics for a single camera frame
    def diagnose_frame(self,frame,master_dark=self.master_dark,master_flat=self.master_flat,bg_noise=self.bg_noise,broadband):
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
        broadband : Boolean
            If True, only compute the broadband flux inside the chip outputs
            If False, only compute the dispersed flux inside the chip outputs
        '''
                
        # Calibrating frame
        frame_cal,frame_cal_snr = self.human_interf.calib_frame(frame,master_dark,master_flat,bg_noise)
        # Fetching signal and signal-to-noise ratios
        rois_s = frame_cal.rois_data
        rois_snr = frame_cal_snr.rois_data
        # Amount of relevant ROIs (=chip outputs)
        Nroi = len(rois_s)
        
        # Gathering fluxes,snr
        flux_broad = np.zeros(Nroi)
        snr_broad = np.zeros(Nroi)
        flux_disp = [np.zeros(self.output_height)]*Nroi
        snr_disp = [np.zeros(self.output_height)]*Nroi
        
        if broadband:
            for i in range(0,Nroi):
                px_outputs = self.ind_outputs_sorted[i]
                for px in px_outputs:
                    k,l = px[0],px[1]
                    flux_px = rois_s[i][k,l]
                    snr_pix = rois_snr[i][k,l]
                    flux_broad[i] += flux_px
                    snr_broad[i] += snr_pix
                    
            # Arrays 'flux_broad' & 'snr_broad' now contain
            # > 1st index a : ROI (chip output) number (0,1,2,...,6,7)
            # flux_broad[a] is the total, broadband flux in chip output a
        
        if not broadband:
            for i in range(0,Nroi):
                px_outputs = self.ind_outputs_sorted[i]
                for px in px_outputs:
                    k,l = px[0],px[1]
                    flux_px = rois_s[i][k,l]
                    snr_px = rois_snr[i][k,l]
                    idx = k-self.output_top_idx
                    flux_disp[i][idx] += flux_px
                    snr_disp[i][idx] += snr_px
        
            # Arrays 'flux_disp' & 'snr_disp' now contain
            # > 1st index a : ROI (chip output) number (0,1,2,...,6,7)
            # > 2nd index b : index of pixel row within the ROI (0,1,...,self.output_height)
            # flux[a][b] is then the flux value in ROI a, summed for all output (identified by SNR criterion) pixels in the row b.
        
        return flux_broad,snr_broad,flux_disp,snr_disp
        
        
        