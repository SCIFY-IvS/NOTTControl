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

class Diagnostics(object):

    def __init__(self,infra_interf=None,piezo_interf=None,redis_client=None,human_interf=None,use_geom=True,snr_thresh=5,framerate=100):    
        """
        Parameters
        ----------
        use_geom : boolean
            If True, the outputs are identified as all pixels within the ROIs
            If False, the outputs are identified as all pixels with SNR > snr_thresh
        snr_thresh : float
            SNR threshold for output identification
        """
        
        #-----------------------#
        # Setting up interfaces |
        #-----------------------#
        if infra_interf is None:
            # Camera interface
            infra_interf = InfratecInterface()
            # TBD 
            #framerate = infra_interf.getparam_single(240)
            #integtime = infra_interf.getparam_idx_int32(262,0)
            self.framerate = framerate       # in Hz
            #self.integtime = integtime      # in microseconds
        if piezo_interf is None:
            # Piezo interface
            piezo_interf = pypiezo.piezointerface()
        if redis_client is None:
            # Redis client
            redis_client = redisclient.RedisClient(human_interface.dburl)
            
        self.infra_interf = infra_interf
        self.piezo_interf = piezo_interf
        self.redis_client = redis_client
            
        if human_interf is None:
            # Human interface 
            # TBD : Offset
            human_interf = human_interface.HumInt(interf=piezo_interf,db_server=redis_client,pad=0.08,offset=5.0)
        else:
            # Overwrite piezo interface and redis client with the ones tied to input human interface.
            self.piezo_interf = human_interf.interf
            self.redis_client = human_interf.ts
            
        self.human_interf = human_interf
        
        #---------------------------#
        # Determining output pixels | For use_geom = False: guarantee that this function is called when not in a state of null.
        #---------------------------#
        
        # Getting a calibrated science frame
        dt = 100*(1/self.framerate)
        sci_frames = self.human_interf.science_frame_sequence(dt)
        dark_frames = self.human_interf.dark_frame_sequence(dt)
        self.dark_frames = dark_frames
        self.rois = sci_frames.rois
        self.channels = list(self.rois.keys())
        cal_mean,cal_std,_,_ = sci_frames.calib(dark_frames)
        cal_snr = np.divide(cal_mean,cal_std)
        # Identifying the outputs
        outputs_pos = self.human_interf.identify_outputs(cal_snr,use_geom,snr_thresh)
        self.outputs_pos = outputs_pos
        # Determining indices of photometric channels
        photo_idx = []
        for i,channel_label in enumerate sci_frames.rois:
            if list(channel_label)[0] == "P":
                photo_idx.append(i)     
        # Determining the top index and height of the outputs from the selected photometric channel(s)
        photo_outputs_pos = outputs_pos[photo_idx]
        # output_pxs : 1st index - N total output px in the photo ROIs
        #              2nd index - 0 = Index of the photo ROI
        #                          1,2 - Position within the ROI of the output px
        output_pxs = np.argwhere(photo_outputs_pos)
        row_ind = output_pxs[:,1]
        self.output_top_idx = int(np.min(row_ind))
        self.output_height = int(np.max(row_ind)) - self.output_top_idx+1

    def diagnose(self,dt,visual_feedback=True,visual_feedback_flux=True,custom_lambs=False):
    
        if custom_lambs:
            lambs = pix_to_lamb
            if len(lambs) != self.output_height:
                raise Exception("The length of the custom list of wavelengths" + str(len(lambs)) + " does not match the size of the outputs " + str(self.output_height))
        else:
            lambs = np.linspace(low_lamb,up_lamb,self.output_height)
    
        # Fetch science frames
        sci_frames = self.human_interf.science_frame_sequence(dt)
        # Calibration
        cal_mean,cal_std,cal_seq,cal_seq_std = sci_frames.calib(self.dark_frames)
        cal_mean_snr = np.divide(cal_mean,cal_std)
        cal_seq_snr = np.divide(np.transpose(cal_seq,axes=[1,0,2,3]),cal_seq_std)
        cal_seq_snr = np.transpose(cal_seq_snr,axes=[1,0,2,3])
        # Masking outputs
        cal_mean = cal_mean*self.outputs_pos
        cal_mean_snr = cal_mean_snr*self.outputs_pos
        # Time series of broadband flux: sum output pixels' signal in each frame
        fluxes_broad = cal_seq.sum(axis=(2,3))
        snrs_broad = cal_seq_snr.sum(axis=(2,3)) 
        # Dispersed flux: sum output pixels' signal row-per-row in master frame
        flux_disp = cal_mean.sum(axis=2)[self.output_top_idx:self.output_top_idx+self.output_height]
        snr_disp = cal_mean_snr.sum(axis=2)[self.output_top_idx:self.output_top_idx+self.output_height]
    
        # Timestamps of individual frames
        ids = sci_frames.ids
        stamps = []
        for id_s in ids:
            HMS = int(id_s.split(sep="_")[1]) # string to int
            stamps.append(HMS)
        # Normalizing to start
        stamps = np.array(stamps)-stamps[0]
    
        
        if visual_feedback:
            
            # Only make figure if there isn't already one active
            if not hasattr(self, '_diag_fig') or not plt.fignum_exists(getattr(self, '_diag_fig_num', -1)):
                plt.ion()
                self._diag_fig, self._diag_axs = plt.subplots(4, gridspec_kw={"height_ratios": [4, 1.5, 1.5, 1], "hspace": 0.15}, figsize=(10,8))
                self._diag_fig_num = self._diag_fig.number
            
            fig, axs = self._diag_fig, self._diag_axs
            
            # Clear axes
            for ax in axs:
                ax.clear()

            fig.suptitle("Diagnostics of chip outputs in time frame  ["+str(ids[0])+" , "+str(ids[-1])+"]  (ms)")
            colors = ['gray','brown','blue','red','black','green','purple','orange','pink','pink']
            markers = ['o','o','x','^','^','x','o','o','x','x']  
            
            if visual_feedback_flux:
                
                for i in range(0, len(channels)):
                    channel = self.channels[i]
                    roi_idx = self.rois[channel].idx
                    axs[0].scatter(stamps,fluxes_broad[i],color=colors[idx],marker=markers[idx],label="ROI"+str(idx))
                    
                    if channel == "I1" or channel == "I4":
                        plot_idx = 1
                    if channel == "I2" or channel == "I3":
                        plot_idx = 2
                    axs[plot_idx].scatter(lambs,flux_disp[i],color=colors[roi_idx],marker=markers[roi_idx],s=10,label="ROI"+roi_idx+"/"+str(channel))
                    
                if "I2" in channels and "I3" in channels:
                    idx_I2 = np.argwhere(np.array(channels)=="I2")[0][0]
                    idx_I3 = np.argwhere(np.array(channels)=="I3")[0][0]
                    diff = flux_disp[idx_I3]-flux_disp[idx_I2]
                    axs[3].scatter(lambs,diff,color="magenta",marker=markers[7],label="I3-I2")
                    axs[3].set_ylim(np.min(diff),np.max(diff))
                    
                axs[0].set_xlabel("Time (ms)")
                for i in range(1,4):
                    axs[i].set_xlabel("Wavelength (um)")
                for i in range(0,4):
                    axs[i].set_ylabel("counts")
                
            else:
                
                for i in range(0, len(channels)):
                    channel = self.channels[i]
                    roi_idx = self.rois[channel].idx
                    axs[0].scatter(stamps,snrs_broad[i],color=colors[idx],marker=markers[idx],label="ROI"+str(idx))
                    
                    if channel == "I1" or channel == "I4":
                        plot_idx = 1
                    if channel == "I2" or channel == "I3":
                        plot_idx = 2
                    axs[plot_idx].scatter(lambs,snr_disp[i],color=colors[roi_idx],marker=markers[roi_idx],s=10,label="ROI"+roi_idx+"/"+str(channel))
                    
                if "I2" in channels and "I3" in channels:
                    idx_I2 = np.argwhere(np.array(channels)=="I2")[0][0]
                    idx_I3 = np.argwhere(np.array(channels)=="I3")[0][0]
                    diff = snr_disp[idx_I3]-snr_disp[idx_I2]
                    axs[3].scatter(lambs,diff,color="magenta",marker=markers[7],label="I3-I2")
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
            fig.canvas.draw()
            fig.canvas.flush_events()
    
        return stamps,fluxes_broad,snrs_broad,flux_disp,snr_disp
            