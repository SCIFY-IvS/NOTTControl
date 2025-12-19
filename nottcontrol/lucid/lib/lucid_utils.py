# -*- coding: utf-8 -*-
"""
Created on Wed Dec 17 13:36:18 2025

@author: Thomas
"""

#---------#
# Imports #
#---------#

# General
import time
import ast
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
# Imports for visible camera (lucid) interfacing
from arena_api.system import system
# Imports for centroid fitting
from scipy.ndimage import gaussian_filter, sobel
from lmfit import Parameters, minimize
from astropy.modeling import models, fitting

#---------------#
# Configuration #
#---------------#

# Loading config
from nottcontrol.lucid import config_lucid
# Dictionary for type conversions
convert_dict = dict(config_lucid['convert_dict'])

def convert(dic,conversion_dic):
    """
    The .cfg file format does not allow for specification of parameter type.
    This function converts the parameter values (retrieved from the .cfg file as strings) to the type that is specified in the input conversion_dic.
    """
    # Converting to correct types
    for key in dic.keys():
        if conversion_dic[key] == "Bool":
            dic[key] = bool(dic[key])
        if conversion_dic[key] == "Int":
            dic[key] = int(dic[key])
        if conversion_dic[key] == "Float":
            dic[key] = float(dic[key])
        if conversion_dic[key] == "String":
            dic[key] = str(dic[key])
        if conversion_dic[key] == "IntTuple":
            dic[key] = ast.literal_eval(dic[key])
    return dic

# Connectivity parameters
im_ip = str(config_lucid['connection']['im_ip'])
pup_ip = str(config_lucid['connection']['pup_ip'])
# Camera parameters
stream_im = convert(dict(config_lucid['stream_im']),convert_dict)
stream_pup = convert(dict(config_lucid['stream_pup']),convert_dict)
readout_im = convert(dict(config_lucid['readout_im']),convert_dict)
readout_pup = convert(dict(config_lucid['readout_pup']),convert_dict)
stream_params = {"im_cam":stream_im, "pup_cam":stream_pup}
readout_params = {"im_cam":readout_im, "pup_cam":readout_pup}
# Fitting parameters
fit_im = convert(dict(config_lucid['fit_im']),convert_dict)
fit_pup = convert(dict(config_lucid['fit_pup']),convert_dict)
fit_params = {"im_cam":fit_im, "pup_cam":fit_pup}
# Beam centroid positions and radius in reference, injecting state
ref_im = convert(dict(config_lucid['ref_im']),convert_dict)
ref_pup = convert(dict(config_lucid['ref_pup']),convert_dict)
ref_state = {"im_cam":ref_im, "pup_cam":ref_pup}

