# -*- coding: utf-8 -*-
"""
Created on Wed Jan 14 11:45:30 2026

@author: Thomas

This class bundles functionalities for
- retrieving frames from the infrared camera
- calculating diagnostics of the dispersed chip outputs in those exchanged frames
- providing visual feedback on the calculated diagnostics

"""

from time import sleep,time
import numpy as np
import matplotlib.pyplot as plt
from nottcontrol import config as nott_config
from nottcontrol.camera.infratec_interface import InfratecInterface
import nottcontrol.components.pypiezo as pypiezo
import nottcontrol.components.human_interface as human_interface
from nottcontrol import redisclient

pix_to_lamb = nott_config.getarray('CAMERA','pix_to_lamb')
low_lamb = float(nott_config['CAMERA']['low_lamb'])
up_lamb = float(nott_config['CAMERA']['up_lamb'])

class Diagnostics():

    def __init__(self,snr_thresh=5,framerate_=100):    
        
        # Camera interface
        infra_interf_ = InfratecInterface()
        # TBD 
        #framerate_ = infra_interf_.getparam_single(240)
        #integtime_ = infra_interf_.getparam_idx_int32(262,0)
        self.infra_interf = infra_interf_
        self.framerate = framerate_       # in Hz
        #self.integtime = integtime_       # in microseconds
        # Piezo interface
        piezo_interf_ = pypiezo.piezointerface()
        self.piezo_interf = piezo_interf_
        # Redis client
        redis_client_ = redisclient.RedisClient(human_interface.dburl)
        self.redis_client = redis_client_
        # Human interface 
        # TBD : Offset
        human_interf_ = human_interface.HumInt(interf=piezo_interf_,db_server=redis_client_,pad=0.08,offset=5.0)
        self.human_interf = human_interf_
        
        # Determine pixels corresponding to outputs
        # To Do: Guarantee that this function is called when not in a null state.
        #        Otherwise, the simple SNR criterion used will not pick up the output positions of the two dark outputs.
        dt = 50*(1/self.framerate)
        # Fetch a master dark
        master_dark_,bg_noise_ = self.human_interf.dark_frame_sequence(dt)
        # Fetch a master flat (TBD)
        master_flat_ = master_dark_.copy()
        master_flat_.set_data(np.ones_like(master_dark_.data))
        self.master_dark = master_dark_
        self.master_flat = master_flat_
        self.bg_noise = bg_noise_
        
        # Fetch a science frame
        master_sci_,_ = self.human_interf.science_frame_sequence(dt) 
        # Calibrate science frame 
        master_sci_cal,master_sci_cal_snr = self.human_interf.calib_frame(master_sci_,master_dark_,master_flat_,bg_noise_)
        # Identify outputs
        outputs_mask_ = self.human_interf.identify_outputs(master_sci_cal_snr,True,snr_thresh)
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
        ind_outputs_sorted_ = np.array(ind_outputs_sorted_)
        self.ind_outputs_sorted = ind_outputs_sorted_
        # Determining the top index and height of the outputs from the photometric channels
        ind_outputs_sorted_photo = ind_outputs_sorted_[[0,1,Nroi-2,Nroi-1]]
        output_row_min = np.zeros(4)
        output_row_max = np.zeros(4)
        for i in range(0,4):
            output_row = np.transpose(ind_outputs_sorted_photo[i])[0]
            output_row_min[i] = np.min(output_row)
            output_row_max[i] = np.max(output_row)
        
        self.output_top_idx = int(np.min(output_row_min))
        self.output_height = int(np.max(output_row_max) - self.output_top_idx)+1

    def set_cam_framerate(self,framerate):
        # framerate in Hz
        # TBD 
        framerate_64 = np.array([framerate],dtype=np.float64)
        framerate_32 = framerate_64.astype(np.float32)[0]
        self.infra_interf.setparam_single(240,framerate_32)
        self.framerate = framerate_32
        return
    
    def set_cam_integtime(self,integtime):
        # integtime in microseconds
        # TBD 
        integtime_64 = np.array([integtime],dtype=np.int64)
        integtime_32 = integtime_64.astype(np.int32)[0]
        # Using index 0 as camera is in Single Integration Mode
        self.infra_interf.setparam_idx_int32(262,0,integtime_32)
        self.integtime = integtime_32
        return

    def diagnose(self,dt,visual_feedback=True,visual_feedback_flux=True,custom_lambs=False):
    
        if custom_lambs:
            lambs = pix_to_lamb
            if len(lambs) != self.output_height:
                raise Exception("The length of the custom list of wavelengths" + str(len(lambs)) + " does not match the size of the outputs " + str(self.output_height))
        else:
            lambs = np.linspace(low_lamb,up_lamb,self.output_height)
    
        # Fetching master science frame and constituent, individual science frames
        master_sci_frame,sci_frames = self.human_interf.science_frame_sequence(dt)
        # Broadband flux,snr of chip outputs in single science frames
        fluxes_broad = []
        snrs_broad = []
        for sci_frame in sci_frames:
            flux_broad,snr_broad,_,_ = self.diagnose_frame(sci_frame,broadband=True)
            fluxes_broad.append(flux_broad)
            snrs_broad.append(snr_broad)
        fluxes_broad = np.transpose(fluxes_broad)
        snrs_broad = np.transpose(snrs_broad)
        # Dispersed flux,snr of chip outputs in master science frame
        _,_,flux_disp,snr_disp = self.diagnose_frame(master_sci_frame,broadband=False)
        # Timestamps of individual frames
        ids = master_sci_frame.id
        stamps = []
        for id_s in ids:
            HMS = int(id_s.split(sep="_")[1])
            stamps.append(HMS)
        # Normalizing to start
        stamps = np.array(stamps)-stamps[0]
        
        if visual_feedback:
            
            fig,axs = plt.subplots(4,gridspec_kw={"height_ratios": [4, 1.5, 1.5, 1],"hspace": 0.15}, figsize=(10,8))
            fig.suptitle("Diagnostics of chip outputs in time frame  ["+str(ids[0])+" , "+str(ids[-1])+"]  (ms)")
            colors = ['gray','brown','blue','red','black','green','purple','orange']
            markers = ['o','o','x','^','^','x','o','o']  
            
            if visual_feedback_flux:
                
                for i in range(0,8):
                    axs[0].scatter(stamps,fluxes_broad[i],color=colors[i],marker=markers[i],label="ROI"+str(i+1))
            
                # Bright
                axs[1].scatter(lambs,flux_disp[2],color=colors[2],marker=markers[2],s=10,label="ROI3 / B1")
                axs[1].scatter(lambs,flux_disp[5],color=colors[5],marker=markers[5],s=12,label="ROI6 / B2")
                # Null
                axs[2].scatter(lambs,flux_disp[3],color=colors[3],marker=markers[3],s=10,label="ROI4 / D1")
                axs[2].scatter(lambs,flux_disp[4],color=colors[4],marker=markers[4],s=12,label="ROI5 / D2")
                # Differential null
                diff = flux_disp[4]-flux_disp[3]
                axs[3].scatter(lambs,diff,color='magenta',marker=markers[7],label="Diff. null")
                axs[3].set_ylim(np.min(diff),np.max(diff))
    
                axs[0].set_xlabel("Time (ms)")
                for i in range(1,4):
                    axs[i].set_xlabel("Wavelength (um)")
                for i in range(0,4):
                    axs[i].set_ylabel("counts")
                
            else:
                
                for i in range(0,8):
                    axs[0].scatter(stamps,snrs_broad[i],color=colors[i],marker=markers[i],label="ROI"+str(i+1))
            
                # Bright
                axs[1].scatter(lambs,snr_disp[2],color=colors[2],marker=markers[2],s=10,label="ROI3 / B1")
                axs[1].scatter(lambs,snr_disp[5],color=colors[5],marker=markers[5],s=12,label="ROI6 / B2")
                # Null
                axs[2].scatter(lambs,snr_disp[3],color=colors[3],marker=markers[3],s=10,label="ROI4 / D1")
                axs[2].scatter(lambs,snr_disp[4],color=colors[4],marker=markers[4],s=12,label="ROI5 / D2")
                # Differential null
                diff = snr_disp[4]-snr_disp[3]
                axs[3].scatter(lambs,diff,color='magenta',marker=markers[7],label="D2-D1")
                axs[3].set_ylim(np.min(diff),np.max(diff))
    
                axs[0].set_xlabel("Time (ms)")
                for i in range(1,4):
                    axs[i].set_xlabel("Wavelength (um)")
                for i in range(0,4):
                    axs[i].set_ylabel("Output SNR")
    
            # Legend
            for i in range(0,4):
                axs[i].legend(loc="upper right")
                
            # Showing
            plt.tight_layout()
            plt.subplots_adjust(right=0.85)     
            plt.show()
    
        return stamps,fluxes_broad,snrs_broad,flux_disp,snr_disp
    
    # Lower-level: Calculating diagnostics for a single camera frame
    # TO BE CLEANED
    def diagnose_frame(self,frame,broadband,master_dark=None,master_flat=None,bg_noise=None):
        '''
        Parameters
        ----------
        frame : Instance of the Frame class
            Infrared camera frame  
        broadband : Boolean
            If True, only compute the broadband flux inside the chip outputs
            If False, only compute the dispersed flux inside the chip outputs
        master_dark : Instance of the Frame class
            Master dark frame
        master_flat : Instance of the Frame class
            Master flat frame
        bg_noise : Instance of the Frame class
            Background noise frame
        '''
            
        # Setting defaults
        if master_dark is None:
            master_dark = self.master_dark
        if master_flat is None:
            master_flat = self.master_flat
        if bg_noise is None:
            bg_noise = self.bg_noise
        
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
        flux_disp = []
        snr_disp = []
        
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
                # Sum over columns for each ROI
                flux_disp.append(rois_s[i].sum(axis=1)[self.output_top_idx:self.output_top_idx+self.output_height])
                snr_disp.append(rois_snr[i].sum(axis=1)[self.output_top_idx:self.output_top_idx+self.output_height])
                #px_outputs = self.ind_outputs_sorted[i]
                #for px in px_outputs:
                #    k,l = px[0],px[1]
                #    flux_px = rois_s[i][k,l]
                #    snr_px = rois_snr[i][k,l]
                #    idx = k-self.output_top_idx
                #    flux_disp[i][idx] += flux_px
                #    snr_disp[i][idx] += snr_px
        
            # Arrays 'flux_disp' & 'snr_disp' now contain
            # > 1st index a : ROI (chip output) number (0,1,2,...,6,7)
            # > 2nd index b : index of pixel row within the ROI (0,1,...,self.output_height)
            # flux[a][b] is then the flux value in ROI a, summed for all output (identified by SNR criterion) pixels in the row b.
        
        return flux_broad,snr_broad,np.array(flux_disp),np.array(snr_disp)
        
        
        