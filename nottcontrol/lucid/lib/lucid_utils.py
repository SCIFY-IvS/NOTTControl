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
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
# Imports for visible camera (lucid) interfacing
from arena_api.system import system
from arena_api.buffer import BufferFactory
from arena_api.enums import PixelFormat
# xaosim-supported datatypes
try:
    from xaosim.shmlib import all_dtypes
except:
    all_dtypes = [np.uint8, np.int8, np.uint16, np.int16,
                  np.uint32, np.int32, np.uint64, np.int64,
                  np.float32, np.float64, np.complex64, np.complex128] 

# Imports for centroid fitting
from scipy.ndimage import gaussian_filter, sobel
from lmfit import Parameters, minimize
from astropy.modeling import models, fitting

#---------------#
# Configuration #
#---------------#

# Loading config
from nottcontrol import config as nott_config
nott_config = nott_config.config_parser._sections
# Dictionary for type conversions
convert_dict = dict(nott_config['convert_dict'])

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
im_ip = str(nott_config['connection']['im_ip'])
pup_ip = str(nott_config['connection']['pup_ip'])
# Camera parameters
stream_im = convert(dict(nott_config['stream_im']),convert_dict)
stream_pup = convert(dict(nott_config['stream_pup']),convert_dict)
readout_im = convert(dict(nott_config['readout_im']),convert_dict)
readout_pup = convert(dict(nott_config['readout_pup']),convert_dict)
stream_params = {"im_cam":stream_im, "pup_cam":stream_pup}
readout_params = {"im_cam":readout_im, "pup_cam":readout_pup}
# Fitting parameters
fit_im = convert(dict(nott_config['fit_im']),convert_dict)
fit_pup = convert(dict(nott_config['fit_pup']),convert_dict)
fit_params = {"im_cam":fit_im, "pup_cam":fit_pup}
# Beam centroid positions and radius in reference, injecting state
ref_im = convert(dict(nott_config['ref_im']),convert_dict)
ref_pup = convert(dict(nott_config['ref_pup']),convert_dict)
ref_state = {"im_cam":ref_im, "pup_cam":ref_pup}