class Utils:
    '''
    Class that bundles functionalities related to the lucid visible cameras installed in the pupil and image plane.
    Functionalities include:
        > Creating and managing camera connections via the lucid-provided "Arena API"
        > Changing the configuration (frame size, exposure time, ...) of connected cameras
        > Streaming frames from the cameras by exchange of buffers
        > Fitting camera frames for beam centroid positions
        > Providing visual feedback
        
    Example use case:
        
    import lucid_utils
    with lucid_utils.Utils() as utils:
        
        utils.start_streaming("im_cam")
        frame,width,height = utils.get_frame("im_cam")
        utils.stop_streaming("im_cam")
        
    '''
 
    def __init__(self):
        
        self.devices = {}
        self.streaming = {"im_cam": False, "pup_cam": False}
        
    def __enter__(self):
        """Connect to both cameras and create associated devices for interfacing. Install default streaming configuration parameters."""
        
        # Connecting to cameras and creating devices
        tries = 0
        tries_max = 6
        sleep_time_secs = 10
        while tries < tries_max: # Wait no longer than 60 seconds for the devices to be connected via Ethernet
            # Seek for visible cameras on the network
            cam_device_infos = []
            for device_info in system.device_infos:
                if device_info["model"] == "PHX064S-M":
                    cam_device_infos.append(device_info)
            
            # Both cameras have been detected on network:
            if len(cam_device_infos) == 2:
                # Create devices
                try:
                    for cam_device_info in cam_device_infos:
                        if cam_device_info["ip"] == im_ip:
                            im_cam_device = system.create_device(cam_device_info)[0]
                            self.devices["im_cam"] = im_cam_device
                            print("Device used for image plane:",im_cam_device)
                        elif cam_device_info["ip"] == pup_ip:
                            pup_cam_device = system.create_device(cam_device_info)[0]
                            self.devices["pup_cam"] = pup_cam_device
                            print("Device used for pupil plane:",pup_cam_device)
                            
                    # Installing default readout and streaming configuration
                    for name in self.devices.keys():
                        self.configure_camera_readout(name,**readout_params[name])
                        self.configure_camera_stream(name,**stream_params[name])
                
                    # Return self to user to allow for utils access.
                    return self
                            
                except Exception as e:
                    self._clean()
                    raise e
                
            else:
                print(f'Try {tries+1} of {tries_max}: waiting for {sleep_time_secs} seconds for both visible cameras to be connected via Ethernet.')
                for sec_count in range(sleep_time_secs):
                    time.sleep(1)
                    print(f'{sec_count+1 } seconds passed ', '.' * sec_count, end='\r')
                tries += 1
                
        raise Exception('Could not find both visible cameras on the network. Please check their Ethernet connection and try again.')
        
    def __exit__(self,exc_type,exc_value,traceback):
        """Stop any ongoing buffer streaming, close all devices."""
        for name in self.devices.keys():
            self.stop_streaming(name)
        self._clean()
        # Returning False as to not suppress any error messages.
        return False
        
    def _clean(self):
        """Destroy all opened devices."""
        for device in self.devices.values():
            system.destroy_device(device)
        print("All devices closed.")
        self.devices = {}
    
    #------------------------------#
    # Camera configuration control #
    #------------------------------#
    
    def configure_camera_readout(self,name,**params):
        """Set the readout configuration parameters for camera "name."""
    
        if not isinstance(name,str):
            name = str(name)
    
        if name not in self.devices.keys():
            raise Exception(f"A camera device with name {name} does not exist.")
            
        device = self.devices[name]
        nodemap = device.nodemap
        
        for param, value in params.items():
            
            if not isinstance(param,str):
                param = str(param)
            
            if param in nodemap.feature_names:
                nodemap[param].value = value
            else:
                print(f"Parameter {param} not found in the nodemap of camera {name}.")
                
        print(f"Camera {name} readout parameters configured.")
    
    def configure_camera_stream(self,name,**params):
        """Set the streaming configuration parameters for camera "name"."""
        
        if not isinstance(name,str):
            name = str(name)
        
        if name not in self.devices.keys():
            raise Exception(f"A camera device with name {name} does not exist.")
            
        device = self.devices[name]
        stream_nodemap = device.tl_stream_nodemap
        
        for param, value in params.items():
            
            if not isinstance(param,str):
                param = str(param)
            
            if param in stream_nodemap.feature_names:
                stream_nodemap[param].value = value
            else:
                print(f"Parameter {param} not found in the stream nodemap of camera {name}.")
                
        print(f"Camera {name} streaming parameters configured.")
        
    def get_camera_info(self,name,param):
        """Return the value corresponding to the given "param" for camera "name", in either stream or readout nodemaps."""
        
        if not isinstance(name,str):
            name = str(name)
        if not isinstance(param,str):
            param = str(param)
        
        device = self.devices[name]
        nodemap = device.nodemap
        stream_nodemap = device.tl_stream_nodemap
        try:
            val = nodemap[param].value
        except:
            val = stream_nodemap[param].value
            
        print(f'Camera {name} has parameter {param} set to {val}.')
        
    
    #-----------------------------------------#
    # Streaming control and frame acquisition #
    #-----------------------------------------#
    
    def start_streaming(self,name):
        """Start streaming on camera "name"."""
        
        if not isinstance(name,str):
            name = str(name)
        
        if self.streaming[name]:
            print(f"Camera {name} is already streaming.")
        else:
            device = self.devices[name]
            device.start_stream()
            print(f"Camera {name} started streaming.")
            
        self.streaming[name] = True
        
    def stop_streaming(self,name):
        """Stop streaming on camera "name"."""
        
        if not isinstance(name,str):
            name = str(name)
        
        if self.streaming[name]:
            device = self.devices[name]
            device.stop_stream()
            print(f"Camera {name} stopped streaming.")
        else:
            print(f"Camera {name} is not streaming.")
    
        self.streaming[name] = False
        
    def get_frame(self,name): # To be checked : Is "with device.start_stream()" superior?
        """Retrieve a frame (and its width & height) from camera "name"."""
        
        if not isinstance(name,str):
            name = str(name)
        
        device = self.devices[name]
        nodemap = device.nodemap
        
        if not self.streaming[name]:
            raise Exception(f'Camera {name} is not streaming, cannot read frames.')
        
        buffer = device.get_buffer()
        frame = np.array(buffer.data, dtype=np.uint8)
        frame = frame.reshape(buffer.height, buffer.width)
        # Width and height
        w = nodemap["Width"].value
        h = nodemap["Height"].value
        # Requeue to release buffer memory
        device.requeue_buffer(buffer)
        
        return frame,w,h
    
    def get_fit(self,name,beam_nr,visual_feedback):
        """Fit for the centroid position and radius of a single beam that is visible on camera "name".
        beam_nr is either 1,2,3 or 4. Beams are numbered counting towards the bench edge; beam 1 is the innermost one, beam 4 the outermost one.
        If "visual_feedback" is True, the frame and identified centroid / beam size are plotted.
        """
        
        if not isinstance(name,str):
            name = str(name)
        
        if name == "im_cam":
            return self.get_fit_im(beam_nr,visual_feedback,**fit_params[name])
        if name == "pup_cam":
            return self.get_fit_pup(beam_nr,visual_feedback,**fit_params[name])
        else:
            raise Exception(f"Camera with name {name} not recognized. Please specify either 'im_cam' or 'pup_cam' as name.")
       
    def get_fit_im(self,beam_nr,visual_feedback,**params):
        """
        Fit for the centroid position and radius of a single beam that is visible on the image camera.
        beam_nr is either 1,2,3 or 4. Beams are numbered counting towards the bench edge; beam 1 is the innermost one, beam 4 the outermost one.
        If "visual_feedback" is True, the frame and identified centroid / beam size are plotted.
        """
        # Unpack parameters
        mybinx,mybiny,perc_grad_low,perc_grad_high,perc_int = params["mybinx"],params["mybiny"],params["perc_grad_low"],params["perc_grad_high"],params["perc_int"]
        # Name of considered beam
        beam_name = "beam"+str(beam_nr)
        # Reference state of considered beam
        ref = ref_state["im_cam"][beam_name]
        # Binning function
        def bin_frame(data, binning_x, binning_y):
            h, w = data.shape
            bins_x = h // binning_x
            bins_y = w // binning_y
            a = data.reshape(bins_x, binning_x, bins_y, binning_y).mean(axis=(1,3))
            return a
    
        #--------------#
        # Taking frame #
        #--------------#
        myframe,w,h = self.get_frame("im_cam")
        myframe_bin = bin_frame(myframe,mybinx,mybiny)
        #------------------------------------------------------------#
        # Detecting the beam edge by gradient and intensity criteria #
        #------------------------------------------------------------#
        # Calculating gradients (Sobel operator)
        grad_x = sobel(myframe_bin,axis=1)
        grad_y = sobel(myframe_bin,axis=0)
        grad_mag = np.sqrt(grad_x**2 + grad_y**2)
        # Determining the pixels with the highest gradient
        thresh_grad_low = np.percentile(grad_mag,perc_grad_low)
        thresh_grad_high = np.percentile(grad_mag,perc_grad_high)
        mask_grad_low = grad_mag >= thresh_grad_low
        mask_grad_high = grad_mag <= thresh_grad_high
        mask_grad = mask_grad_low & mask_grad_high
        # Determining the pixels with the highest intensity
        thresh_int = np.percentile(myframe_bin,perc_int)
        mask_int = myframe_bin >= thresh_int
        # Determining the pixels that belong to the beam edge by convolving above two criteria
        mask_edge = mask_grad & mask_int
        #-----------------#
        # Initial guesses #
        #-----------------#
        # Guess for centroid position
        rows, cols = np.where(mask_edge)
        centroid_x = np.mean(cols)
        centroid_y = np.mean(rows)
        print("Centroid guess xy: ", centroid_x*mybinx, centroid_y*mybiny)
        # Guess for beam radius
        radius = np.hypot(np.std(rows),np.std(cols))
        print("Radius guess: ", radius*mybinx)
        # Guess for total flux in binned beam
        x, y = np.meshgrid(np.arange(w/mybinx), np.arange(h/mybiny), )
        mask_circle = np.hypot(x-centroid_x,y-centroid_y) < radius
        flux = np.sum(myframe_bin[mask_circle])
        print("Flux guess: ", flux*mybinx*mybiny)
        # Detector noise estimate (TBD)
        amin, amax = np.percentile(myframe, 95.), np.percentile(myframe, 99.)
        amask =  (myframe <= amax) * (myframe >= amin)
        noise = np.std(myframe[amask])
        print("Noise estimation: ", noise)
        #---------#
        # Fitting #
        #---------#
        param = Parameters()
        param.add("x_loc", centroid_x, min=0, max=w)
        param.add("y_loc", centroid_y, min=0, max=h)
        param.add("radius", radius, min=0.01*radius, max=5*radius, vary=True)
        param.add("flux", flux, min = 0.01*flux, max = 5*flux, vary=True)
    
        refearray = np.zeros_like(myframe_bin)

        def disc(aparam):
            model = np.zeros(refearray.shape)
            xx, yy = np.meshgrid(np.arange(model.shape[1]), np.arange(model.shape[0]), )
            rad = np.hypot(xx-aparam["x_loc"], yy-aparam["y_loc"])
            mod = np.exp(-(rad**2/aparam["radius"]**2)**8)
            mod = aparam["flux"] / mod.sum() * mod
            return mod
            
        def residual(aparam, data, error):
            model = disc(aparam)
            myresid = (data - model)**2/error**2
            return myresid.flatten()
        
        res = minimize(residual, param, args=[myframe_bin, noise])
        
        #-------------#
        # Fit results #
        #-------------#
        # Fitted centroid & radius
        centroid_x_fit = res.params["x_loc"]*mybinx
        centroid_y_fit = res.params["y_loc"]*mybiny
        # Only considering circular beams
        radius_fit = res.params["radius"]*mybinx
        
        #-----------------#
        # Visual feedback #
        #-----------------#
        if visual_feedback:
            
            fig = plt.figure(figsize=(15,10))
            ax = fig.add_subplot(111)
            img = ax.imshow(myframe)
            
            fit_beam = Circle((centroid_x_fit, centroid_y_fit), radius_fit, 
                            color='blue', fill=False, linewidth=2,ls=":",label="Current")
            ref_beam = Circle((ref[0], ref[1]), ref[2], 
                            color='red', fill=False, linewidth=5,label="Reference")
            
            ax.add_patch(fit_beam)
            ax.add_patch(ref_beam)
            
            ax.scatter(centroid_x_fit,centroid_y_fit,color="blue")
            ax.scatter(ref[0],ref[1],color="red")
            
            # Set tick labels
            Nticks = 10
            xticks = np.linspace(0,w-1,Nticks)
            yticks = np.linspace(0,h-1,Nticks)
            labelsx = np.round(np.linspace(0,w-1,Nticks)*2.4,0)
            labelsy = np.round(np.linspace(0,h-1,Nticks)*2.4,0)
            ax.axes.get_xaxis().set_ticks(xticks)
            ax.axes.get_yaxis().set_ticks(yticks)
            ax.set_xticklabels(labelsx)
            ax.set_yticklabels(labelsy)
            
            # Add axis labels
            ax.set_xlabel('Relative Position (um)', fontsize=14)
            ax.set_ylabel('Relative Position (um)', fontsize=14)
            
            clb = plt.colorbar(img)
            clb.ax.set_title('Counts',fontsize=12)
            ax.legend()
            ax.grid(color="white",linestyle="--",linewidth=0.5)
            
            fig.suptitle("Image camera view", fontsize=24)
            fig.canvas.draw()
            fig.canvas.flush_events()
            fig.show()
            
        return centroid_x_fit,centroid_y_fit,radius_fit
    
    def get_fit_pup(self,beam_nr,visual_feedback,**params):
        """
        Fit for the centroid position and radius of a single beam that is visible on the pupil camera.
        beam_nr is either 1,2,3 or 4. Beams are numbered counting towards the bench edge; beam 1 is the innermost one, beam 4 the outermost one.
        If "visual_feedback" is True, the frame and identified centroid / beam size are plotted.
        """
        # Unpack parameters
        sigma,mybinx,mybiny,perc_grad_low,perc_grad_high,perc_int = params["sigma"],params["mybinx"],params["mybiny"],params["perc_grad_low"],params["perc_grad_high"],params["perc_int"]
        # Name of considered beam
        beam_name = "beam"+str(beam_nr)
        # Reference state of considered beam
        ref = ref_state["pup_cam"][beam_name]
        # Binning function
        def bin_frame(data, binning_x, binning_y):
            h, w = data.shape
            bins_x = h // binning_x
            bins_y = w // binning_y
            a = data.reshape(bins_x, binning_x, bins_y, binning_y).mean(axis=(1,3))
            return a
        
        #---------------------------------------#
        # Taking frame, smoothening and binning #
        #---------------------------------------#
        myframe,w,h = self.get_frame("pup_cam")
        myframe_smooth = gaussian_filter(myframe,sigma)
        myframe_smooth_bin = bin_frame(myframe_smooth,mybinx,mybiny)
        myframe_bin = bin_frame(myframe,mybinx,mybiny)
        #------------------------------------------------------------#
        # Detecting the beam edge by gradient and intensity criteria #
        #------------------------------------------------------------#
        # Calculating gradients (Sobel operator)
        grad_x = sobel(myframe_smooth_bin,axis=1)
        grad_y = sobel(myframe_smooth_bin,axis=0)
        grad_mag = np.sqrt(grad_x**2 + grad_y**2)
        # Determining the pixels with the highest gradient
        thresh_grad_low = np.percentile(grad_mag,perc_grad_low)
        thresh_grad_high = np.percentile(grad_mag,perc_grad_high)
        mask_grad_low = grad_mag >= thresh_grad_low
        mask_grad_high = grad_mag <= thresh_grad_high
        mask_grad = mask_grad_low & mask_grad_high
        # Determining the pixels with the highest intensity
        thresh_int = np.percentile(myframe_smooth_bin,perc_int)
        mask_int = myframe_smooth_bin >= thresh_int
        # Determining the pixels that belong to the beam edge by convolving above two criteria
        mask_edge = mask_grad & mask_int
        #-----------------#
        # Initial guesses #
        #-----------------#
        # Guess for centroid position
        rows, cols = np.where(mask_edge)
        centroid_x = np.mean(cols)
        centroid_y = np.mean(rows)
        print("Centroid guess xy: ", centroid_x*mybinx, centroid_y*mybiny)
        # Guess for beam radius
        radius = np.hypot(np.std(rows),np.std(cols))
        print("Radius guess: ", radius*mybinx)
        # Guess for total flux in binned beam
        x, y = np.meshgrid(np.arange(w/mybinx), np.arange(h/mybiny), )
        mask_circle = np.hypot(x-centroid_x,y-centroid_y) < radius
        flux = np.sum(myframe_bin[mask_circle])
        print("Flux guess: ", flux*mybinx*mybiny)
        # Detector noise estimate (TBD)
        amin, amax = np.percentile(myframe, 55.), np.percentile(myframe, 65.)
        amask =  (myframe <= amax) * (myframe >= amin)
        noise = np.std(myframe[amask])
        print("Noise estimation: ", noise)
        #---------#
        # Fitting #
        #---------#
        param = Parameters()
        param.add("x_loc", centroid_x, min=0, max=w)
        param.add("y_loc", centroid_y, min=0, max=h)
        param.add("radius", radius, min=0.5*radius, max=1.5*radius, vary=True)
        param.add("flux", flux, min = 0.5*flux, max = 1.5*flux, vary=True)
    
        refearray = np.zeros_like(myframe_bin)

        def disc(aparam):
            model = np.zeros(refearray.shape)
            xx, yy = np.meshgrid(np.arange(model.shape[1]), np.arange(model.shape[0]), )
            rad = np.hypot(xx-aparam["x_loc"], yy-aparam["y_loc"])
            mod = np.exp(-(rad**2/aparam["radius"]**2)**8)
            mod = aparam["flux"] / mod.sum() * mod
            return mod
            
        def residual(aparam, data, error):
            model = disc(aparam)
            myresid = (data - model)**2/error**2
            return myresid.flatten()
        
        res = minimize(residual, param, args=[myframe_bin, noise])
        
        #-------------#
        # Fit results #
        #-------------#
        # Fitted centroid & radius
        centroid_x_fit = res.params["x_loc"]*mybinx
        centroid_y_fit = res.params["y_loc"]*mybiny
        # Only considering circular beams
        radius_fit = res.params["radius"]*mybinx
        
        #-----------------#
        # Visual feedback #
        #-----------------#
        if visual_feedback:
            
            fig = plt.figure(figsize=(15,10))
            ax = fig.add_subplot(111)
            img = ax.imshow(myframe)
            
            fit_beam = Circle((centroid_x_fit, centroid_y_fit), radius_fit, 
                            color='blue', fill=False, linewidth=2,ls=":",label="Current")
            ref_beam = Circle((ref[0], ref[1]), ref[2], 
                            color='red', fill=False, linewidth=5,label="Reference")
            
            ax.add_patch(fit_beam)
            ax.add_patch(ref_beam)
            
            ax.scatter(centroid_x_fit,centroid_y_fit,color="blue")
            ax.scatter(ref[0],ref[1],color="red")
            
            # Set tick labels
            Nticks = 10
            xticks = np.linspace(0,w-1,Nticks)
            yticks = np.linspace(0,h-1,Nticks)
            labelsx = np.round(np.linspace(0,w-1,Nticks)*2.4,0)
            labelsy = np.round(np.linspace(0,h-1,Nticks)*2.4,0)
            ax.axes.get_xaxis().set_ticks(xticks)
            ax.axes.get_yaxis().set_ticks(yticks)
            ax.set_xticklabels(labelsx)
            ax.set_yticklabels(labelsy)
            
            # Add axis labels
            ax.set_xlabel('Relative Position (um)', fontsize=14)
            ax.set_ylabel('Relative Position (um)', fontsize=14)
            
            clb = plt.colorbar(img)
            clb.ax.set_title('Counts',fontsize=12)
            ax.legend()
            ax.grid(color="white",linestyle="--",linewidth=0.5)
            
            fig.suptitle("Pupil camera view", fontsize=24)
            fig.canvas.draw()
            fig.canvas.flush_events()
            fig.show()
            
        return centroid_x_fit,centroid_y_fit,radius_fit
        
        
        
        
    
    
    
    
    
    
    
    
    
    
    
    
    