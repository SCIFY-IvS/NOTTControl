# -*- coding: utf-8 -*-
"""
Created on Wed Jan 14 11:45:30 2026

@author: Thomas

This class bundles functionalities for
- exchange and time synchronization of data with the infrared camera
- calculating diagnostics of the dispersed chip outputs in exchanged frames
- providing visual feedback on the calculated diagnostics

"""

import numpy as np
from nottcontrol.camera.infratec_interface import InfratecInterface

class Diagnostics():

    def __init__(self):    
        
        interf_ = InfratecInterface()
        framerate_ = interf_.getparam_single(240)
        self.interf = interf_
        self.framerate = framerate_

    # Upper-level: Data exchange and synchronization + calculating diagnostics for a demanded time series
    def diagnose(self,start,stop,visual_feedback):
    
    
    # Lower-level: Calculating diagnostics for a single camera frame
    def diagnose_frame(self,frame,,visual_feedback):
        '''
        Parameters
        ----------
        frame : Instance of the Frame class
            Infrared camera frame with 
        visual_feedback : boolean
            True is visual feedback is desired.

        Returns
        -------
        None.

        '''
        