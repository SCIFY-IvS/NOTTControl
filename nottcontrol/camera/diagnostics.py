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

class Diagnostics(object):
    
    pix_to_lamb = nott_config.getarray('CAMERA','pix_to_lamb')
    low_lamb = float(nott_config['CAMERA']['low_lamb'])
    up_lamb = float(nott_config['CAMERA']['up_lamb']) 
    dlamb = up_lamb-low_lamb    

    def __init__(self,infra_interf=None,piezo_interf=None,redis_client=None,human_interf=None,use_geom=True,snr_thresh=5):    
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
            human_interf = human_interface.HumInt(interf=piezo_interf,db_server=redis_client,shutter_pad=10,pad=0.08,offset=5.0)
        else:
            # Overwrite piezo interface and redis client with the ones tied to input human interface.
            self.piezo_interf = human_interf.interf
            self.redis_client = human_interf.ts
            
        self.human_interf = human_interf
        
        #---------------------------#
        # Determining output pixels | For use_geom = False: guarantee that this code block is called when not in a state of null.
        #---------------------------#
        
        # Getting a calibrated science frame
        dt = 5.
        self.human_interf.shutter_set([1,1,1,1],wait=True)
        sci_frames = self.human_interf.science_frame_sequence(dt)
        dark_frames = self.human_interf.dark_frame_sequence(dt)
        self.Nroi = len(sci_frames.rois_data)
        self.dark_frames = dark_frames
        # Full frame
        cal_mean_full,cal_mean_full_std = sci_frames.calib_master(dark_frames,full=True)
        cal_snr_full = np.divide(cal_mean_full,cal_mean_full_std)
        # Frame chopped in rois
        cal_mean,cal_mean_std = sci_frames.calib_master(dark_frames)
        cal_snr = np.divide(cal_mean,cal_mean_std)
        # Identifying the outputs
        outputs_pos = self.human_interf.identify_outputs(cal_snr_full,sci_frames.rois_crop,cal_snr,use_geom,snr_thresh)
        self.outputs_pos = outputs_pos
        # Linking ROIs to output channels
        channels_roi,channels_data = sci_frames.link_to_channels
        self.channels_roi = channels_roi
        self.channels_data = channels_data
        self.channels = list(channels_roi.keys())
        # Determining indices of photometric channels
        photo_idx = []
        for channel_label in self.channels:
            if list(channel_label)[0] == "P":
                photo_idx.append(self.channels_roi[channel_label].idx-1)    
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
            lambs = self.pix_to_lamb
            if len(lambs) != self.output_height:
                raise Exception("The length of the custom list of wavelengths" + str(len(lambs)) + " does not match the size of the outputs " + str(self.output_height))
        else:
            lambs = np.linspace(self.low_lamb,self.up_lamb,self.output_height)
    
        # Fetch science frames
        sci_frames = self.human_interf.science_frame_sequence(dt)
        # Calibration and masking outputs
        cal_mean,cal_mean_std,cal_seq,cal_seq_std = sci_frames.calib(self.dark_frames)
        
        cal_mean = cal_mean*self.outputs_pos
        cal_mean_snr = np.divide(cal_mean,cal_mean_std)
        cal_mean_std = cal_mean_std*self.outputs_pos
        
        cal_seq = cal_seq*self.outputs_pos[:, np.newaxis, :, :]
        cal_seq_snr = np.divide(cal_seq,cal_seq_std[:, np.newaxis, :, :])
        cal_seq_std = cal_seq_std*self.outputs_pos
        
        # Time series of broadband flux: sum output pixels' signal in each frame
        fluxes_broad = cal_seq.sum(axis=(2,3))
        snrs_broad = cal_seq_snr.sum(axis=(2,3)) 
        fluxes_broad_err = np.sqrt((cal_seq_std**2).sum(axis=(1,2)))
        # Dispersed flux: sum output pixels' signal row-per-row in master frame
        flux_disp = cal_mean.sum(axis=2)[self.output_top_idx:self.output_top_idx+self.output_height]
        snr_disp = cal_mean_snr.sum(axis=2)[self.output_top_idx:self.output_top_idx+self.output_height]
        flux_disp_err = np.sqrt((cal_mean_std**2).sum(axis=2)[self.output_top_idx:self.output_top_idx+self.output_height])
    
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
                self._diag_fig, self._diag_axs = plt.subplots(3, gridspec_kw={"height_ratios": [3.25, 3.25, 1.5], "hspace": 0.20}, figsize=(10,8))
                self._diag_fig_num = self._diag_fig.number
            
            fig, axs = self._diag_fig, self._diag_axs
            
            # Clear axes
            for ax in axs:
                ax.clear()

            integtime_ms = np.average(sci_frames.integtimes)*1000

            fig.suptitle("Diagnostics of chip outputs in time frame  ["+str(ids[0])+" , "+str(ids[-1])+"]  (ms) - Frame integration time : "+str(integtime_ms)+" (ms)")
            colors_markers = {"P1":['gray','o'],"P2":['brown','o'],"I1":['blue','x'],"I2":['red','^'],"I3":['black','^'],"I4":['green','x'],"P3":['purple','o'],"P4":['orange','o'],"B1":['pink','x'],"B2":['pink','x']} # photo P, interferometric I, background B
            
            if visual_feedback_flux:
                
                for channel in self.channels:
                    c = colors_markers[channel][0]
                    m = colors_markers[channel][1]
                    roi_idx = self.channels_roi[channel].idx
                    axs[0].errorbar(stamps,fluxes_broad[roi_idx-1],yerr=np.array([fluxes_broad_err[roi_idx-1]]*len(fluxes_broad[roi_idx-1])),color=c,marker=m,label="ROI"+str(roi_idx)+"/"+str(channel))
                    axs[1].errorbar(lambs+(roi_idx-1)*self.dlamb,flux_disp[roi_idx-1],yerr=flux_disp_err[roi_idx-1],color=c,marker=m,label="ROI"+str(roi_idx)+"/"+str(channel))
                    
                if "I2" in self.channels and "I3" in self.channels:
                    idx_I2 = self.channels_roi["I2"].idx
                    idx_I3 = self.channels_roi["I3"].idx
                    diff = flux_disp[idx_I3-1]-flux_disp[idx_I2-1]
                    diff_err = np.sqrt(flux_disp_err[idx_I3-1]**2+flux_disp_err[idx_I2-1]**2)
                    axs[2].errorbar(lambs,diff,yerr=diff_err,color="magenta",marker=colors_markers["B1"][1],label="I3-I2")
                    axs[2].set_ylim(np.min(diff),np.max(diff))
                    
                axs[0].set_xlabel("Time (ms)")
                Nticks = self.Nroi+1
                axs[1].set_xticks(lambs[0]+np.linspace(0,self.Nroi*self.dlamb,Nticks))
                axs[1].set_xticklabels([lambs[0]]*Nticks)
                for i in range(1,3):
                    axs[i].set_xlabel("Wavelength (um)")
                for i in range(0,3):
                    axs[i].set_ylabel("counts")
                
            else:
                
                for channel in self.channels:
                    c = colors_markers[channel][0]
                    m = colors_markers[channel][1]
                    roi_idx = self.channels_roi[channel].idx
                    axs[0].scatter(stamps,snrs_broad[roi_idx-1],color=c,marker=m,label="ROI"+str(roi_idx)+"/"+str(channel))
                    axs[1].scatter(lambs+(roi_idx-1)*self.dlamb,snr_disp[roi_idx-1],color=c,marker=m,label="ROI"+str(roi_idx)+"/"+str(channel))
                    
                if "I2" in self.channels and "I3" in self.channels:
                    idx_I2 = self.channels_roi["I2"].idx
                    idx_I3 = self.channels_roi["I3"].idx
                    diff = snr_disp[idx_I3-1]-snr_disp[idx_I2-1]
                    axs[2].scatter(lambs,diff,color="magenta",marker=colors_markers["B1"][1],label="I3-I2")
                    axs[2].set_ylim(np.min(diff),np.max(diff))
    
                axs[0].set_xlabel("Time (ms)")
                Nticks = self.Nroi+1
                axs[1].set_xticks(lambs[0]+np.linspace(0,self.Nroi*self.dlamb,Nticks))
                axs[1].set_xticklabels([lambs[0]]*Nticks)
                for i in range(1,3):
                    axs[i].set_xlabel("Wavelength (um)")
                for i in range(0,3):
                    axs[i].set_ylabel("Output SNR")
    
            # Legend
            for i in range(0,3):
                axs[i].legend(loc="upper right")
                
            # Showing
            plt.tight_layout()
            plt.subplots_adjust(right=0.85)     
            fig.canvas.draw()
            fig.canvas.flush_events()
    
        return stamps,fluxes_broad,fluxes_broad_err,snrs_broad,flux_disp,flux_disp_err,snr_disp
            