class LucidUtils:
    '''
    Class that bundles functionalities related to the lucid visible cameras installed in the pupil and image plane.
    Functionalities include:
        > Creating and managing camera connections and streams via the lucid-provided "Arena API"
        > Changing the configuration (frame size, exposure time, ...) of connected cameras and their streams
        > Fetching camera frames by exchange of buffers
        > Fitting camera frames for beam centroid positions
        > Enabling threading with user-specified callback function
        
    Example use case:
        
    import lucid_utils
    with lucid_utils.LucidUtils() as utils:
        # Getting a single frame
        frame,width,height = utils.snap("im_cam")
        
    '''
 
    def __init__(self):
        
        self.devices = {}
        self.readout_configured = {"im_cam": False, "pup_cam": False}
        self.stream_configured = {"im_cam": False, "pup_cam": False}
        self.streaming = {"im_cam": False, "pup_cam": False}
        # Field used for threading a callback function
        self.streaming_callback = {"im_cam": False, "pup_cam": False}

        # Pixel formats are matched to the shmlib numpy data types, despite not all pixel formats being supported by the lucid camera (see arena_api enums).
        #               follow the Pixel Format Naming Convention (pfnc)
        self.pxformats = ['Mono8',   'Mono8s',  'Mono16',     'Mono16s',
                          'Mono32',  'Mono32s', 'Mono64',     'Mono64s',
                          'Mono32f', 'Mono64f', 'Complex64f', 'Complex128f']
        self.dtypes = all_dtypes
        
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
            
            # Two cameras have been detected on network:
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

                    # Check that both cameras are correctly loaded
                    if "im_cam" not in self.devices or "pup_cam" not in self.devices:
                        raise Exception("Two cameras detected but could not match their IP addresses to the ones in the configuration file.")
                            
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
            try:
                system.destroy_device(device)
            except Exception as e:
                print(f"Failed to destroy device: {e}")
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
        if not self.devices[name].is_connected():
            raise Exception(f"Camera device with name {name} is not connected.")
        
        device = self.devices[name]
        nodemap = device.nodemap

        # Flag that readout is under configuration
        self.readout_configured[name] = False

        fail = False
        for param, value in params.items():
            
            if not isinstance(param,str):
                param = str(param)
                
            try:
                # a) Verify the node is writable
                if not nodemap[param].is_writable:
                    raise RuntimeError(f"Parameter {param} is not writable at the moment. Often nodes are locked whilst streaming.")
                # b) In the specific case of PixelFormat, check whether the camera supports the input format first.
                # Based on "Acquisition: Compressed Image Handling" arena api example code
                if param == 'PixelFormat':
                    entries = nodemap[param].enumentry_names
                    found = False
                    for e in entries:
                        if (e == value):
                            found = True
                            break
                    if not found:
                        raise Exception("Input PixelFormat not supported by camera.")
                # c) In the case of any other param
                nodemap[param].value = value

            except Exception as e:
                fail = True
                print(f"Failed to configure readout parameter {param} on camera {name}: {e}")
                
        if not fail:
            self.readout_configured[name] = True
            print(f"Camera {name} readout parameters configured.")
    
    def configure_camera_stream(self,name,**params):
        """Set the streaming configuration parameters for camera "name"."""
        
        if not isinstance(name,str):
            name = str(name)
        if name not in self.devices.keys():
            raise Exception(f"A camera device with name {name} does not exist.")
        if not self.devices[name].is_connected():
            raise Exception(f"Camera device with name {name} is not connected.")
       
        device = self.devices[name]
        stream_nodemap = device.tl_stream_nodemap

        # Flag that stream is under configuration
        self.stream_configured[name] = False

        fail = False
        for param, value in params.items():
            
            if not isinstance(param,str):
                param = str(param)

            try:
                # a) Verify the node is writable
                if not stream_nodemap[param].is_writable:
                    raise RuntimeError(f"Parameter {param} is not writable at the moment. Often nodes are locked whilst streaming.")
                # b) In the specific case of PixelFormat, check whether the camera supports the input format first.
                # Based on "Acquisition: Compressed Image Handling" arena api example code
                if param == 'PixelFormat':
                    entries = stream_nodemap[param].enumentry_names
                    found = False
                    for e in entries:
                        if (e == value):
                            found = True
                            break
                    if not found:
                        raise Exception("Input PixelFormat not supported by camera.")
                # c) In the case of any other param
                stream_nodemap[param].value = value
                
            except Exception as e:
                fail = True
                print(f"Failed to configure stream parameter {param} on camera {name}: {e}")

        if not fail:
            self.stream_configured[name] = True
            print(f"Camera {name} streaming parameters configured.")
        
    def get_camera_info(self,name,param):
        """Return the value corresponding to the given "param" for camera "name", in either stream or readout nodemaps."""
        
        if not isinstance(name,str):
            name = str(name)
        if not isinstance(param,str):
            param = str(param)        
        if not self.devices[name].is_connected():
            raise Exception(f"Camera device with name {name} is not connected.")

        device = self.devices[name]
        nodemap = device.nodemap
        stream_nodemap = device.tl_stream_nodemap
        try:
            val = nodemap[param].value
        except KeyError:
            try:
                val = stream_nodemap[param].value
            except KeyError:
                raise KeyError(f"Parameter {param} is part of neither the camera, nor the stream nodemap.")
            
        print(f'Camera {name} has parameter {param} set to {val}.')
        return val
    
    #-----------------------------------------#
    # Streaming control and frame acquisition #
    #-----------------------------------------#
    
    def start_streaming(self,name):
        """Start streaming on camera "name"."""
        
        if not isinstance(name,str):
            name = str(name)
        if not self.devices[name].is_connected():
            raise Exception(f"Camera device with name {name} is not connected.")
        # Never start streaming on an unconfigured or unsuccessfully re-configured camera
        if not self.readout_configured[name] or not self.stream_configured[name]:
            raise Exception(f"Please guarantee that camera {name} is correctly configured before streaming. Refer to .configure_camera_readout and .configure_camera_stream.")
        
        if self.streaming[name]:
            print(f"Camera {name} is already streaming.")
        else:
            device = self.devices[name]
            device.start_stream()
            self.streaming[name] = True
            print(f"Camera {name} started streaming.")
        
    def stop_streaming(self,name):
        """Stop streaming on camera "name"."""
        
        if not isinstance(name,str):
            name = str(name)        
        if not self.devices[name].is_connected():
            raise Exception(f"Camera device with name {name} is not connected.")
        if self.streaming[name]:
            device = self.devices[name]
            device.stop_stream()
            self.streaming[name] = False
            print(f"Camera {name} stopped streaming.")
        else:
            print(f"Camera {name} is not streaming.")
        
    def _get_frame(self,device,nodemap,pxformat=None,dtype=None,verbose=False): 
        """Retrieve a frame (and its width & height) by retrieving a buffer from "device" with corresponding readout nodemap "nodemap".
           Method assumes device is streaming prior to call and will not handle closing the stream after call.
           self.pxformats stores a list of pixel format names, not all of which are supported by the camera.
           self.dtypes stores a list of corresponding numpy data types
           If no pixel format (pxformat) is specified, the buffer is copied with its native format.
           If a pixel format (pxformat) is specified, the buffer is converted to that format.
           If the used pixel format is not in self.pxformats, the user should specify the corresponding numpy data type via parameter dtype.

           Params:
            - pxformat: Instance of the ! PixelFormat class (e.g., PixelFormat.BGRa10)
            - dtype: Instance of the numpy class, numpy datatype

        """

        # Verifying device connection
        if not device.is_connected():
            raise Exception(f"Camera device is not connected.")

        # Fetching buffer
        buffer = device.get_buffer()
        # Copying buffer
        if pxformat is None:
            # Keep native (i.e., set up in camera configuration) pixel format
            buffer_copy = BufferFactory.copy(buffer)
        else:
            # Convert to user-specified format
            buffer_copy = BufferFactory.convert(buffer, pxformat)
        # Requeueing the buffer as it is no longer needed
        device.requeue_buffer(buffer)

        # Analysing buffer copy
        # ---------------------
        if verbose:
            print("Buffer id: ", buffer_copy.frame_id)
            print("Buffer timestamp (ns): ", buffer_copy.timestamp_ns)
            print("Buffer pixel format: ", buffer_copy.pixel_format.name)
            print("")
            print("Buffer payload type: ", buffer_copy.payload_type) # To check whether the buffer holds Chunk data and the w,h retrieval should be adapted to that. To be removed
            print("Buffer has image data? ", buffer_copy.has_imagedata)
            print("Buffer has chunk data? ", buffer_copy.has_chunkdata)
            print("")
            print("Buffer size: ", buffer_copy.buffer_size)
            print("Size of filled buffer: ", buffer_copy.size_filled)
            print("Payload size: ", buffer_copy.payload_size)
            print("Is buffer incomplete? ", buffer_copy.is_incomplete)
            print("Is data larger than buffer? ", buffer_copy.is_data_larger_than_buffer)
            print("")
            print("Buffer width, height (px): ", buffer_copy.width, buffer_copy.height)
            print("Buffer x,y offsets (px): ", buffer_copy.offset_x, buffer_copy.offset_y)
 
        # Width and height
        w = buffer_copy.width
        h = buffer_copy.height
        # Pixel format name
        pxformat_str = nodemap['PixelFormat'].value
        # Numpy data type
        if pxformat_str not in self.pxformats:
            if dtype is None:
                raise Exception("Pixel format not supported for automatic conversion to numpy data type (see self.pxformats in lucid_utils). Please input a numpy datatype manually via the 'dtype' parameter of this method.")
            else:
                dtype = dtype
        else:
            dtype = self.dtypes[np.argwhere(self.pxformats == pxformat_str)] 
        # Data
        frame = np.array(buffer.data, dtype=dtype)
        frame = frame.reshape(h,w)

        # Destroy the buffer copy
        BufferFactory.destroy(buffer_copy)
        
        return frame,w,h

    def snap(self, name, verbose=False):
        """Take a snapshot of camera {name}'s view, i.e. one single frame of data. This function handles the opening and closing of the stream."""

        if not isinstance(name,str):
            name = str(name)
        device = self.devices[name]
        nodemap = device.nodemap
        # Open stream
        self.start_streaming(name)
        try:
            frame, w, h = self._get_frame(device,nodemap,verbose)
        finally:
            self.stop_streaming(name)
            print(f"Camera {name} returned a snapshot, stream closed.")
        return frame, w, h

    def start_thread(self, name, callback):
        """Create and return a thread that fetches snapshots of camera {name} in real-time and passes each one to the callback function.
        Use stop_streaming_callback to stop the thread from outside.
        Wait for thread to finish by calling thread.join() before running other code."""
        
        # Flag that a callback stream is starting
        self.start_streaming_callback(name)
        # Creating a stop event
        stop_event = threading.Event()

        def _loop():
            if not isinstance(name,str):
                name = str(name)
            device = self.devices[name]
            nodemap = device.nodemap
            # Open stream
            self.start_streaming(name)
            try:
                while not stop_event.is_set():
                    if self.streaming_callback[name]:
                        frame, w, h = self._get_frame(device,nodemap)
                        # Pass frame to callback function
                        callback(frame, w, h)
                    else:
                        # Break out of thread
                        stop_event.set()
                    time.sleep(0.01)
            finally:
                self.stop_streaming(name)

        thread = threading.Thread(target=_loop)
        thread.start()
        return thread

    def start_streaming_callback(self, name):
        self.streaming_callback[name] = True

    def stop_streaming_callback(self, name):
        self.streaming_callback[name] = False

    def fit(self,name,beam_nr,visual_feedback):
        """Fit for the centroid position and radius of a single beam that is visible on camera "name". This function handles the opening and closing of the stream.
        beam_nr is either 1,2,3 or 4. Beams are numbered counting towards the bench edge; beam 1 is the innermost one, beam 4 the outermost one.
        If "visual_feedback" is True, the frame and identified centroid / beam size are plotted.
        """
        
        if not isinstance(name,str):
            name = str(name)
        self.start_streaming(name)
        try:
            if name == "im_cam":
                return self.get_fit_im(beam_nr,visual_feedback,**fit_params[name])
            elif name == "pup_cam":
                return self.get_fit_pup(beam_nr,visual_feedback,**fit_params[name])
            else:
                raise Exception(f"Camera with name {name} not recognized. Please specify either 'im_cam' or 'pup_cam' as name.")
        finally:
            self.stop_streaming(name)
       
    # Binning function
    def _bin_frame(self, data, binning_x, binning_y):
        h, w = data.shape
        bins_x = h // binning_x
        bins_y = w // binning_y
        resid_x = h % binning_x
        resid_y = w % binning_y
        # Cropping data dimensions to be multiples of the binning factor
        data = data[:h-resid_x,:w-resid_y]
        # Binning
        a = data.reshape(bins_x, binning_x, bins_y, binning_y).mean(axis=(1,3))
        return a
        
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
    
        #--------------#
        # Taking frame #
        #--------------#
        device = self.devices["im_cam"]
        nodemap = device.nodemap
        myframe,w,h = self._get_frame(device, nodemap)
        myframe_bin = self._bin_frame(myframe,mybinx,mybiny)
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
        x, y = np.meshgrid(np.arange(w//mybinx), np.arange(h//mybiny), )
        mask_circle = np.hypot(x-centroid_x,y-centroid_y) < radius
        flux = np.sum(myframe_bin[mask_circle])
        print("Flux guess: ", flux*mybinx*mybiny)
        # Detector noise estimate (TBD)
        amin, amax = np.percentile(myframe, 99.5), np.percentile(myframe, 99.9)
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
                            color='red', fill=False, linewidth=2,label="Reference")
            
            ax.add_patch(fit_beam)
            ax.add_patch(ref_beam)
            
            ax.scatter(centroid_x_fit,centroid_y_fit,color="blue",s=8)
            ax.scatter(ref[0],ref[1],color="red",s=8)
            
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
        
        #---------------------------------------#
        # Taking frame, smoothening and binning #
        #---------------------------------------#
        device = self.devices["pup_cam"]
        nodemap = device.nodemap
        myframe,w,h = self._get_frame(device, nodemap)
        myframe_smooth = gaussian_filter(myframe,sigma)
        myframe_smooth_bin = self._bin_frame(myframe_smooth,mybinx,mybiny)
        myframe_bin = self._bin_frame(myframe,mybinx,mybiny)
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
        x, y = np.meshgrid(np.arange(w//mybinx), np.arange(h//mybiny), )
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
                            color='red', fill=False, linewidth=2,label="Reference")
            
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
        
        
        
        
    
    
    
    
    
    
    
    
    
    
    
    
    
