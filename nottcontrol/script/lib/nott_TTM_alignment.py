# -*- coding: utf-8 -*-
"""
Created on Thu Dec 12 11:51:16 2024

Collection of functions created to facilitate NOTT alignment through mirror tip/tilt motion.

@author: Thomas Mattheussen
"""

#-------#
# TO DO #
#-------#

# ! A) Complete act_pos_align, the actuator positions in a state of alignment, for each configuration.
# --> First positions after manual optimization of injection
# --> Second positions after localization/optimization algorithms

# ! B) Add tool to align the beams on the visible cameras
# --> Implement optimization algorithm

# C) Add a function that calculates the rotation angle between on-sky cartesian and NOTT image/pupil plane cartesian frames. 
# --> Got VLTI maps from M.A.M., still need Asgard 3D models to have a grasp of the complete sequence of passed mirrors from post-switchyard to NOTT image plane.

# D) Check symbolic & numeric framework setup. 
# --> What changes were made to the bench in the past year? How to change the framework to account for this?
# --> Translation distances changed? Effect of flexure mounts on distances? Need re-simulation in Zemax?
# --> Specifications of any optics changed? OAP2: Horizontal diameter increased but shape and focal length should be unchanged.

# E) Improve general code efficiency. 
# F) Complete documentation. 

# G) Re-run framework performance with the flexure mounts. Compare to thesis results.
# H) Optimize the efficiency of localization & optimization algorithms - i.e., decide on spiral steps and speeds.
# I) Write and run algorithm performance.

#---------#
# Imports #
#---------#

# General
from sympy import *
import numpy as np
import matplotlib.pyplot as plt
import random

import sys
import time
from datetime import datetime,timedelta,timezone
import logging

# OPCUA
from nottcontrol.opcua import OPCUAConnection
# Silent messages from opcua every time a command is sent
logger = logging.getLogger("asyncua")
logger.setLevel(logging.WARNING)
from nottcontrol.components.motor import Motor
from nottcontrol.camera.frame import Frame
from nottcontrol.lucid.lib.lucid_utils import LucidUtils
from nottcontrol.script.lib.nott_database import define_time
from nottcontrol.script.lib.nott_database import get_field
from configparser import ConfigParser
from nottcontrol import config as nott_config
from nottcontrol.script import data_files

#-----------------------------#
# Parameters from config file #
#-----------------------------#
# Opcua address
url = nott_config['DEFAULT']['opcuaaddress']
# Global parameters
t_write = nott_config.getint('redis', 't_write')
bool_UT = nott_config.getboolean('injection', 'bool_UT')
bool_offset = nott_config.getboolean('injection', 'bool_offset')
fac_loc = nott_config.getint('injection', 'fac_loc')
SNR_inj = nott_config.getint('injection', 'SNR_inj')
acq_time = nott_config.getfloat('injection', 'acq_time')
Ncrit = nott_config.getint('injection', 'Ncrit')
Nsteps_skyb = nott_config.getint('injection', 'Nsteps_skyb')
Nexp = nott_config.getint('injection', 'Nexp')
disp_double = nott_config.getfloat('injection', 'disp_double')
step_double = nott_config.getfloat('injection', 'step_double')
speed_double = nott_config.getfloat('injection', 'speed_double')
print("Read configuration [t_write,bool_UT,bool_offset,fac_loc,SNR_inj,acq_time,Ncrit,Nsteps_skyb,Nexp,disp_double,step_double,speed_double] : ",[t_write,bool_UT,bool_offset,fac_loc,SNR_inj,acq_time,Ncrit,Nsteps_skyb,Nexp,disp_double,step_double,speed_double])

# Time stamping functions

def unix_to_datetime(unix_stamp):
    # Converting unix_stamp (milliseconds since 01/01/1970 00:00:00) to a datetime object
    epoch = datetime.fromtimestamp(0,timezone.utc)
    dt = timedelta(milliseconds=unix_stamp)
    utc_stamp = epoch + dt
    return utc_stamp
    
def datetime_to_id(utc_stamp):
    # Converting datetime object utc_stamp to frame_id (Y%m%d_H%M%S formatted string, date and time separated by an underscore)
    Ymd = utc_stamp.strftime("%Y%m%d")
    HMS = utc_stamp.strftime("%H%M%S%f")[:-3]
    frame_id = Ymd+"_"+HMS
    return frame_id
    
class alignment:
     
    def __init__(self, ts, humint):
        """    
        Terminology
        ----------
        X = Shift in the x-direction, in the pupil plane (cold stop)
        Y = Shift in the y-direction, in the pupil plane (cold stop)
        x = Shift in the x-direction, in the image plane (chip input)
        y = Shift in the y-direction, in the image plane (chip input)
        (a1X,a2X) = TTM1 X and TTM2 X angular offsets (tip).
        (a1Y,a2Y) = TTM1 Y and TTM2 Y angular offsets (tilt).
        Note : A TTM X angle should be interpreted as an angle about the X-axis.
               Therefore, a TTM X angle induces a positional Y shift & vice versa.
        (D1,...,D8) = Distances traveled by the beam throughout the system, between components.
        di,dc = Injection & cold stop lens thicknesses
        P1 = Injection lens front surface optical power
        R1,R2,Rsl = OAP1,OAP2,Slicer curvature radii
               
        Description
        ----------
        The function does the following:
            (1) Define Sympy symbols.
            (2) Define general component transformations.
            (3) Chain together the transformations, encountered by a beam as it 
                travels through NOTT. This procedure is done independently for the
                transverse X and Y dimensions. The result is four equations, each linking
                one of (X,Y,x,y) to the relevant angular offsets (TTM Y for X/x-direction shifts & vice versa).
            (4) Define vector N globally, comprising the four symbolic equations.
            (5) Translate the obtained four equations into one single matrix equation b=Ma, with b the shifts and a the angular offsets.
            (6) Define matrix M and vector of symbolic shifts b globally. 
            (7) Construct lambdified evaluators for the internal forward (_int), reverse (_int_reverse) and sky framework.
                One lambdify is constructed per wavelength channel.
                These evaluators are then called in the framework evaluation methods.
                Pre-computing them minimizes Sympy overhead in these methods. 
            (8) Define the actuator positions, corresponding to a state of optimized injection, globally.
            (9) Open an OPCUA connection and initialise actuator Motor objects for all configurations.

        Parameters
        ----------
        ts : redis Timeseries client, reference to the redis database client
             Used for timestamping actuator position readouts by redis database time
             Client should be the same one as the one used in the HumInt object
        humint : human interface for frame acquisition, instance of the HumInt class (see human_interface.py)
                   
        Defines
        -------
        The function initializes global variables M, N and b, which are then used in numeric framework evaluations.
        self.M : (4,4) matrix of symbolic Sympy expressions (stored for reference)
        self.N : (1,4) matrix of symbolic Sympy expressions (stored for reference)
        self.b : (4,1) matrix of symbolic Sympy expressions (stored for reference)
        self._eval_int : list of 3 callables (index = wavelength)
                         f(X,Y,x,y, ...) > ttm_offsets
        self._eval_rev : list of 3 callables (index = wavelength)
                         f(a1X,a1Y,a2X,a2Y, ...) > shifts
        self._eval_sky : list of 3 callables (index = wavelength)
                         f(dTTM1X,dTTM1Y, ...) > (Minv, a2X, a2Y)
        self.act_pos_align : (4,4) numpy array (config, actuator) of actuator positions in aligned state
        self.opcua_conn : OPCUAconnection
        self.actuators : (4,4) numpy array (config, actuator) of Motor objects
        self.ts : redis client reference for timestamping  
            
        """

        self.ts = ts
        self.humint = humint

        # Identify photometric output ROI indices
        photo_idx = np.zeros(4, dtype=np.int32)
        for i in range(0, 4):
            photo_idx[i] = humint.channel_roi_link["P"+str(i+1)]
        self.photo_idx = photo_idx
        
        print("Defining symbolic framework ...")
        #---------------------------#
        # (1) Symbols and constants #
        #---------------------------#
        # Symbols and optical constants are defined locally in initialisation, become redundant once the lambdified callables are built

        # Symbols
        # -------
        X,x,Y,y = symbols("X x Y y")
        a1X,a2X,a1Y,a2Y = symbols("a_1^X a_2^X a_1^Y a_2^Y") 
        D1, D2, D3, D4, D5, D6, D7, D8 = symbols("D_1 D_2 D_3 D_4 D_5 D_6 D_7 D_8")
        di, dc, ni, nc, P1, f1, f2, fsl = symbols("d_i d_c n_i n_c P_1 f_{OAP_1} f_{OAP_2} f_{sl}")

        # Optical constants
        #------------------
        # Slicer quantities (mm) (Zemax)
        Rsli = 96.644
        fsli = -Rsli / 2
        # OAP focal lengths (mm) (Garreau et al. 2024)
        fOAP1 = 629.2 
        fOAP2 = 262.17
        # Lens thicknesses (mm) (Zemax)
        dinj = 10 
        dcryo = 4
        # Lens refractive indices in wavelength channels (Literature)
        niarr = np.array([2.4189, 2.4176, 2.4168], dtype=np.float64) 
        ncarr = np.array([1.4140, 1.4115, 1.4096], dtype=np.float64)
        # Injection lens curvature radius (front surface)
        Rinj = 28.195
        # Optical power front injection lens surface (1/mm)
        Parr = (niarr - np.ones(3, dtype=np.float64)) / Rinj
        
        #-------------------------------#
        # (2) Component transformations #
        #-------------------------------#
        def Translation(D, M):
            return Matrix([[1, D],[0, 1]]) * M 
        def TTM(a, M):
            return -M + Matrix([[0],[2*a]])
        def ThinLens(f, nv, nprimv, M):
            return Matrix([[1,0],[-1/f,nv/nprimv]])*M
        def ThickLens(p1, p2, dv, nv, nprimv, n2v, M):
            return Matrix([[1-p1*dv/n2v, nv*dv/n2v],[-p1/nprimv - p2/nprimv + p1*p2*dv / (nprimv * n2v), (1 - p2*dv / n2v)*(nv/nprimv)]])*M
        
        #------------------------------#
        # (3) Chaining transformations #
        #------------------------------#
        # Initial state
        initX = Matrix([[0], [0]])
        initY = Matrix([[0], [0]])
        # TTM1
        M1X = TTM(a1Y,initX)
        M1Y = TTM(a1X,initY)
        # Translation (delay lines)
        M2X = -Translation(D1,M1X)
        M2Y = Translation(D1,M1Y)
        # TTM2
        M3X = TTM(a2Y,M2X)
        M3Y = TTM(a2X,M2Y)
        # Translation
        M4X = Translation(D2,M3X)
        M4Y = Translation(D2,M3Y)
        # OAP1
        M5X = -ThinLens(f1, 1, 1, M4X)
        M5Y = -ThinLens(f1, 1, 1, M4Y)
        # Translation (mirrors)
        M6X = -Translation(D3, M5X)
        M6Y = -Translation(D3, M5Y)
        # Slicer
        M7X = -ThinLens(fsl, 1, 1, M6X)
        M7Y = -ThinLens(fsl, 1, 1, M6Y)
        # Translation 
        M8X = Translation(D4, M7X)
        M8Y = Translation(D4, M7Y)
        # OAP2
        M9X = -ThinLens(f2, 1, 1, M8X)
        M9Y = -ThinLens(f2, 1, 1, M8Y)
        # Translation
        M10X = Translation(D5, M9X)
        M10Y = Translation(D5, M9Y)
        # Cryostat lens
        M11X = ThickLens(0, 0, dc, 1, 1, nc, M10X)
        M11Y = ThickLens(0, 0, dc, 1, 1, nc, M10Y)
        # Translation
        M12X = Translation(D6, M11X)
        M12Y = Translation(D6, M11Y)
        ###################
        # Cold stop plane #
        ###################
        # Translation
        M13X = Translation(D7, M12X)
        M13Y = Translation(D7, M12Y)
        # Injection Lens
        M14X = ThickLens(P1, 0, di, 1, 1, ni, M13X)
        M14Y = ThickLens(P1, 0, di, 1, 1, ni, M13Y)
        # Translation
        M15X = Translation(D8, M14X)
        M15Y = Translation(D8, M14Y)
        ###############
        # Image Plane #
        ###############
        # Matrices M12 and M15 now contain shifts and offsets in the cold stop pupil and the image plane respectively.
        M12X = M12X.applyfunc(simplify)
        M15X = M15X.applyfunc(simplify)
        M12Y = M12Y.applyfunc(simplify)
        M15Y = M15Y.applyfunc(simplify)
        
        #-------------#
        # (4) Merging #
        #-------------#
        eqns = [M12X[0]-X,M12Y[0]-Y,M15X[0]-x,M15Y[0]-y]
        
        Mloc, bloc = linear_eq_to_matrix(eqns, [a1Y,a1X,a2Y,a2X])
        
        eqns_ = [M12X[0],M12Y[0],M15X[0],M15Y[0]]
        
        # Defining framework 
        self.M = Mloc.copy()
        self.b = bloc.copy()
        self.N = eqns_.copy()

        #-------------------------------------------------------------#
        # 5) Build lambdified callable for each wavelength            |
        #    Inter-component distances remain as free symbols         |
        #    Other optical constants are common among all evaluations |
        # ------------------------------------------------------------#
        # Optical parameter substitution build
        def _optical_subspar(lam):
            return [(di, dinj), (dc, dcryo), (ni, niarr[lam]), (nc, ncarr[lam]), (P1, Parr[lam]), (f1, fOAP1), (f2, fOAP2), (fsl, fsli)]

        D_syms = (D1, D2, D3, D4, D5, D6, D7, D8)
        D_names = "D1,D2,D3,D4,D5,D6,D7,D8"

        def _build_eval_int(lam, Minv):
            # Substitute optical constants
            bsub = self.b.subs(_optical_subspar(lam))
            # Construct framework - (4,1) Sympy matrix
            frame = Minv * bsub
            # Lambdify to evaluator
            f = lambdify((X, Y, x, y) + D_syms, frame.T.tolist()[0], modules="numpy")
            return f
            
        def _build_eval_rev(lam):
            # Substitute optical constants
            Nsub = [expr.subs(_optical_subspar(lam)) for expr in self.N]
            # Lambdify to evaluator
            f = lambdify((a1X, a1Y, a2X, a2Y) + D_syms, Nsub, modules="numpy")
            return f

        def _build_eval_sky(Minv):
            # Lambdify to evaluator (a2X, a2Y deliberately survive as sympy symbols, since they are unknowns determined in a solveset call)
            f = lambdify(D_syms, Minv, modules="sympy")
            return f

        print("Building lambdified framework evaluators ...")
        self._eval_int = []
        self._eval_rev = []
        self._eval_sky = []
        for lam in range(0, 3):
            print("Wavelength channel {lam}")
            Msub = self.M.subs(_optical_subspar(lam))
            Minv = Msub.inv(method="LU")
            self._eval_int.append(_build_eval_int(lam, Minv))
            self._eval_rev.append(_build_eval_rev(lam))
            self._eval_sky.append(_build_eval_sky(Minv))

        # Define a2X and a2Y symbols outside of __init__, for use in solveset
        self._a2X = a2X
        self._a2Y = a2Y

        print("Framework ready.")
        
        # Defining actuator positions corresponding to an aligned & injecting state.
        self.act_pos_align = np.array([[4.1507145,4.6841595,4.8155535,3.714595],
                                       [3.6502095,3.4818495,4.5511795,3.8486425],
                                       [4.3360325,4.716886,4.754462,3.167242],
                                       [4.8310475,4.6418865,4.88122,4.0027285]],dtype=np.float64)

        # OPCUA connection
        print("Opening OPCUA connection ...")
        self.opcua_conn = OPCUAConnection(url)
        self.opcua_conn.connect()
        print("OPCUA connection established.")
        print("Initializing actuator Motor objects ...")
        # Actuator Motor objects
        self.actuators = []
        for i in range(1, 5):
            act_names = ['NTTA'+str(i), 'NTPA'+str(i), 'NTTB'+str(i), 'NTPB'+str(i)]
            acts = [Motor(self.opcua_conn, 'ns=4;s=MAIN.nott_ics.TipTilt.'+name, name, 0.020) for name in act_names]
            self.actuators.append(acts)
        print("Actuator Motor objects initialized.")

    def __del__(self):
        # Disconnect from OPCUA
        if hasattr(self, 'opcua_conn'):
            try:
                self.opcua_conn.disconnect()
            except Exception:
                pass

    def close(self):
        # Manual wrapper to close the OPCUA connection
        if hasattr(self, 'opcua_conn'):
            self.opcua_conn.disconnect()
        
    #-------------------------------#
    # Numeric Framework Evaluations #
    #-------------------------------#
    def _framework_numeric_int(self,shifts,D,lam=1):
        """
        Description
        -----------
        The function numerically evaluates the symbolic framework by input positional shifts (X,Y,x,y),
        returning thereto necessary angular offsets (dTTM1X,dTTM1Y,dTTM2X,dTTM2Y).
        
        Context
        -------
        The function is called in the context of internal NOTT alignment, f.e. scanning the image plane for beam injection.
        This is a pure numpy evaluation, leveraging the lambdified evaluator constructed in class init
        
        Parameters
        ----------
        shifts : (1,4) numpy array of floats (mm)
            User-desired positional shifts (X,Y,x,y) in cold stop (X,Y) and image (x,y) plane.
        D : (1,8) numpy array of floats (mm)
            Eight distance values (D1,...,D8) traveled by the reference beam between components.
        lam : single integer
            NOTT wavelength channel number (0 = 3.5 micron ; 1 = 3.8 micron ; 2 = 4.0 micron)
        Do note : Distance grid Dgrid is simulated for the central wavelength in Zemax.
            
        Returns
        -------
        ttm_offsets : (1,4) numpy array of floats (radian)
        The angular TTM offsets (dTTM1X,dTTM1Y,dTTM2X,dTTM2Y) necessary to achieve the input shifts 
            
        """
        
        # Numeric evaluation
        result = self._eval_int[lam](shifts[0], shifts[1], shifts[2], shifts[3], D[0], D[1], D[2], D[3], D[4], D[5], D[6], D[7])
        # Flipping X and Y angles to comply with function output
        ttm_offsets = np.array([result[1],result[0],result[3],result[2]],dtype=np.float64)
        
        return ttm_offsets
    
    def _framework_numeric_int_reverse(self,ttm_offsets,D,lam=1):
        """
        Description
        -----------
        The function numerically evaluates the symbolic framework by input TTM angular offsets (dTTM1X,dTTM1Y,dTTM2X,dTTM2Y),
        returning the positional shifts (X,Y,x,y) that the offsets induce.
        This is a pure numpy evaluation, leveraging the lambdified evaluator constructed in class init

        Parameters
        ----------
        ttm_offsets : (1,4) numpy array of floats (rad)
            User-desired TTM angular offsets (dTTM1X,dTTM1Y,dTTM2X,dTTM2Y).
        D : (1,8) numpy array of floats (mm)
            Eight distance values (D1,...,D8) traveled by the reference beam between components.
        lam : single integer
            NOTT wavelength channel number (0 = 3.5 micron ; 1 = 3.8 micron ; 2 = 4.0 micron).
        Do note : Distance grid Dgrid is simulated for the central wavelength in Zemax.

        Returns
        -------
        shifts : (1,4) numpy array of floats (mm)
            Induced positional shifts in CS/IM planes (X,Y,x,y).

        """
        result = self._eval_rev[lam](ttm_offsets[0], ttm_offsets[1], ttm_offsets[2], ttm_offsets[3], D[0], D[1], D[2], D[3], D[4], D[5], D[6], D[7])
        shifts = np.array(result, dtype=np.float64)
        return shifts
    
    def _framework_numeric_sky(self,dTTM1X,dTTM1Y,D,lam=1,CS=True):
        """
        Description
        -----------
        The function numerically evaluates the symbolic framework expression by substituting the input dTTM1X & dTTM1Y angular offsets.
        Then, the shifts (X,Y,x,y) are determined as a function of the remaining angular offsets (dTTM2X,dTTM2Y).
        Based on parameter CS, a choice is made : if True, (dTTM2X,dTTM2Y) are determined such that (X,Y)=(0,0) - fixed pupil position.
                                                  if False, (dTTM2X,dTTM2Y) are determined such that (x,y)=(0,0) - fixed image position.
                                                  No non-trivial combination of (dTTM2X,dTTM2Y) exists that guarantees both.
        Inversion of matrix M and substitution of optical constants has been done in class init.
        Only remaining Sympy work is in the solveset call, for two linear expressions in a2X and a2Y.
        Remaining work is pure numpy evaluation.
                                             
        Context
        -------
        The function is relevant in the context of on-sky scanning. There, TTM1 takes the role of the scanner; a TTM1 angular offset changes the on-sky angle of the picked up FOV.
        A desired on-sky angular offset should then be translated to a necessary TTM1 angular offset, which is to be imposed to the system.
        Thereafter, the TTM2 angular offsets should be calculated that make it such that the scanning has no effect on alignment in a user-specified plane (CS/IM).
        
        Parameters
        ----------
        dTTM1X,dTTM1Y : two float values
            User-desired TTM1 angular offsets, calculated from desired on-sky angles by étendue conservation.
        D : (1,8) numpy array of floats (mm)
            Eight distance values (D1,...,D8) traveled by the reference beam between components.
        lam : single integer
            NOTT wavelength channel number (0 = 3.5 micron ; 1 = 3.8 micron ; 2 = 4.0 micron).
        Do note : Distance grid Dgrid is simulated for the central wavelength in Zemax.
        CS : boolean
            True (default) if the user wants a sky shift to keep the cold stop position unchanged.
            False if the user wants a sky shift to keep the image plane position unchanged.
            
        Returns
        -------
        ttm_offsets : (1,4) numpy array of floats
            Array of angular TTM offsets (dTTM1X,dTTM1Y,dTTM2X,dTTM2Y), containing : 
            The angular TTM offsets (dTTM2X,dTTM2Y) that keep either the CS or IM position unchanged for induced offsets (dTTM1X,dTTM1Y)
        shifts : (1,4) numpy array of floats
            The shifts that come at the cost of inducing the TTM angles.
            
        """
        # Loading a2X, a2Y symbols
        a2X = self._a2X
        a2Y = self._a2Y
        # Loading Minv from lambdified evaluator
        Minv = self._eval_sky[lam](D[0], D[1], D[2], D[3], D[4], D[5], D[6], D[7])
        # Evaluating
        c = Matrix([dTTM1Y,dTTM1X,a2Y,a2X])
        sol = Minv * c # contains (X,Y,x,y) as linear expressions of (a2X, a2Y)
        
        if CS:
            dTTM2X = list(solveset(sol[1],a2X).args)[0]
            dTTM2Y = list(solveset(sol[0],a2Y).args)[0]
            x = float(sol[2].subs([(a2X,dTTM2X),(a2Y,dTTM2Y)]))
            y = float(sol[3].subs([(a2X,dTTM2X),(a2Y,dTTM2Y)]))
                            
            ttm_offsets = np.array([dTTM1X,dTTM1Y,float(dTTM2X),float(dTTM2Y)],dtype=np.float64)
            shifts = np.array([0.0,0.0,x,y],dtype=np.float64)
            
            return ttm_offsets,shifts
        else:
            dTTM2X = list(solveset(sol[3],a2X).args)[0]
            dTTM2Y = list(solveset(sol[2],a2Y).args)[0]
            X = float(sol[0].subs([(a2X,dTTM2X),(a2Y,dTTM2Y)]))
            Y = float(sol[1].subs([(a2X,dTTM2X),(a2Y,dTTM2Y)]))
                            
            ttm_offsets = np.array([dTTM1X,dTTM1Y,float(dTTM2X),float(dTTM2Y)],dtype=np.float64)
            shifts = np.array([X,Y,0.0,0.0],dtype=np.float64)
            
            return ttm_offsets,shifts
        
    #######################
    # Auxiliary Functions #
    #######################

    def _sky_to_ttm(self,sky_angles):
        """    
        Description 
        ----------
        Input on-sky angular offsets are converted to output TTM angular offsets by 
        conservation of étendue between entrance and exit pupil.
    
        Constants
        ----------
        Entrance pupil beam diameter : 8.2 m for UTs, 1.8 m for ATs
        Exit pupil (TTM positions) beam diameter : 12 mm 
        Note : Asgard/Heimdallr brings all four VLTI beams to a diameter of 12 mm, regardless of AT pupil diameter.
        
        Parameters
        ----------
        sky_angles : (1,4) numpy array of floats (radian)
            An array of on-sky angular offsets 
            
        Returns
        -------
        ttm_angles : (1,4) numpy array of floats (radian)
            An array of TTM angular offsets

        """
        Dexit = 12*10**(-3)  
        if bool_UT:
            Dentr = 8.2
        else:
            Dentr = 1.8 
        
        D_rat = Dentr/Dexit
        sinpar = D_rat * np.sin(sky_angles)
        
        if (np.abs(sinpar) > 1).any():
            raise ValueError("At least one of the specified on-sky angles is too large. Applying étendue conservation to convert to TTM angles would mean taking the arcsin of a value > 1.")
            
        ttm_angles = np.arcsin(D_rat * np.sin(sky_angles))
            
        return ttm_angles
        
    def _ttm_to_sky(self,ttm_angles):
        """    
        Description 
        ----------
        Function with the reverse effect of _sky_to_ttm.
        See documentation in _sky_to_ttm
        """
        Dexit = 12*10**(-3)  
        if bool_UT:
            Dentr = 8.2
        else:
            Dentr = 1.8
        
        D_rat = Dexit/Dentr
        sky_angles = np.arcsin(D_rat * np.sin(ttm_angles))
        
        return sky_angles
            
    def _snap_distance_grid(self,ttm_angles,config):
        """
        Description
        -----------
        For a given set of TTM angles, corresponding to a reference configuration, the 
        closest point in the Zemax simulated grid is found and its corresponding distance is returned. 

        Auxiliary
        ---------
        Dgrid : (4,8,11,5,11,5) numpy matrix of float values (mm)
                From left to right, the dimensions correspond to (configuration,inter-component distance,TTM1Y,TTM2Y,TTM1X,TTM2X)
        TTM1X,TTM1Y : Two (4,11) numpy matrices of float values (radian)
                TTM1 angles by which Dgrid is simulated
        TTM2X,TTM2Y : Two (4,5) numpy matrices of float values (radian)
                TTM2 angles by which Dgrid is simulated
            
        Remarks
        -------
        The grid is simulated for an approximate range of absolute angles of pm 1000 microrad for TTM1 and pm 500 microrad for TTM2. 
        As of now, no TTM angles beyond these values are supported.
            
        Parameters
        ----------
        ttm_angles : (1,4) numpy array of floats
            TTM angles (TTM1X,TTM1Y,TTM2X,TTM2Y)
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3).
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 - in Garreau et al. 2024 - for reference).

        Returns
        -------
        D_snap : (1,8) numpy array of float values (mm)
            An array of Zemax-simulated distances (D1,...,D8) corresponding to the grid point closest to ttm_angles

        """
        
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
    
        a = np.argmin(np.abs(data_files.TTM1Ygrid[config] - ttm_angles[1]))
        b = np.argmin(np.abs(data_files.TTM2Ygrid[config] - ttm_angles[3]))
        c = np.argmin(np.abs(data_files.TTM1Xgrid[config] - ttm_angles[0]))
        d = np.argmin(np.abs(data_files.TTM2Xgrid[config] - ttm_angles[2]))
        
        D_snap = data_files.Dgrid[config,:,a,b,c,d]
  
        return D_snap

    def _snap_accuracy_grid(self,speed,disp):
        """
        Description
        -----------
        For given actuators speeds and displacements, linear interpolation of the closest four accuracy grid points is performed to 
        return an accuracy value for each of the four actuators.
        Note : For points outside of the simulated grid ranges, the function returns the accuracy of the closest, edge grid point.
        This approach is incomplete. This function is never called for points outside of the simulated grid.
    
        Auxiliary
        ---------
        accurgrid_pos : (1,21,21) numpy matrix of float values (mm) 
            Simulated accuracies (achieved minus imposed position, obtained using NTPB2) for positive displacements.
        accurgrid_neg : (1,21,21) numpy matrix of float values (mm)
            Simulated accuracies (achieved minus imposed position, obtained using NTPB2) for negative displacements.
        disp_range and speed_range indicate the displacements and speeds by which these auxiliary accuracy grids were simulated.
        
        Parameters
        ----------
        speed : (1,4) numpy array of floats (mm/s)
            The speeds by which the actuators are to be moved.
        disp : (1,4) numpy array of floats (mm) 
            The displacements by which the actuators are to be moved.

        Returns
        -------
        a_snap : (1,4) numpy array of floats (mm)
            Accuracy value for each actuator, obtained by linear interpolation.

        """
        
        # Container array for accuracies
        a_snap = np.zeros(len(speed))
        # Looping over all four actuators 
        for i in range(0, len(speed)):
            if disp[i] != 0:
                # Sign of displacement
                sign = np.sign(disp[i])
                # Simulation ranges of grid
                disp_range = sign*np.geomspace(0.0005,0.025,21) 
                speed_range = np.geomspace(0.0005/100,0.025,21) 
                # Determining indices (i1,j1) of closest neighbouring grid point
                disp_diff = np.abs(disp_range - disp[i])
                speed_diff = np.abs(speed_range - speed[i])
                i1 = np.argmin(disp_diff)
                j1 = np.argmin(speed_diff)
                # Determining indices (i2,j2) of second closest neighbouring grid point
                
                # 1) Displacement
                # Point is right of closest grid point...
                if np.abs(disp[i]) > np.abs(disp_range[i1]):
                    # ... and beyond the grid range:
                    if (i1 == len(disp_range)-1):
                        i2 = i1
                    # ... and within the grid range:
                    else:
                        i2 = i1+1
                # Left of closest grid point...
                elif np.abs(disp[i]) < np.abs(disp_range[i1]):
                    # ... and beyond the grid range:
                    if (i1 == 0):
                        i2 = i1
                    # ... and within the grid range:
                    else:
                        i2 = i1-1
                # On grid point
                elif disp[i] == disp_range[i1]:
                    i2 = i1
                    
                # 2) Speed
                if speed[i] > speed_range[j1]:
                    if (j1 == len(speed_range)-1):
                        j2 = j1
                    else:
                        j2 = j1+1
                elif speed[i] < speed_range[j1]:
                    if (j1 == 0):
                        j2 = j1
                    else:
                        j2 = j1-1
                elif speed[i] == speed_range[j1]:
                    j2 = j1
    
                # Weights 
                if (i1==i2):
                    v1,v2 = [0.5,0.5]
                else:
                    v2,v1 = [disp_diff[i1],disp_diff[i2]]/(disp_diff[i1]+disp_diff[i2])
                if (j1==j2):
                    w1,w2 = [0.5,0.5]
                else:
                    w2,w1 = [speed_diff[j1],speed_diff[j2]]/(speed_diff[j1]+speed_diff[j2]) 
                # Interpolation
                if sign > 0:
                    # Accuracy interpolation
                    a_disp = v1*data_files.accurgrid_pos[i1,j1]+v2*data_files.accurgrid_pos[i2,j1]
                    a_speed = w1*data_files.accurgrid_pos[i1,j1]+w2*data_files.accurgrid_pos[i1,j2]
                    # Average
                    a_snap[i] = (a_disp+a_speed)/2
                if sign < 0:
                    # Accuracy interpolation
                    a_disp = v1*data_files.accurgrid_neg[i1,j1]+v2*data_files.accurgrid_neg[i2,j1]
                    a_speed = w1*data_files.accurgrid_neg[i1,j1]+w2*data_files.accurgrid_neg[i1,j2]
                    # Average
                    a_snap[i] = (a_disp+a_speed)/2
        
        return a_snap

    def _get_actuator_pos(self,config):
        """
        Description
        -----------
        The function retrieves the current absolute on-bench actuator positions, for the specified configuration, by communication with opcua.
        The corresponding timestamp is fetched from the redis database, querying the "cam_integtime" field.
        This is purposely done to sync with the timestamps associated to acquired IR camera frames
        (see frame acquisition methods in human_interface.py)
        That way, read frames can be unambiguously linked to associated actuator positions in localization / optimization spirals.
        
        Parameters
        ----------
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3).
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference).

        Returns
        -------
        pos : (1,4) numpy array of float values (mm)
            Current actuator positions for the specified configuration (=beam)
        time : single integer (ms)
            Redis database timestamp at which the actuator positions were read out.

        """
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")

        acts = self.actuators[config]
        pos = np.array([acts[i].getPositionAndSpeed()[0] for i in range(0, 4)], dtype=np.float64)
        timestamp = self.ts.ts.get("cam_integtime")[0]
        
        return [pos, timestamp]
    
    def _actuator_position_to_ttm_angle(self,pos,config):
        """
        Description
        -----------
        The function links given actuator positions to the TTM angles they induce.
        
        Parameters
        ----------
        pos : (1,4) numpy array of floats (mm)
            The actuator (x1,x2,x3,x4) positions.
            
        Constants 
        ---------
        d1_pa : TTM1 (Siskyou IXF2.0a M flexure mount) pivot-to-actuator distance (mm) 
        d2_pa : TTM2 (Newport U200-G2K Ultima gimbal mount) pivot-to-actuator distance (mm)

        Remarks
        -------
        For both sets of TTMs : The two actuators are installed in agreement with the transverse X/Y dimensions.
                                To achieve a TTMX/TTMY (tip/tilt) angular offset, the corresponding actuator can act independently.
        For the set of TTM1s : The pivot point is located at the bottom of the flexure ridge and it remains fixed (to fair approximation) through tip/tilt motion, as confirmed by Siskyou.
                               The lever arm stretches from this pivot to the point where the actuator holder clamps the actuator.
                               Motorized tip-tilt motion is induced thanks to the actuator - affirmed to the mount sub-part that is to be tipped/tilted via an actuator holder - pushing against a driver block on the adjacent sub-part.
                               Lever arm distance deduced from CAD models provided by Siskyou.
        For the set of TTM2s : The pivot point is located at the center of the front optical cavity, by gimbal design.
                               The lever arm stretches from this pivot to the contact point of the actuator and the mount.
                               Lever arm distance measured on-bench. 

        Returns
        -------
        ttm_angles : (1,4) array of floats (radian)
            The TTM (TTM1X,TTM1Y,TTM2X,TTM2Y) angles.

        """
        # Lever arm distances
        d1_pa = 71.566060392 
        d2_pa = 1.375*25.4
        # Zemax optimal coupling angles (rad)
        ttm_angles_optim = np.array([[0.10,32,-0.11,-41],[4.7,-98,4.9,30],[-2.9,134,-3.1,-107],[3.7,115,3.3,-141]],dtype=np.float64)*10**(-6)
        ttm_config = ttm_angles_optim[config]
        # Actuator positions in a state of alignment (mm)
        act_config = self.act_pos_align[config]

        # TTM1X
        TTM1X = ttm_config[0] + (pos[1]-act_config[1])/d1_pa    
        # TTM1Y
        TTM1Y = ttm_config[1] + (pos[0]-act_config[0])/d1_pa
        # TTM2X
        TTM2X = ttm_config[2] - np.arcsin((pos[3]-act_config[3])/d2_pa)
        # TTM2Y
        TTM2Y = +ttm_config[3] + np.arcsin((pos[2]-act_config[2])/d2_pa)
        
        ttm_angles = np.array([TTM1X,TTM1Y,TTM2X,TTM2Y],dtype=np.float64)
        
        return ttm_angles
    
    def _ttm_angle_to_actuator_position(self,ttm_angles,config):
        """
        Description
        -----------
        The function links given TTM angles to the actuator positions that induce them.
        
        Parameters
        ----------
        ttm_angles : (1,4) array of floats (radian)
            The TTM (TTM1X,TTM1Y,TTM2X,TTM2Y) angles.
            
        Constants 
        ---------
        d1_pa : TTM1 (Siskyou IXF2.0a M flexure mount) pivot-to-actuator distance (mm) 
        d2_pa : TTM2 (Newport U200-G2K Ultima gimbal mount) pivot-to-actuator distance (mm)

        Remarks
        -------
        For both sets of TTMs : The two actuators are installed in agreement with the transverse X/Y dimensions.
                                To achieve a TTMX/TTMY (tip/tilt) angular offset, the corresponding actuator can act independently.
        For the set of TTM1s : The pivot point is located at the bottom of the flexure ridge and it remains fixed (to fair approximation) through tip/tilt motion, as confirmed by Siskyou.
                               The lever arm stretches from this pivot to the point where the actuator holder clamps the actuator.
                               Motorized tip-tilt motion is induced thanks to the actuator - affirmed to the mount sub-part that is to be tipped/tilted via an actuator holder - pushing against a driver block on the adjacent sub-part.
                               Lever arm distance deduced from CAD models provided by Siskyou.
        For the set of TTM2s : The pivot point is located at the center of the front optical cavity, by gimbal design.
                               The lever arm stretches from this pivot to the contact point of the actuator and the mount.
                               Lever arm distance measured on-bench.   

        Returns
        -------
        pos : (1,4) numpy array of floats (mm)
            The actuator (x1,x2,x3,x4) positions.
        """

        # Center-to-actuator distances
        d1_pa = 71.566060392 
        d2_pa = 1.375*25.4
        # Zemax optimal coupling angles (rad)
        ttm_angles_optim = np.array([[0.10,32,-0.11,-41],[4.7,-98,4.9,30],[-2.9,134,-3.1,-107],[3.7,115,3.3,-141]],dtype=np.float64)*10**(-6)
        ttm_config = ttm_angles_optim[config]
        # Actuator positions in a state of alignment (mm)
        act_config = self.act_pos_align[config]
    
        # TTM1
        x1 = act_config[0] + d1_pa*(ttm_angles[1]-ttm_config[1])
        x2 = act_config[1] + d1_pa*(ttm_angles[0]-ttm_config[0])
        # TTM2 
        x3 = act_config[2] - d2_pa*np.sin(ttm_config[3]-ttm_angles[3])
        x4 = act_config[3] + d2_pa*np.sin(ttm_config[2]-ttm_angles[2])
        
        pos = np.array([x1,x2,x3,x4],dtype=np.float64)
        
        return pos

    def _ttm_shift_to_actuator_displacement(self,ttm_angles,ttm_shifts,config):
        """
        Description
        -----------
        Function that relates demanded angular TTM offsets, away from an initial TTM configuration, 
        to the necessary actuator displacements.
        
        Parameters
        ----------
        ttm_angles : (1,4) numpy array of float values (radian)
            Initial (TTM1X,TTM1Y,TTM2X,TTM2Y) angular configuration.
        ttm_shifts : (1,4) numpy array of float values (radian)
            Angular offsets (dTTM1X,dTTM1Y,dTTM2X,dTTM2Y) away from the initial configuration.

        Returns
        -------
        displacements : (1,4) numpy array of float values (mm)
            The actuator displacements (dx1,dx2,dx3,dx4) necessary to achieve the demanded angular offsets.
            dx1 : Displacement of the TTM1 actuator whose motion is in the XZ plane, thus inducing TTM1 Y (tilt) angles.
            dx2 : Displacement of the TTM1 actuator whose motion is in the YZ plane, thus inducing TTM1 X (tip) angles. 
            dx3 : Displacement of the TTM2 actuator whose motion is in the XZ plane, thus inducing TTM2 Y (tilt) angles.
            dx4 : Displacement of the TTM2 actuator whose motion is in the YZ plane, thus inducing TTM2 X (tip) angles.
            Sign convention : A positive displacement is away from the actuator
    
        """
        # Final ttm angles
        ttm_final = ttm_angles + ttm_shifts
        
        # Initial actuator positions
        act_init = self._ttm_angle_to_actuator_position(ttm_angles,config)
        # Final actuator positions
        act_final = self._ttm_angle_to_actuator_position(ttm_final,config)
        
        displacements = np.array(act_final-act_init,dtype=np.float64)
        
        return displacements

    def _actuator_displacement_to_ttm_shift(self,act_pos,act_disp,config):
        """
        Description
        -----------
        Function that relates actuator displacements to the TTM offsets they induce away from the
        current TTM angles.

        Parameters
        ----------
        act_pos : (1,4) numpy array of floats (mm)
            Absolute actuator positions (x1,x2,x3,x4).
        act_disp : (1,4) numpy array of floats (mm)
            Actuator displacements (dx1,dx2,dx3,dx4).

        Returns
        -------
        ttm_shifts : (1,4) numpy array of floats (rad)
            Induced TTM angular offsets (dTTM1X,dTTM1Y,dTTM2X,dTTM2Y).

        """
        # Final actuator positions
        act_final = act_pos + act_disp
        
        # Initial TTM angles
        ttm_init = self._actuator_position_to_ttm_angle(act_pos,config)
        # Final TTM angles
        ttm_final = self._actuator_position_to_ttm_angle(act_final,config)
        
        ttm_shifts = np.array(ttm_final-ttm_init,dtype=np.float64)
        
        return ttm_shifts
    
    def _actoffset(self,act_speed,act_disp):
        """
        Description
        -----------
        The function returns the offsets that occur upon actuator displacement, obtained from empirical analysis.
        
        Parameters
        ----------
        act_speed : (1,4) numpy array of floats (mm/s)
            Speeds by which the actuators are to be moved.
        act_disp : (1,4) numpy array of floats (mm)
            Displacements by which the actuators are to be moved.
            
        Returns
        -------
        accur_snap : (1,4) numpy array of floats (mm)
            Accuracies (positional offsets) for the four actuators, retrieved from the empirical accuracy grid.
        
        """
        
        # Only return an empirical offset if the global variable is set to incorporate offsets.
        if bool_offset:
            # Snap accuracies
            accur_snap = np.array(self._snap_accuracy_grid(act_speed,act_disp),dtype=np.float64)
        else:
            # No empirical offsets to be incorporated
            accur_snap = np.zeros(4,dtype=np.float64)
        
        return accur_snap

    def _get_photo_broad(self, dt, config):
        """
        Description
        -----------
        Function returns the total, calibrated broadband flux and error as measured in the ROI that is matched to the photometric chip output of the beam in channel {config}.
        Flux and error are calculated from a master frame - obtained by averaging all acquired frames in time interval {dt} - see get_frames_cal(_broad).

        Parameters
        ----------
        dt : single float (s)
            Total frame acquisition time
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3).
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference).

        Returns
        -------
        cal_broad, cal_broad_std : single float each ; broadband flux and error in photometric output channel

        """

        cal_disp, cal_disp_std, cal_broad, cal_broad_std = self.humint.get_frames_cal_broad(dt)
        idx = self.photo_idx[config]
        cal_broad, cal_broad_std = cal_broad[idx], cal_broad_std[idx]
        return cal_broad, cal_broad_std

    def _valid_state(self,bool_slicer,ttm_angles_final,act_displacements,act_pos,config):
        """
        Description
        -----------
        The function carries out several checks concerning the validity of a TTM configuration.
        A final configuration can be invalid/troublesome in four ways:
            (1) The final configuration would displace the beam off the slicer.
            (2) The requested actuator displacement is lower than what is achievable by the resolution.
            --> In this case, the motion is carried out by double actuator motion. The user is warned but the state is not considered invalid. # TBD
            (3) The requested final TTM configuration is beyond the limits of what the actuator travel ranges (6 mm) can achieve
            (4) The requested final TTM configuration is beyond the current range supported by Dgrid (pm 1000 microrad for TTM1, pm 500 microrad for TTM2).
        Only a configuration that is not invalid in one of the four above ways will be considered as valid.

        Parameters
        ----------
        bool_slicer : single Boolean
            see individual_step
        ttm_angles_final : (1,4) numpy array of float values (radian)
            Final configuration of (TTM1X,TTM1Y,TTM2X,TTM2Y) angles.
        act_displacements : (1,4) numpy array of float values (mm)
            Actuator displacements (dx1,dx2,dx3,dx4).
        act_pos : (1,4) numpy array of float values (mm)
            Current absolute actuator positions (x1,x2,x3,x4) for the TTMs corresponding to beam "config".
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3).
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference).

        Returns
        -------
        Valid : A Boolean value denoting whether the final configuration is valid.
                True = valid , False = invalid
        i : a (1,4) numpy array of integers
            Indicates what conditions are violated by the configuration.

        """
    
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
    
        # Zemax optimal coupling angles 
        ttm_angles_optim = np.array([[0.10,32,-0.11,-41],[4.7,-98,4.9,30],[-2.9,134,-3.1,-107],[3.7,115,3.3,-141]],dtype=np.float64)*10**(-6)
        ttm_config = ttm_angles_optim[config]
    
        Valid = True
        i = np.array([0,0,0,0])
        
        #---------------#
        # Criterion (1) #
        #---------------#
        
        TTM1X = ttm_angles_final[0]
        TTM1Y = ttm_angles_final[1]
        TTM2X = ttm_angles_final[2]
        TTM2Y = ttm_angles_final[3]
        # Shifts away from optimal coupling
        TTM1X_shift = TTM1X-ttm_config[0]
        TTM1Y_shift = TTM1Y-ttm_config[1]
        TTM2X_shift = TTM2X-ttm_config[2]
        TTM2Y_shift = TTM2Y-ttm_config[3]
        
        # The boundaries in (TTM1Y_shift,TTM2Y_shift) space for this criterion were derived in Zemax. 
        # A conservative safe margin of 50 microrad is implemented.
        
        if (config == 0):
            valid1 = (TTM2Y_shift >= -TTM1Y_shift-459*10**(-6) and TTM2Y_shift <= -TTM1Y_shift+541*10**(-6))
        elif (config == 1):
            valid1 = (TTM2Y_shift >= -TTM1Y_shift-587*10**(-6) and TTM2Y_shift <= -TTM1Y_shift+508*10**(-6))
        elif (config == 2):
            valid1 = (TTM2Y_shift >= -TTM1Y_shift-243*10**(-6) and TTM2Y_shift <= -TTM1Y_shift+655*10**(-6))
        else:
            valid1 = (TTM2Y_shift >= -TTM1Y_shift-507*10**(-6) and TTM2Y_shift <= -TTM1Y_shift+443*10**(-6))
      
        if not valid1 and not bool_slicer:
            i[0] = 1
            Valid = valid1
      
        #---------------#
        # Criterion (2) #
        #---------------#
        
        # Actuator resolution (mm)
        act_res = 0.2 * 10**(-3) 
        
        crit2 = (np.abs(act_displacements) - act_res < 0)
        for j in range(0, 4):
            if np.logical_and(crit2[j],act_displacements[j] != 0):
                i[1] = 1
                print("Warning : displacement below actuator resolution, carried out by double motion.")
                #Valid = valid2
                

        
        #---------------#
        # Criterion (3) #
        #---------------#
    
        # Actuator travel range (mm)
        act_range = 6 
    
        for j in range(0, 4):
            disp = act_displacements[j]
            if disp > 0:
                valid3 = (act_range - act_pos[j] >= disp)
            else:
                valid3 = (act_pos[j] + disp >= 0)
    
            if not valid3:
                i[2] = 1
                Valid = valid3
    
        #---------------#
        # Criterion (4) #
        #---------------#
        
        valid4 = True
        if (np.abs(TTM1X_shift) > 1000*10**(-6) or np.abs(TTM1Y_shift) > 1000*10**(-6)):
            valid4= False
        if (np.abs(TTM2X_shift) > 500*10**(-6) or np.abs(TTM2Y_shift) > 500*10**(-6)):
            valid4= False
        
        if (not valid4 and not bool_slicer):
            i[3] = 1
            Valid = valid4
    
        return Valid,i

    def _timestamps_to_frames(self, act_times):
        """
        Description
        -----------
        This function takes a list of redis unix timestamps (ms), returned by _get_actuator_pos, converts
        it to a list of IDs and creates a Frame object from those IDs.
        This Frame object contains all camera frames whose timestamps fall within the time window
        throughout which the sampled actuator motion was carried out.
        Note1: Timestamping of actuator positions and IR camera frames (and thus photometric readouts)
               is performed by the same clock, the one of the redis database. This largely removes the need for any empirical time delay correction.
        Note2: A small nuance on time synchronization of actuator positions and IR camera frames.
               The timestamps - associated with actuator positions - are determined by querying the timestamp of
               the last-recorded redis entry (and therefore camera frame, as frame recording & redis writing are intertwined, see scify.py).
               The actuator position timestamp is therefore the time of the last frame that finished exposing.
               For low camera sample rates and large actuator speeds, this could induce a large mismatch in the link between
               actuator positions and IR camera frames.
               The actuator speeds in the spiral methods are determined with this in mind;
               given the camera sample rate, the actuator speed is taken such that this temporal mismatch
               does not induce a positional mismatch larger than an imposed threshold.

        Parameters
        ----------
        act_times : list of int (ms)
                Redis unix timestamps at which the actuator positions were sampled.

        Returns
        -------
        frames : object of the Frame class
                The IR camera frames that were acquired during the window of actuator motion.
                Passed to get_frames_cal(_broad) later for retrieval of associated photometric output fluxes.
        """
        # Temporal window of actuator motion
        t_start = act_times[0]
        t_end = act_times[-1]
        # Fetch recorded redis stamps (unix, ms) in the window
        pairs = get_field("cam_integtime", t_start, t_end, False)
        unix_stamps = pairs[:,0]
        integtimes = pairs[:,1]
        # Convert unix stamps to frame IDs and construct Frame object
        ids = [datetime_to_id(unix_to_datetime(stamp)) for stamp in unix_stamps]
        frames = Frame(ids, integtimes)
        return frames

    def _move_abs_ttm_act(self,init_pos,disp,speeds,pos_offset,config,sample=False,err_prev=np.zeros(4,dtype=np.float64)): 
        """
        Description
        -----------
        The function moves all actuators (1,2,3,4) in a configuration "config" (=beam), initially at positions "init_pos",
        by given displacements "disp", at speeds "speeds", taking into account offsets "pos_offset".
        Actuator positions are sampled during the motion and the associated redis timestamps are registered.
        If "sample" is True, those redis timestamps are used - after the actuator motion - to fetch the IR camera frames that were
        recorded during the time window of actuator motion.
        Those IR camera frames can then be passed to the human_interface calibration methods (get_frames_cal(_broad)) to get photometric readouts.
        In the context of spiraling, actuator errors "err_prev" of the previous step can be taken into account.
        Actuator naming convention within a configuration : 
            1 : TTM1 actuator that is closest to the bench edge
            2 : TTM1 actuator that is furthest from the bench edge
            3 : TTM2 actuator whose motion is in the XZ plane, thus inducing TTM2 Y angles.
            4 : TTM2 actuator whose motion is in the YZ plane, thus inducing TTM2 X angles.
    
        Parameters
        ----------
        init_pos : (1,4) numpy array of float values (mm)
            Positions from which the actuators should be moved.
        disp : (1,4) numpy array of float values (mm)
            Displacements by which the actuators should be moved.
        speeds : (1,4) numpy array of float values (mm/s)
            Speeds by which the actuators should move.
        pos_offset : (1,4) numpy array of float values (mm)
            offsets to be accounted for when moving (deduced empirically)
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3).
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference).     
        sample : single boolean
            If True, the function returns IR camera frames - recorded in the time window of actuator motion - as a Frame object
        err_prev : list of float values (mm)
            Errors made upon a previous spiral step, to be carried over to the next one for purpose of accuracy.
            
        Returns
        -------
        t_start_loop : single integer value (ms)
            Redis time at which the movements started.
        t_spent_loop : single integer value (ms)
            Time spent for moving all four actuators.
        act : list of (4,1) numpy arrays (mm)
            Actuator positions, for the specified config, sampled throughout the actuator motion.
        act_times : list of int (ms)
            Redis timestamps corresponding to each sample of actuator positions.
        frames : Frame object / None
            IR camera frames that were recorded during the actuator motion window (if sample=True)
            None (if sample = False)
        err : (4,1) numpy array of floats (mm)
            Actuator errors made upon actuator motions. Positive values indicate overshoot.

        """
        
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")

        # Actuator names 
        act_names = ['NTTA'+str(config+1),'NTPA'+str(config+1),'NTTB'+str(config+1),'NTPB'+str(config+1)]
        
        # Desired final positions
        final_pos = init_pos + (disp)#-err_prev) #TBD
        
        # Containers for samples of actuator position and positional errors
        act = []
        act_times = []
        err = np.zeros(4,dtype=np.float64)

        # Auxiliary functions
        def _wait_for_arrival(act_idx):
            # Poll until the actuator report a STANDING/OPERATIONAL state.
            on_destination = False
            while not on_destination:
                time.sleep(0.005)
                status, state, _ = self.actuators[config][act_idx].getStatusInformation()
                on_destination = (status == "STANDING" and state == "OPERATIONAL")
            
        def _fire_move(act_idx, target_pos, speed):
            # Fire a MoveAbsolute command through OPCUA
            self.actuators[config][act_idx].command_move_absolute(target_pos, speed).execute()
            
        # Move functions
        def move_single(double):
            """
            Execute one move on an actuator and sample positions throughout that move.
            
            Parameters
            ----------
            double : single boolean
                True : this function is called as the first step a double actuator motion, overshooting the target position.
                        sample positions until target position is passed; don't sample in overshoot phase
                False : this function is called as a standalone, single move
                        sample positions until arrival at target position
            """
            # Execute move
            _fire_move(i, final_pos_off[i], speeds[i])
            # Poll
            on_destination = False
            sample_double = True
            while not on_destination:
                # If double motion, evaluate whether to sample first
                if double:
                    act_pos = self._get_actuator_pos(config)[0]
                    if disp[i] > 0:
                        sample_double = (act_pos[i] < final_pos[i])
                    else:
                        sample_double = (act_pos[i] > final_pos[i])
                # Sample
                if sample_double:
                    act_samp = self._get_actuator_pos(config)
                    act.append(act_samp[0])
                    act_times.append(act_samp[1])

                status, state, _ = self.actuators[config][i].getStatusInformation()
                on_destination = (status == "STANDING" and state == "OPERATIONAL")

            # Arrived at destination
            ach_pos = self._get_actuator_pos(config)[0][i]
            if not double:
                err[i] = ach_pos - final_pos[i]
                print("Moved actuator "+act_names[i]+" by a displacement "+str(disp[i]*1000)+ " um with an error "+ str(1000*(ach_pos-final_pos[i]))+" um. This required an offset-incorporated displacement of "+ str(1000*disp_off)+" um.")

        def move_double():
            """
            Sequence of three separate moves for displacements that are sub-actuator-resolution
                1) Overshoot the target. Sampling happens during this phase, as long as target is not overshot
                2) Neutralize backlash by retracing 0.5 um
                3) Accurate approach to final position 
            """
            
            # 1) Move 1 : Deliberately overshooting and sampling until the target is overshot
            move_single(True)

            # 2) Move 2 : Neutralize backlash
            # Current actuator positions
            act_curr_temp = self._get_actuator_pos(config)[0]
            # Backlash-neutralized position
            disp_back = sign*0.0005
            pos_back = act_curr_temp[i] + disp_back
            # Fire move and await completion
            _fire_move(i, pos_back, 0.0005)
            _wait_for_arrival(i)
            
            # 2.5) Update the offset required to reach the final position
            # Current actuator positions
            act_curr_temp = self._get_actuator_pos(config)[0]
            # Necessary displacements
            act_disp_temp = final_pos - act_curr_temp
            # Update speed
            speeds[i] = speed_double
            # Offsets from accuracy grid
            pos_offset_return = self._actoffset(speeds, act_disp_temp)
            # Final target position
            final_pos_off[i] = final_pos[i] - pos_offset_return[i]
            
            # 3) Move 3 : Returning to get to the desired position in accurate fashion.
            # Fire move and await completion
            _fire_move(i, final_pos_off[i], speeds[i])
            _wait_for_arrival(i)
            # Evaluate error              
            ach_pos = self._get_actuator_pos(config)[0][i]
            err[i] = ach_pos-final_pos[i]
            print("Moved actuator "+act_names[i]+" by a displacement "+str(disp[i]*1000)+ " um with an error "+ str(1000*(ach_pos-final_pos[i]))+" um. This required an offset-incorporated displacement of "+ str(1000*disp_off)+" um.")

        #---------------------
        # MAIN ACTUATOR LOOP
        # Looping over all four actuators
        t_start_loop = self.ts.ts.get("cam_integtime")[0]
        for i in range(0,4):
            # Only continue for actuators upon which displacement is imposed
            if (disp[i] != 0):
                # Incorporating offsets
                final_pos_off = final_pos.copy()
                final_pos_off[i] -= pos_offset[i] # in mm
                # Actual displacement (offset incorporated)
                disp_off = final_pos_off[i]-init_pos[i]
                
                if (np.abs(disp[i]) >= disp_double):
                    # 1) Single motion suffices
                    move_single(False)
                else:
                    # 2) Double motion necessary
                    sign = np.sign(disp[i])
                    # Deliberately overshooting
                    step_over = step_double 
                    speeds[i] = speed_double 
                    final_pos_off[i] = init_pos[i] + sign*step_over
                    move_double()
        
        t_end_loop = self.ts.ts.get("cam_integtime")[0]
        t_spent_loop = round(t_end_loop-t_start_loop)

        # Retrospectively acquire the frames recorded during the motion time window
        if (sample and len(act_times) > 0):
            frames = self._timestamps_to_frames(act_times)
        else:
            frames = None

        return t_start_loop,t_spent_loop,act,act_times,frames,err

    #-----------------#
    # Individual Step #
    #-----------------#

    def individual_step(self,bool_slicer,sky,steps,speeds,config,sample,err_prev=np.zeros(4,dtype=np.float64)): 
        """
        Description
        -----------
        The function carries out a desired step in NOTT beam configuration "config". The following steps are taken:
            (1) The current actuator positions are registered.
            (2) The current actuator positions are translated into the corresponding current TTM angular configuration.
            (3) The current TTM angular configuration is linked to the nearest point in the Zemax-simulated grid. The corresponding distances (D1,...,D8) are retrieved.
            (4) The framework is used to evaluate the necessary TTM offsets for the user-defined purpose.
            (5) The actuator displacements, necessary to achieve the TTM offsets, are calculated.
            (6) The necessary actuator movements are imposed to the bench via OPC UA.

        If sample = True, the function returns a Frame object containing IR camera frames that are recorded during the time window of motion.
        These frames are timestamped by the same clock (redis database clock) as the actuator positions.

        Parameters
        ----------
        bool_slicer : single boolean
            True : individual_step is called by a method that displaces the beam off the slicer (localization spiral).
            False : individual_step is called by a method that should not displace the beam off the slicer (optimization spiral).
        sky : single integer
            sky == 0 : User specifies desired (dX,dY,dx,dy) shifts in the CS(X,Y) and IM(x,y) plane.
            sky == 1 : User specifies on-sky angular shifts (dskyX,dskyY) and wishes for TTM1 to facilitate this on-sky shift while keeping the CS position fixed.
            sky == -1 : User specifies on-sky angular shifts (dskyX,dskyY) and wishes for TTM1 to facilitate this on-sky shift while keeping the IM position fixed. 
        steps : (1,4) numpy array of float values 
            sky == 0 : steps = (dX,dY,dx,dy). (mm)
            sky != 0 : steps = (dskyX,dskyY,0,0). (rad)
        speeds : (1,4) numpy array of float values (mm/s)
            Speeds by which the actuators (1,2,3,4) will move.
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3).
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference).
        sample : single boolean
            Whether to sample photometric ROI averages throughout the motion.
        err_prev : numpy array of float values (mm)
            Actuator errors made upon a previous spiral step, to be carried over to the next one for purpose of accuracy.
        
        Returns
        -------
        t_start : single integer (ms)
            Redis time at which the actuator motions commenced.
        t_spent : single integer (ms)
            Time spent for moving all four actuators.
        act : list of (4,1) numpy arrays (mm)
            Actuator positions, for the specified config, sampled throughout the actuator motion.
        act_times : list of int (ms)
            Redis timestamps corresponding to each sample of actuator positions.
        frames : Frame object / None
            IR camera frames that were recorded during the actuator motion window (if sample=True)
            None (if sample = False)
        err : List of floats (mm)
            Errors made upon actuator motions. Positive values indicate overshoot.
        act_disp : numpy array of floats (mm)
            Actuator displacements imposed by the step.

        """
        
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
    
        # Register current actuator positions
        act_curr = self._get_actuator_pos(config)[0]
        
        # Translate to current TTM angular configuration
        TTM_curr = self._actuator_position_to_ttm_angle(act_curr,config)

        # Couple the configuration to the nearest grid point & retrieve the Zemax-simulated distances
        D_arr = self._snap_distance_grid(TTM_curr, config)
        
        # Numerically evaluate framework
        if (sky != 0):
            TTM_angles = self._sky_to_ttm(np.array([steps[0],steps[1],0,0],dtype=np.float64))
            dTTM1X = TTM_angles[0]
            dTTM1Y = TTM_angles[1]
            CSbool = (sky==1)
            TTM_offsets,shifts_par = self._framework_numeric_sky(dTTM1X,dTTM1Y,D_arr,1,CSbool) 
            #print("Step : (dX,dY,dx,dy) = ",shifts_par)
        else:
            TTM_offsets = self._framework_numeric_int(steps,D_arr,1) # Current Dgrid only supports central wavelength
            #print("Step :  (dX,dY,dx,dy) = ",steps)
        
        # Calculating the necessary actuator displacements
        act_disp = self._ttm_shift_to_actuator_displacement(TTM_curr,TTM_offsets,config)
        
        # Offsets from accuracy grid
        pos_offset = self._actoffset(speeds,act_disp) 
        
        # Final TTM configuration
        TTM_final = TTM_curr + TTM_offsets
    
        # Before imposing the displacements to the actuators, the state validity is checked.
        valid,cond = self._valid_state(bool_slicer,TTM_final,act_disp-pos_offset,act_curr,config)
        if not valid:
            raise ValueError("The requested change does not yield a valid configuration. Out of conditions (1,2,3,4) the ones in following array indicate what conditions were violated : "+str(cond)+
                             "\n Conditions :\n (1) The final configuration would displace the beam off the slicer."+
                             "\n (2) The requested angular TTM offset is lower than what is achievable by the TTM resolution."+
                             "\n (3) The requested final TTM configuration is beyond the limits of what the actuator travel ranges can achieve."+
                             "\n (4) The requested final TTM configuration is beyond the current range supported by Dgrid (pm 1000 microrad for TTM1, pm 500 microrad for TTM2).")
                
        # Only push actuator motion if it would yield a valid state
        t_start,t_spent,act,act_times,frames,err = self._move_abs_ttm_act(act_curr,act_disp,speeds,pos_offset,config,sample,err_prev) 
        
        return t_start,t_spent,act,act_times,frames,err,act_disp
    
    #----------#
    # Scanning #
    #----------#    

    def localization_spiral(self,sky,step,speed,config,dt_base=0.5):
        """
        Description
        -----------
        The function traces a square spiral in the user-specified plane (either image or on-sky plane) to locate the internal beam / on-sky source.
        The spiral stops once a co-added frame, sampled throughout the last step, exceeds "SNR_inj" sigma's above the pre-spiral baseline broadband photometric output flux.
        The global SNR maximum - across all samples throughout the step - is then determined and the bench is pushed to the associated sampled actuator positions.

        Sampling specifics:        
        With each step, pairs of actuator positions and redis timestamps are sampled (move_abs_ttm_act).
        The sequence of frames - recorded within the time window of the step's motion - is fetched (_timestamps_to_frames).
        The resulting Frame object is used to obtain frame-per-frame broadband flux (human_interface.get_frames_cal_broad).

        For internal alignment, the stepsize is fixed to 20 um (waveguide diameter) and "step" is a dummy parameter.

        A maximum value for the actuator speed is derived from the camera frame rate and a chosen tolerance on the positional mismatch of
        associated (via redis timestamps) and truly synchronous actuator positions related to a camera frame.
        This upper boundary is meant to guarantee that the beam moves no more than a distance "tolerance" per camera frame.
        (! see Note2 in _timestamp_to_frames for reference.)
        
        For on-sky spiralling, a time out is incorporated. Once the spiral arm reaches a dimension of Nstep_sky*step, the spiralling procedure is quit.
        The purpose of this time out is to not allow for endless spiralling in an on-sky region that is nowhere near a source.
        
        Parameters
        ----------
        sky : single boolean
            If True : spiral by given dimension on-sky
            If False : spiral by given dimension in image plane
        step : single float value 
            The dimension by which the spiral should make its steps.
            If sky == True : on-sky angular step (radian) 
                            Note : It is recommended to take the apparent on-sky angular radius of the source as step.
            If sky == False : image plane step (mm)
                            Note : Dummy parameter, 20 micron (waveguide dimension) is taken by default.
        speed : single float value (mm/s)
            Actuator speed by which a spiral step should occur
            Note: Parameter to be removed once an optimal speed is recovered (which balances efficiency and accuracy)
            Note2: bound by upper_speed, derived from positional mismatch tolerance
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3).
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference).
        dt_base : single float (s)
            Time window span across which a baseline photometry measurement is made before spiraling.
            
        Returns
        -------
        None.
        
        """
        sky = int(bool(sky))
        
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
        if (speed <= 0):
            raise ValueError("Given actuator speed cannot be negative.")
        
        if sky : 
            d = step
        else:
            d = 20*10**(-3) #(mm)

        # Upper boundary for actuator speed, based on camera frame rate and positional tolerance
        #---------------------------------------------------------------------------------------
        # Tolerance (half of waveguide diameter)
        tol_loc = 10**(-3) # mm
        # Estimating camera frame rate from a sequence of redis timestamps
        pairs = get_field("cam_integtime", self.ts.ts.get("cam_integtime")[0]-5000, self.ts.ts.get("cam_integtime")[0], False)
        frame_period = 10**(-3) * np.median(np.diff(pairs[:,0])) # seconds
        # Cropping upper speed boundary to TwinCat boundary (30 um/s)
        upper_speed = min(tol_loc / frame_period, 30*10**(-3))
        # Cropping user input speed 
        spd = min(speed, upper_speed)

        # Baseline photometric broadband flux measurement
        # -----------------------------------------------
        photo_init, noise = self._get_photo_broad(dt_base, config)
        print(f"Baseline flux: {photo_init:.4f} with noise: {noise:.4f}")

        if photo_init > fac_loc * noise:
            raise Exception("Localization spiral not started. Initial configuration is likely already in a state of injection.")
        
        print("----------------------------------")
        print(f"Spiraling for localization at actuator speed {spd} mm/s ...")
        print("----------------------------------")

        # Visualization # TBD
        # -------------------
        # Container for average SNR values (for spiraling plot)
        dim = 11
        SNR_av = -10*np.ones((dim,dim))
        # Appending initial exposure - defined to be zero - at initial indices k,l (indplot = [k,l])
        indplot = np.array([dim//2,dim//2])
        SNR_av[indplot[0]][indplot[1]] = 0
    
        # Initializing Plot
        fig = plt.figure(figsize=(10,10))
        ax = fig.add_subplot(111)
        img = ax.imshow(SNR_av)
        # Set limits
        img.set_clim(vmin=-10, vmax=10)
        # Set tick labels
        xticks = np.linspace(0,dim-1,dim)
        yticks = np.linspace(0,dim-1,dim)
        labels = np.arange(-20*(dim//2),20*(dim//2+1),20)
        ax.axes.get_xaxis().set_ticks(xticks)
        ax.axes.get_yaxis().set_ticks(yticks)
        ax.set_xticklabels(labels)
        ax.set_yticklabels(-labels)
        # Plotting initial SNR improvement value (=0) as label
        ax.text(indplot[1],indplot[0],np.round(SNR_av[indplot[0]][indplot[1]],2),ha='center',va='center',fontsize=14)
        # Title
        fig.suptitle("Localization spiral", fontsize=24)
        # Showing
        fig.canvas.draw()
        fig.canvas.flush_events()
        
        def _update_plot(indplotpar,val):    
            # Changing the indices according to recent spiral step
            indplot_change = np.array([[-1,0],[0,-1],[+1,0],[0,1]])
            indplotpar += indplot_change[move]
            # Storing average SNR improvement in container
            SNR_av[indplotpar[0]][indplotpar[1]] = val
            # Updating spiraling plot
            img.set_data(SNR_av)
            # Updating plot
            ax.text(indplotpar[1],indplotpar[0],np.round(SNR_av[indplotpar[0]][indplotpar[1]],2),ha='center',va='center',fontsize=14)
            fig.canvas.draw()
            fig.canvas.flush_events()
            plt.pause(0.0001)
            
            return indplotpar
                   
        #           x---x---x---x
        #           |           |
        #           x   x---x   x
        ##########  |   |   |   |
        # Spiral #  x   x   x   x
        ##########  |   |       |
        #           x   x---x---x
        #           |
        #           x---x---...    
    
        # Possible moves
        if sky:
            up=np.array([0,d,0,0],dtype=np.float64)
            left=np.array([-d,0,0,0],dtype=np.float64)
            down=np.array([0,-d,0,0],dtype=np.float64)
            right=np.array([d,0,0,0],dtype=np.float64)
            moves = np.array([up,left,down,right])
        else:
            up=np.array([0,0,0,d],dtype=np.float64)
            left=np.array([0,0,-d,0],dtype=np.float64)
            down=np.array([0,0,0,-d],dtype=np.float64)
            right=np.array([0,0,d,0],dtype=np.float64)
            moves = np.array([up,left,down,right])
    
        # Stop criterion
        stop = False
        # What move is next (index in moves array)?
        move = 0 
        # How many times has the move type switched?
        Nswitch = 0
        # How much consequent moves are being made in a direction at the moment?
        Nsteps = 1
        
        # Containers for actuator positions and paired broadband flux values
        ACT = []
        ACT_flux = []
        
        while not stop:
        
            # Initializing err_prev
            err_prev = np.zeros(4,dtype=np.float64)  
        
            # Carrying out step(s)
            for i in range(0,Nsteps):
                # Step
                speeds = np.full(4, spd, dtype=np.float64)
                _,_,acts,act_times,frames,err,_ = self.individual_step(True,sky,moves[move],speeds,config,True,err_prev) 
                # Saving errors for next step
                err_prev = np.array(err,dtype=np.float64)

                # Evaluate photometric readout over motion time window
                if (frames is not None and len(acts) > 0):
                    # Fetching individual frames for linking to actuator positions
                    _,_,flux_seq,_ = self.humint.get_frames_cal_broad(frames=frames, sequence=True)
                    flux_step = flux_seq[:, self.photo_idx[config]]
                    # Fetching co-added frames for injection detection
                    # How much frames amount to {acq_time} seconds
                    n_frames = int(acq_time // frame_period)
                    # How much bins do we thus need
                    n_bins = len(flux_seq) // n_frames
                    # Floor to min 1 bin
                    n_part = max(n_bins, 1)
                    children_frames = frames.partition(n_part)
                    flux_bin = np.array(self.humint.get_frames_cal_broad(frames=child, sequence=False)[2][self.photo_idx[config]] for child in children_frames])
                else:
                    flux_step = np.array([photo_init])
                    flux_bin = np.array([photo_init])
                snr_step = (flux_step - photo_init) / noise
                snr_bin = (flux_bin - photo_init) / noise

                # Pair each actuator position set to the nearest camera frame
                n_act, n_frame = len(acts), len(flux_step)
                for j in range(0, n_act):
                    # calculate the proportional index in the photometric readout array
                    k = int(round(j * (n_frame-1) / max(n_act-1, 1)))
                    k = min(k, n_frame-1)
                    ACT.append(acts[j])
                    ACT_flux.append(flux_step[k])

                # Injection criterion
                if (snr_bin > SNR_inj).any():
                    print("Injecting state found!")
                    print(f"Mean SNR of co-added frames ({acq_time} s each) that are above imposed threshold {SNR_inj}: {np.mean(snr_bin[snr_bin > SNR_inj]):.2f}")

                    indplot = _update_plot(indplot, float(np.max(snr_bin)))

                    # Push bench to global flux maximum, sampled across the spiral
                    ACT_flux_arr = np.array(ACT_flux, dtype=np.float64)
                    i_max = np.argmax(ACT_flux_arr)
                    ACT_final = ACT[i_max]
                    act_curr = self._get_actuator_pos(config)[0]
                    act_disp = ACT_final - act_curr
                    spd_push = np.full(4, speed_double, dtype=np.float64)
                    pos_off = self._actoffset(spd_push, act_disp)
                    print(f"Bringing bench to injecting actuator positions at {act_curr+act_disp} mm")
                    self._move_abs_ttm_act(act_curr, act_disp, spd_push, pos_off, config, sample=False)
                    plt.close(fig)
                    return 

                indplot = _update_plot(indplot, float(np.mean(snr_bin)))
                # Refresh photometric baseline with each step (countering camera drift)
                photo_init, noise = self._get_photo_broad(dt_base, config)
                
            # Setting up next move
            move = (move+1) % 4
            # Counting the amount of performed move type switches
            Nswitch += 1
            if (Nswitch % 2 == 0):
                Nsteps += 1
            
            # Implementing boundary stop condition for on-sky spiralling
            if (sky and Nsteps >= Nsteps_skyb):
                raise TimeoutError("The on-sky spiral scanning algorithm timed out. Consider repointing closer to source.")
         
        plt.close(fig)
        return

    def optimization_spiral(self,sky,step,speed,config,dt_sample):
        """
        Description
        -----------
        The function traces a square spiral in the user-specified plane (either image or on-sky plane).
        The spiral is stopped once it has covered an area that is two steps wide in each direction (up,down,left,right).
        Along the spiral, corresponding actuator configurations and camera averages are retrieved via opcua and stored.
        The actuator configuration, throughout the spiral, that reached maximal injection is pushed to the bench.
        
        Parameters
        ----------
        sky : single boolean
            If True : spiral on-sky.
            If False : spiral in image plane.
        step : single float value (mm)
            The dimension by which the spiral should make its steps.
            If sky == True : on-sky angular step (radian) 
            If sky == False : dummy parameter, 5 micron is taken by default.
        speed : single float value (mm/s)
            Actuator speed by which a spiral step should occur.
            Note: Parameter to be removed once optimal speed is obtained.
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3).
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference).
        dt_sample : single float (s)
            Amount of time a sample should span.

        Remarks
        -------
        The function is expected to be called after the "localization_spiral" function has been called. It is thus expected that a first, broad-scope alignment has already been performed.
        If sky == True : Before calling this function, it is expected that the TTMs have already been aligned such that the on-sky source is imaged onto the chip input.
        If sky == False : Before calling this function, it is expected that the TTMs have already been aligned such that the internal VLTI beam is injected into the chip input.

        Returns
        -------
        None.

        """
        print("----------------------------------")
        print("Spiraling for optimization...")
        print("----------------------------------")
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
        
        #if (speed > 1.22*10**(-3) or speed <= 0):
        #    raise ValueError("Given actuator speed is beyond the accepted range (0,1.22] um/s")
        
        d = step
        
        # Actuator configs and times
        ACT = []
        ACT_times = []
        
        # Delay time (total delay minus writing time)
        t_delay = self._get_delay(100,True)-t_write
        # Exposure time for first exposure (ms)
        dt_exp_opt = 200
        # Start time for initial exposure
        t_start = self._get_time(1000*time.time(),t_delay)
        # Sleep
        time.sleep((dt_exp_opt+t_write)*10**(-3))
        # Initial position noise measurement
        _,noise = self._get_noise(Nexp,t_start,dt_exp_opt)
        # Initial position photometric output measurement
        photo_init = self._get_photo(Nexp,t_start,dt_exp_opt,config)
        # Storing initial actuator configuration and timestamp.
        act_curr = self._get_actuator_pos(config)[0]
        ACT.append(act_curr)
        ACT_times.append(self._get_time(1000*time.time(),t_delay))
    
        # Container for average SNR values (for spiraling plot)
        dim = 7
        SNR_max = -10*np.ones((dim,dim))
        # Appending initial exposure - defined to be zero - at initial indices k,l (indplot = [k,l])
        indplot = np.array([dim//2,dim//2])
        SNR_max[indplot[0]][indplot[1]] = 0
    
        # Initializing Plot
        fig = plt.figure(figsize=(10,10))
        ax = fig.add_subplot(111)
        img = ax.imshow(SNR_max)
        # Set limits
        img.set_clim(vmin=-50, vmax=50)
        # Set tick labels
        xticks = np.linspace(0,dim-1,dim)
        yticks = np.linspace(0,dim-1,dim)
        labels = np.arange(-1000*d*(dim//2),1000*d*(dim//2+1),1000*d)
        ax.axes.get_xaxis().set_ticks(xticks)
        ax.axes.get_yaxis().set_ticks(yticks)
        ax.set_xticklabels(labels)
        ax.set_yticklabels(-labels)
        # Plotting initial SNR improvement value (=0) as label
        ax.text(indplot[1],indplot[0],np.round(SNR_max[indplot[0]][indplot[1]],2),ha='center',va='center',fontsize=14)
        # Title
        fig.suptitle("Optimization spiral", fontsize=24)
        # Showing
        fig.canvas.draw()
        fig.canvas.flush_events()
    
        def _update_plot(indplotpar,val):
            
            # Changing the indices according to recent spiral step
            indplot_change = np.array([[-1,0],[0,-1],[1,0],[0,1]])
            indplotpar += indplot_change[move]
            # Storing average SNR improvement in container
            SNR_max[indplotpar[0]][indplotpar[1]] = val
            # Updating spiraling plot
            img.set_data(SNR_max)
            # Updating plot
            ax.text(indplotpar[1],indplotpar[0],np.round(SNR_max[indplotpar[0]][indplotpar[1]],2),ha='center',va='center',fontsize=14)
            fig.canvas.draw()
            fig.canvas.flush_events()
            plt.pause(0.0001)
            
            return indplotpar
    
        #            x---x   x
        ##########   |   |   |
        # Spiral #   x   x   x
        ##########   |       |
        #            x---x---x
        
        # Possible moves
        if sky:
            up=np.array([0,d,0,0],dtype=np.float64)
            left=np.array([-d,0,0,0],dtype=np.float64)
            down=np.array([0,-d,0,0],dtype=np.float64)
            right=np.array([d,0,0,0],dtype=np.float64)
            moves = np.array([up,left,down,right])
        else:
            up=np.array([0,0,0,d],dtype=np.float64)
            left=np.array([0,0,-d,0],dtype=np.float64)
            down=np.array([0,0,0,-d],dtype=np.float64)
            right=np.array([0,0,d,0],dtype=np.float64)
            moves = np.array([up,left,down,right])
    
        # Stop criterion
        stop = False
        # What move is next (index in moves array)?
        move = 0 
        # How many times has the move type switched?
        Nswitch = 0
        # How much consequent moves are being made in a direction at the moment?
        Nsteps = 1

        while not stop:
        
            # Initializing err_prev
            err_prev = np.zeros(4,dtype=np.float64)     
            # Initializing act_disp_prev
            act_disp_prev = np.zeros(4,dtype=np.float64)
        
            # Carrying out step(s)
            for i in range(0,Nsteps):
                # Step
                speeds = np.array([speed,speed,speed,speed], dtype=np.float64) # TBD
                _,_,acts,act_times,rois,err,act_disp = self.individual_step(True,sky,moves[move],speeds,config,True,dt_sample,t_delay,err_prev,act_disp_prev)
                # Saving error for next step.
                err_prev = np.array(err,dtype=np.float64)
                # Saving actuator steps for next step.
                act_disp_prev = act_disp
                # Saving actuator configurations and timestamps sampled throughout step.
                for j in range(0, len(acts)):
                    ACT.append(acts[j])
                    ACT_times.append(act_times[j])
                # Updating plot
                indplot = _update_plot(indplot, np.max((rois-photo_init)/noise))
        
            # Setting up next move
            if move < 3:
                move += 1
            else:
                move = 0
            
            # Stop condition
            if (Nsteps == 3):
                stop = True
            
            # Counting the amount of performed move type switches
            Nswitch += 1
        
            if (Nswitch % 2 == 0):
                Nsteps += 1
    
        # Safety sleep
        time.sleep(10*t_write*10**(-3)) # TBD
        # Find optimal injection found along spiral (performed once more, post-movement, to eliminate possible time sync issues during sampling)
        # Re-reading the photometric outputs (timeframe of dt_sample around each actuator timestamp)
        SNR_samples = np.array([self._get_photo(Nexp,round(timestamp-(1000*dt_sample/2)),round(1000*dt_sample),config)-photo_init for timestamp in ACT_times] / noise,dtype=np.float64)
        # Finding optimal injection index
        i_max = np.argmax(SNR_samples)
        # Corresponding actuator positions
        ACT_final = ACT[i_max]
        # Current configuration
        act_curr = self._get_actuator_pos(config)[0]
        # Necessary displacements
        act_disp = ACT_final-act_curr
        #speeds = np.array(np.abs(act_disp/100),dtype=np.float64)
        speeds = np.array([0.0011,0.0011,0.0011,0.0011],dtype=np.float64) #TBD
        pos_offset = self._actoffset(speeds,act_disp) 
        print("Bringing to optimized actuator position : ", np.max(SNR_samples), "SNR improvement at ", act_curr+act_disp, " mm.")
        # Push bench to configuration of optimal found injection.
        _,_,_,_,_,_ = self._move_abs_ttm_act(act_curr,act_disp,speeds,pos_offset,config,False,0.010,self._get_delay(100,True)-t_write)
         
        plt.close(fig)
        return
    
    def optimization_spiral_gradient(self,sky,step,speed,config,dt_sample,SNR_opt=5):
        """
        Description
        -----------
        The function traces a square spiral in the user-specified plane (either image or on-sky plane).
        Throughout each step along the spiral, corresponding actuator configurations and camera averages are retrieved via opcua and stored.
        If a single sample along a step shows an improvement in SNR, compared to the pre-spiral photometric output, that is larger than SNR_opt, the spiral is stopped.
        The actuator configuration corresponding to this sample is then pushed to the bench.
        
        Parameters
        ----------
        sky : single boolean
            If True : spiral on-sky.
            If False : spiral in image plane.
        step : single float value (mm)
            The dimension by which the spiral should make its steps.
            If sky == True : on-sky angular step (radian) 
            If sky == False : dummy parameter, 5 micron is taken by default.
        speed : single float value (mm/s)
            Actuator speed by which a spiral step should occur.
            Note: Parameter to be removed once optimal speed is obtained.
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3).
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference).
        dt_sample : single float (s)
            Amount of time a sample should span.

        Remarks
        -------
        The function is expected to be called after the "localization_spiral" function has been called. It is thus expected that a first, broad-scope alignment has already been performed.
        If sky == True : Before calling this function, it is expected that the TTMs have already been aligned such that the on-sky source is imaged onto the chip input.
        If sky == False : Before calling this function, it is expected that the TTMs have already been aligned such that the internal VLTI beam is injected into the chip input.

        Returns
        -------
        None.

        """
        print("----------------------------------")
        print("Spiraling for optimization...")
        print("----------------------------------")
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
        
        #if (speed > 1.22*10**(-3) or speed <= 0):
        #    raise ValueError("Given actuator speed is beyond the accepted range (0,1.22] um/s")
        
        d = step
        
        # Actuator configs and times
        ACT = []
        ACT_times = []
        
        # Delay time (total delay minus writing time)
        t_delay = self._get_delay(100,True)-t_write
        # Exposure time for first exposure (ms)
        dt_exp_opt = 200
        # Start time for initial exposure
        t_start = self._get_time(1000*time.time(),t_delay)
        # Sleep
        time.sleep((dt_exp_opt+t_write)*10**(-3))
        # Initial position noise measurement
        _,noise = self._get_noise(Nexp,t_start,dt_exp_opt)
        # Initial position photometric output measurement
        photo_init = self._get_photo(Nexp,t_start,dt_exp_opt,config)
        # Storing initial actuator configuration and timestamp.
        act_init = self._get_actuator_pos(config)[0]
        ACT.append(act_init)
        ACT_times.append(self._get_time(1000*time.time(),t_delay))
    
        # Container for average SNR values (for spiraling plot)
        dim = 7
        SNR_max = -10*np.ones((dim,dim))
        # Appending initial exposure - defined to be zero - at initial indices k,l (indplot = [k,l])
        indplot = np.array([dim//2,dim//2])
        SNR_max[indplot[0]][indplot[1]] = 0
    
        # Initializing Plot
        fig = plt.figure(figsize=(10,10))
        ax = fig.add_subplot(111)
        img = ax.imshow(SNR_max)
        # Set limits
        img.set_clim(vmin=-50, vmax=50)
        # Set tick labels
        xticks = np.linspace(0,dim-1,dim)
        yticks = np.linspace(0,dim-1,dim)
        labels = np.arange(-1000*d*(dim//2),1000*d*(dim//2+1),1000*d)
        ax.axes.get_xaxis().set_ticks(xticks)
        ax.axes.get_yaxis().set_ticks(yticks)
        ax.set_xticklabels(labels)
        ax.set_yticklabels(-labels)
        # Plotting initial SNR improvement value (=0) as label
        ax.text(indplot[1],indplot[0],np.round(SNR_max[indplot[0]][indplot[1]],2),ha='center',va='center',fontsize=14)
        # Title
        fig.suptitle("Optimization spiral", fontsize=24)
        # Showing
        fig.canvas.draw()
        fig.canvas.flush_events()
    
        def _update_plot(indplotpar,val):
            
            # Changing the indices according to recent spiral step
            indplot_change = np.array([[-1,0],[0,-1],[1,0],[0,1]])
            indplotpar += indplot_change[move]
            # Storing average SNR improvement in container
            SNR_max[indplotpar[0]][indplotpar[1]] = val
            # Updating spiraling plot
            img.set_data(SNR_max)
            # Updating plot
            ax.text(indplotpar[1],indplotpar[0],np.round(SNR_max[indplotpar[0]][indplotpar[1]],2),ha='center',va='center',fontsize=14)
            fig.canvas.draw()
            fig.canvas.flush_events()
            plt.pause(0.0001)
            
            return indplotpar
    
        #            x---x   x
        ##########   |   |   |
        # Spiral #   x   x   x
        ##########   |       |
        #            x---x---x   
        
        # Possible moves
        if sky:
            up=np.array([0,d,0,0],dtype=np.float64)
            left=np.array([-d,0,0,0],dtype=np.float64)
            down=np.array([0,-d,0,0],dtype=np.float64)
            right=np.array([d,0,0,0],dtype=np.float64)
            moves = np.array([up,left,down,right])
        else:
            up=np.array([0,0,0,d],dtype=np.float64)
            left=np.array([0,0,-d,0],dtype=np.float64)
            down=np.array([0,0,0,-d],dtype=np.float64)
            right=np.array([0,0,d,0],dtype=np.float64)
            moves = np.array([up,left,down,right])
    
        # Stop criterion
        stop = False
        # What move is next (index in moves array)?
        move = 0 
        # How many times has the move type switched?
        Nswitch = 0
        # How much consequent moves are being made in a direction at the moment?
        Nsteps = 1

        while not stop:
        
            # Initializing err_prev
            err_prev = np.zeros(4,dtype=np.float64)     
            # Initializing act_disp_prev
            act_disp_prev = np.zeros(4,dtype=np.float64)
        
            # Carrying out step(s)
            for i in range(0,Nsteps):
                # Step
                speeds = np.array([speed,speed,speed,speed], dtype=np.float64) # TBD
                _,_,acts,act_times,rois,err,act_disp = self.individual_step(True,sky,moves[move],speeds,config,True,dt_sample,t_delay,err_prev,act_disp_prev)
                # Saving error for next step.
                err_prev = np.array(err,dtype=np.float64)
                # Saving actuator steps for next step.
                act_disp_prev = act_disp
                
                # Container for sampled ROI exposures
                exps = []
                
                # Storing camera values and actuator configurations
                # 1) Saving photometric readout values (SNR) sampled throughout the step
                for j in range(0, len(rois)):
                    exps.append((rois[j]-photo_init)/noise)
                # 2) Saving actuator configurations and timestamps sampled throughout step.
                for j in range(0, len(acts)):
                    ACT.append(acts[j])
                    ACT_times.append(act_times[j])
                    
                # Check whether a sample along the step exceeds the pre-imposed SNR improvement threshold.
                exps_arr = np.array(exps,dtype=np.float64)
                if ((exps_arr > SNR_opt).any()):
                    print("A sample along the step is above the SNR improvement threshold.")
                    print("")
                    
                    # Update plot
                    indplot = _update_plot(indplot,np.max(exps))
                    
                    # Safety sleep
                    time.sleep(10*t_write*10**(-3)) # TBD
                    # Finding optimal injection index
                    i_max = np.argmax(exps_arr)
                    #print("Index, SNR and actuator configuration of found injecting state :", i_max, SNR_samples[i_max], ACT[i_max])
                    # Corresponding actuator positions
                    ACT_final = ACT[i_max]
                    # Current configuration
                    act_curr = self._get_actuator_pos(config)[0]
                    # Necessary displacements
                    act_disp = ACT_final-act_curr
                    #print("Necessary displacements to bring the bench to injecting state : ", act_disp, " mm.")
                    speeds = np.array([0.0011,0.0011,0.0011,0.0011],dtype=np.float64) #TBD
                    pos_offset = self._actoffset(speeds,act_disp) 
                    print("Bringing to actuator position above SNR improvement threshold : ", act_curr+act_disp, " mm.")
                    # Push bench to configuration of optimal found injection.
                    _,_,_,_,_,_ = self._move_abs_ttm_act(act_curr,act_disp,speeds,pos_offset,config,False,0.010,self._get_delay(100,True)-t_write)            
                    return
                    
                # Updating plot
                indplot = _update_plot(indplot, np.max((rois-photo_init)/noise))
                
                # Reset actuator configs and times
                ACT = []
                ACT_times = []
        
            # Setting up next move
            if move < 3:
                move += 1
            else:
                move = 0
            
            # Stop condition
            if (Nsteps == 3):
                stop = True
            
            # Counting the amount of performed move type switches
            Nswitch += 1
        
            if (Nswitch % 2 == 0):
                Nsteps += 1
            
        # If no sample above the SNR improvement threshold is found, return to initial state.
        # Current configuration
        act_curr = self._get_actuator_pos(config)[0]
        # Necessary displacements
        act_disp = act_init-act_curr
        #print("Necessary displacements to bring the bench to injecting state : ", act_disp, " mm.")
        speeds = np.array([0.0011,0.0011,0.0011,0.0011],dtype=np.float64) #TBD
        pos_offset = self._actoffset(speeds,act_disp) 
        print("No sample above SNR improvement threshold found, returning to pre-spiral state : ", act_curr+act_disp, " mm.")
        # Push bench to configuration of optimal found injection.
        _,_,_,_,_,_ = self._move_abs_ttm_act(act_curr,act_disp,speeds,pos_offset,config,False,0.010,self._get_delay(100,True)-t_write)     
        
        plt.close(fig)
        return
    
    def optimization_cross(self,sky,CS,d,speed=1.1*10**(-3),config=1,dt_base=0.050,k=10,l=5):
        """
        Description
        -----------
        This function brings the beam centroid to a state of optimized injection by shaping a cross in the pupil or image plane, controlled by parameter "CS". 
        Motion is continued in each of the four cartesian directions as long as there is monotonuous improvement in sampled broadband flux.
        The sampled flux values are averaged by a sliding window approach, with size k and stepsize l between subsequent windows.
        When a step no longer shows monotonuous improvement, the bench is pushed back to the actuator configuration - sampled along the step - that yielded the maximum flux along all steps in the ongoing direction.

        For sampling specifics: see localization_spiral documentation

        Actuator speed is cropped to an upper boundary, calculated by a positional tolerance. For specifics, see localization_spiral documentation.
        
        Parameters
        ----------
        sky : single boolean
            If True : trace a cross on-sky.
            If False : trace a cross internally.
        CS : single boolean
            If True, the CS position is kept fixed throughout the cross motion, which is then traced in the image plane.
            If False, the IM position is kept fixed throughout the cross motion, which is then traced in the pupil plane.
        d : single float value 
            The dimension by which the cross should make its steps.
            If sky : on-sky angular stepsize (rad)
            else : displacement stepsize in CS/IM plane (mm)
        speed : single float value (mm/s)
            Actuator speed by which a step should occur.
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3).
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference).
        dt_base : single float (s)
            Timespan of window for baseline photometric output measurement
        k : single integer
            Window size for flux sample averaging
        l : single integer
            Step size between consecutive windows
            
        Remarks
        -------
        The function is expected to be called after the "localization_spiral" function has been called. It is thus expected that a first, broad-scope alignment has already been performed.
        If sky == True : Before calling this function, it is expected that the TTMs have already been aligned such that the on-sky source is imaged onto the chip input.
        If sky == False : Before calling this function, it is expected that the TTMs have already been aligned such that the internal VLTI beam is injected into the chip input.

        Returns
        -------
        None.

        """
        print("----------------------------------")
        print("Optimizing by cross-motion...")
        print("----------------------------------")
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
        
        # Upper boundary for actuator speed, based on camera frame rate and positional tolerance
        #---------------------------------------------------------------------------------------
        # Tolerance
        tol_opt = 0.5*10**(-3) # mm
        # Estimating camera frame rate from a sequence of redis timestamps
        pairs = get_field("cam_integtime", self.ts.ts.get("cam_integtime")[0]-5000, self.ts.ts.get("cam_integtime")[0], False)
        frame_period = 10**(-3) * np.median(np.diff(pairs[:,0])) # seconds
        # Cropping upper speed boundary to TwinCat boundary (30 um/s)
        upper_speed = min(tol_opt / frame_period, 30*10**(-3))
        # Cropping user input speed 
        spd = min(speed, upper_speed)

        # Baseline photometric broadband flux measurement
        # -----------------------------------------------
        photo_init, noise = self._get_photo_broad(dt_base, config)
        print(f"Baseline flux: {photo_init:.4f} with noise: {noise:.4f}")

        # Possible moves
        if sky:
            if CS:
                sky = 1
            else:
                sky = -1
            up=np.array([0,d,0,0],dtype=np.float64)
            left=np.array([-d,0,0,0],dtype=np.float64)
            down=np.array([0,-d,0,0],dtype=np.float64)
            right=np.array([d,0,0,0],dtype=np.float64)
            moves = np.array([up,left,down,right])
        else:
            sky = 0
            if CS: 
                up=np.array([0,0,0,d],dtype=np.float64)
                left=np.array([0,0,-d,0],dtype=np.float64)
                down=np.array([0,0,0,-d],dtype=np.float64)
                right=np.array([0,0,d,0],dtype=np.float64)
            else:
                up=np.array([0,d,0,0],dtype=np.float64)
                left=np.array([-d,0,0,0],dtype=np.float64)
                down=np.array([0,-d,0,0],dtype=np.float64)
                right=np.array([d,0,0,0],dtype=np.float64)
            moves = np.array([up,left,down,right])
        dirs = ["up","left","down","right"]
        
        # Probe all four cartesian directions
        for i in range(0,4):            
            print(f"Probing direction {dirs[i]}")

            # Bins for actuator position and flux samples across this direction
            ARM_act = []
            ARM_flux = []

            # Record starting position
            ARM_act.append(self._get_actuator_pos(config)[0])
            ARM_flux.append(photo_init)
            
            stop = False
            while not stop:
                print("Step")
                
                # Step
                speeds = np.full(4, spd, dtype=np.float64)
                _,_,acts,act_times,frames,_,_ = self.individual_step(False,sky,moves[i],speeds,config,True)

                # Evaluate photometry over window spanning the motion timeframe
                if (frames is not None and len(acts) > 0):
                    _,_,flux_seq,_ = self.humint.get_frames_cal_broad(frames=frames, sequence=True)
                    flux_step = flux_seq[:, self.photo_idx[config]]
                else:
                    flux_step = np.array([photo_init])

                # Pair each actuator position set to the nearest camera frame
                n_act, n_frame = len(acts), len(flux_step)
                for j in range(0, n_act):
                    # calculate the proportional index in the photometric readout array
                    b = int(round(j * (n_frame-1) / max(n_act-1, 1)))
                    b = min(b, n_frame-1)
                    ARM_act.append(acts[j])
                    ARM_flux.append(flux_step[b])

                # Assess increasing trend over sliding window
                n_windows = max((len(ARM_flux) - k) // l + 1, 1)
                windows = np.array([ARM_flux[w*l : w*l+k] for w in range(0, n_windows) if w*l+k <= len(ARM_flux)])
                if len(windows)==0:
                    continue
                win_av = np.mean(windows, axis=1)

                # Evaluate if the flux is monotonically increasing and stop if that is not the case
                if not np.all(np.diff(win_av) > 0):
                    stop = True

                # Refresh photometric baseline with each step
                photo_init, noise = self._get_photo_broad(dt_base, config)    

            # Bring the bench to the configuration corresponding to maximum flux along this direction's arm
            ARM_flux_arr = np.array(ARM_flux, dtype=np.float64)
            i_max = np.argmax(ARM_flux_arr)
            act_best = ARM_act[i_max]
            act_curr = self._get_actuator_pos(config)[0]
            act_disp = act_best - act_curr
            spd_push = np.full(4, speed_double, dtype=np.float64)
            pos_off = self._actoffset(spd_push, act_disp)
            snr_best = (ARM_flux_arr[i_max] - photo_init) / noise
            print(f"Best SNR along this direction: {snr_best:.2f} - pushing actuators to {act_curr + act_disp} mm")
            self._move_abs_ttm_act(act_curr, act_disp, spd_push, pos_off, config, sample=False)
    
    ##########################################
    # Performance characterization / Testing #
    ##########################################
    
    def cam_read_test(self,config):
    # Function to test the readout of the camera ROIs from the REDIS database
        
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")    
    
        # REDIS field names of photometric outputs' ROIs
        names = ["roi8_avg","roi7_avg","roi2_avg","roi1_avg"]
        fieldname = names[config]
        
        # Background measurements
        exps = []
        # Closing
        all_shutters_close(4)
        # Gathering five background exposures
        for j in range(0, 5):
            t_start,t_stop = define_time(0.500)
            exps.append(get_field("roi9_avg",t_start,t_stop,True)[1])
            time.sleep(0.500)
        # Taking the mean
        back = np.mean(exps)
        # Reopening
        all_shutters_open(4)
        
        # Readout 500 ms back in time
        t_start,t_stop = define_time(0.500) 
        # Current position noise measurement
        noise = get_field("roi9_avg",t_start,t_stop,True)[1] # Index 1 to get the temporal mean of spatial mean roi9_avg
        # Current position photometric output measurement
        photoconfig = get_field(fieldname,t_start,t_stop,True)[1]
        # Print out values
        print("Five-exposure (5x0.500s) averaged background : ", back)
        print("Current noise (ROI9) average : ", noise)
        print("Current noise (ROI9) average (background subtracted) : ", noise-back)
        print("Demanded photometric output average : ", photoconfig)
        print("Demanded photometric output average (background subtracted) : ", photoconfig-back)
        return
    
    # All functions below serve purpose in the context of actuator performance characterization
    # Characterization is done with actuator act_name
    
    def _move_abs_ttm_act_single(self,pos,speed,act_name,act_index,offset,config=1):        

        start_time = time.time()
        # Opening OPCUA connection
        opcua_conn = OPCUAConnection(url)
        opcua_conn.connect()
        
        # List of time stamps
        time_arr = []
        # List of positions
        pos_arr = []
        # Performing the movement
        #-------------------------#
        # Preparing actuator
        #act.reset()
        #time.sleep(0.100)
        #act.init()
        #time.sleep(0.050)
        #act.enable()
        #time.sleep(0.050)
            
        # Current position
        curr_pos = self._get_actuator_pos(config)[0][act_index]
        # Imposed position
        imposed_pos = pos
        # Imposed displacement
        imposed_disp = imposed_pos - curr_pos
        # Arrays
        imposed_disp_arr = np.zeros(4)
        imposed_speed_arr = np.zeros(4)
        imposed_disp_arr[act_index] = imposed_disp
        imposed_speed_arr[act_index] = speed
        imposed_disp_arr = np.array(imposed_disp_arr, dtype=np.float64)
        imposed_speed_arr = np.array(imposed_speed_arr, dtype=np.float64)
        # Accounting offset
        if offset:
            pos_offset = self._actoffset(imposed_speed_arr,imposed_disp_arr)[act_index]
            print("Offset from accuracy grid:", pos_offset, " mm")
            pos -= pos_offset # in mm

        # Executing move
        parent = opcua_conn.client.get_node('ns=4;s=MAIN.nott_ics.TipTilt.'+act_name)
        method = parent.get_child("4:RPC_MoveAbs")
        arguments = [pos, speed]
        parent.call_method(method, *arguments)
        #act.command_move_absolute(imposed_pos,speed)
        
        # Wait for the actuator to be ready
        on_destination = False
        while not on_destination:
            # Printing status, state and saving position & time every 10 ms (=REDIS sampling)
            time.sleep(0.01)
            status, state = opcua_conn.read_nodes(['ns=4;s=MAIN.nott_ics.TipTilt.'+act_name+'.stat.sStatus', 'ns=4;s=MAIN.nott_ics.TipTilt.'+act_name+'.stat.sState'])
            #print("Status:", status, "|| State:", state)
            on_destination = (status == 'STANDING' and state == 'OPERATIONAL')
            #print(act_name+" pos: ", str(self._get_actuator_pos(config)[0][act_index])+" mm")
            # Save current time
            #time_arr.append(time.time())
            # Save current position
            #pos_arr.append(self._get_actuator_pos(config)[0][3])
                
        # Time spent
        end_time = time.time()
        spent_time = end_time-start_time
        # ACTUAL Position achieved
        final_pos = self._get_actuator_pos(config)[0][act_index]
        print("----------------------------------------------------------------------------------------------------------------------------")
        print("Moving actuator "+act_name+" from "+str(curr_pos)+" mm to "+str(imposed_pos)+" mm at speed "+str(speed)+" mm/s took "+str(spent_time)+" seconds")
        print("Actual actuator position reached :"+str(final_pos)+" mm by error" +str(1000*(imposed_pos-final_pos))+" um.")
        print("----------------------------------------------------------------------------------------------------------------------------")   
        # Close OPCUA connection
        opcua_conn.disconnect()
        
        return spent_time,imposed_pos,final_pos,time_arr,pos_arr
    
    def act_response_test_single(self,act_displacement,speed,act_name,act_index,offset,align_pos,config=1):
        # Function to probe the actuator response (x,t) for given speed and displacement
        
        # STEP 1 : Reset actuator position if begin/end is reached (depending on the direction) and neutralize backlash
        # Current position
        curr_pos = self._get_actuator_pos(config)[0][act_index]
        pos_backlash = curr_pos
        # Actuator travel range [0,6] mm
        #act_range = 6 
        # Validity booleans
        valid_end = True
        valid_start = True
        # Exceeding upper limit of range?
        if act_displacement > 0:
            valid_end = (curr_pos+act_displacement <= align_pos+0.5)
        # Exceeding lower limit of range?
        else:
            valid_start = (curr_pos+act_displacement >= align_pos-0.5)
        
        if not valid_end:
            # Reset to start position
            curr_pos = align_pos
            # Neutralize backlash by imposing 2 micron shift (=10xresolution)
            pos_backlash = curr_pos+2*10**(-3)
        if not valid_start:
            # Reset to end position
            curr_pos = align_pos
            # Neutralize backlash by imposing 2 micron shift (=10xresolution)
            pos_backlash = curr_pos-2*10**(-3)
            
        # Impose the reset (motions need not be accurate here ==> fast speed)
        if not valid_start or not valid_end:
            # Resetting actuator
            _,_,_,_,_ = self._move_abs_ttm_act_single(curr_pos,0.1,act_name,act_index,False)
            # Neutralizing backlash
            _,_,_,_,_ = self._move_abs_ttm_act_single(pos_backlash,0.001,act_name,act_index,False)
            print("Actuator range reset, backlash neutralized")
        
        # STEP 2: Imposing the desired actuator displacement
        curr_pos = self._get_actuator_pos(config)[0][act_index]
        imposed_pos_d = curr_pos + act_displacement
        spent_time,imposed_pos,final_pos,time_arr,pos_arr = self._move_abs_ttm_act_single(imposed_pos_d,speed,act_name,act_index,offset)
        
        return np.array([spent_time,imposed_pos,final_pos],dtype=np.float64),time_arr,pos_arr

    def act_response_test_multi(self,act_displacements,len_speeds,act_name,act_index,offset,config=1):
        # Function to probe the actuator response for a range of displacements and speeds
        # To be used for displacements in ONE CONSISTENT DIRECTION (i.e. only positive / only negative displacements)

        act_pos_align = self.act_pos_align[config]
        if (act_index < 2):
            align_pos = (act_pos_align[0]+act_pos_align[1])/2
        else:
            align_pos = (act_pos_align[2]+act_pos_align[3])/2
        
        # Bring actuator to aligned position
        init_pos = self._get_actuator_pos(config)[0][act_index]
        init_disp = align_pos - init_pos
        _ = self.act_response_test_single(init_disp,0.01,act_name,act_index,False,align_pos)
        
        # Matrix containing time spent moving actuators, actuator accuracy (achieved-imposed) and image shift accuracy (achieved-imposed) for all displacement x speed combinations
        matrix_acc = np.zeros((6,len(act_displacements),len_speeds))
        # Lists containing time and position series of the movement
        times = []
        positions = []
        # Carrying out the test for each combination
        for i in range(0, len(act_displacements)):
            disp = act_displacements[i] #mm
            speeds = np.geomspace(0.0005/100,0.025,len_speeds) #mm/s #logspace
            for j in range(0, len(speeds)):
                acc_arr,time_arr,pos_arr = self.act_response_test_single(disp,speeds[j],act_name,act_index,offset,align_pos)
                matrix_acc[0][i][j] = acc_arr[0]
                act_acc = acc_arr[2]-acc_arr[1]
                matrix_acc[1][i][j] = act_acc
                times.append(time_arr)
                positions.append(pos_arr)
                
                # Calculating ttm shift accuracy from actuator displacement accuracy
                curr_pos = self._get_actuator_pos(config)[0]
                act_disp = np.zeros(4,dtype=np.float64)
                act_disp[act_index] = act_acc
                
                # Finding TTM shifts from actuator displacement
                ttm_acc = self._actuator_displacement_to_ttm_shift(curr_pos,act_disp,config)
                # Finding TTM angles from actuator positions
                curr_ttm = self._actuator_position_to_ttm_angle(curr_pos,config)
                
                # Finding distance value
                Darr = self._snap_distance_grid(curr_ttm,config)
                
                # Evaluating framework to get image plane shift accuracies
                shifts = self._framework_numeric_int_reverse(ttm_acc,Darr,1)
                
                matrix_acc[2:6,i,j] = shifts
            print(i)
        return matrix_acc,times,positions
    
    def act_backlash_test_multi(self,act_displacements,len_speeds,act_name,act_index,offset,config=1):
        # Function to probe the backlash, remaining after incorporation of the empirical actuator offsets, for a range of displacements and speeds.
        # For each speed v and displacement dx, the actuator is moved by \pm dx at speed v and then the same displacement is reversed. The backlash is
        # characterised by how well the initial position (before any displacement) and the final position (after two displacements) agree.
        
        act_pos_align = self.act_pos_align[config]
        if (act_index < 2):
            align_pos = (act_pos_align[0]+act_pos_align[1])/2
        else:
            align_pos = (act_pos_align[2]+act_pos_align[3])/2
        
        # Bring actuator to aligned position.
        init_pos = self._get_actuator_pos(config)[0][act_index]
        init_disp = align_pos - init_pos
        _ = self.act_response_test_single(init_disp,0.01,act_name,act_index,False,align_pos)
        # Matrix containing time spent moving actuators, backlash (final pos-initial pos) and image shift accuracy (final-initial) for all displacement x speed combinations
        matrix_acc = np.zeros((6,len(act_displacements),len_speeds))
        # Carrying out the test for each combination
        for i in range(0, len(act_displacements)):
            disp = act_displacements[i] # mm
            speeds = np.geomspace(0.0005/100,0.025,len_speeds) #mm/s #logspace
            for j in range(0, len(speeds)):
                # Current position
                init_pos = self._get_actuator_pos(config)[0][act_index]
                # Step 1
                arr1,_,_ = self.act_response_test_single(disp,speeds[j],act_name,act_index,offset,align_pos)
                # Step 2
                arr2,_,_ = self.act_response_test_single(-disp,speeds[j],act_name,act_index,offset,align_pos)
                # Final achieved position
                final_pos = arr2[2]
                # Backlash
                back = final_pos - init_pos
                # Total time spent moving actuators
                time_spent = arr1[0]+arr2[0]
                # Storing in matrix
                matrix_acc[0][i][j] = time_spent
                matrix_acc[1][i][j] = back
                # Calculating ttm shift from actuator backlash
                curr_pos = self._get_actuator_pos(config)[0]
                act_disp = np.array([0,0,0,back],dtype=np.float64)
                # Finding TTM shifts from actuator displacement
                ttm_acc = self._actuator_displacement_to_ttm_shift(curr_pos,act_disp,config)
                # Finding TTM angles from actuator positions
                curr_ttm = self._actuator_position_to_ttm_angle(curr_pos,config)
                # Finding distance value
                Darr = self._snap_distance_grid(curr_ttm,config)
                # Evaluating framework to get image plane shift accuracies
                shifts = self._framework_numeric_int_reverse(ttm_acc,Darr,1)
                # Storing in matrix
                matrix_acc[2:6,i,j] = shifts
            print(i)
        return matrix_acc
    
    def actuator_performance(self):
        
        act_name = "NTPB2"
        grid_size = 21
        
        displacements_pos = np.geomspace(0.0005,0.025,grid_size)
        displacements_neg = np.geomspace(-0.0005,-0.025,grid_size)
        for i in range(0,3):
            # Offset-accounted grids
            matrix_acc,times,positions = self.act_response_test_multi(displacements_pos,grid_size,act_name,3,True)
            np.save("offpos"+str(i+1),matrix_acc)
            matrix_acc,times,positions = self.act_response_test_multi(displacements_neg,grid_size,act_name,3,True)
            np.save("offneg"+str(i+1),matrix_acc)
        for i in range(0,4):
            # Backlash grids
            matrix_back = self.act_backlash_test_multi(displacements_pos,grid_size,act_name,3,False)
            np.save("backpos"+str(i+1),matrix_back)
            matrix_back = self.act_backlash_test_multi(displacements_neg,grid_size,act_name,3,False)
            np.save("backneg"+str(i+1),matrix_back)
            # Backlash grids
            matrix_back = self.act_backlash_test_multi(displacements_pos,grid_size,act_name,3,True)
            np.save("backposoff"+str(i+1),matrix_back)
            matrix_back = self.act_backlash_test_multi(displacements_neg,grid_size,act_name,3,True)
            np.save("backnegoff"+str(i+1),matrix_back)
        return
    
    def visible_camera_performance(self,N,pupilpar=False):
        """
        
        Parameters
        ----------
        pupilpar : single boolean
            True when you wish to study the performance of shifts imposed in the pupil plane.
        N : single integer
            How much iterations, i.e. random shifts, to go through.

        """
        # Selecting devices
        tries = 0
        tries_max = 6
        sleep_time_secs = 10
        while tries < tries_max:  # Wait for device for 60 seconds
            # Only select the visible cameras (not the InfraTec):
            device_list = []
            for device_info in system.device_infos:
                if device_info["model"] == "PHX064S-M":
                    device_list.append(device_info)
            # Connect to visible cameras
            devices = system.create_device(device_list)
            if not devices:
                print(
                    f'Try {tries+1} of {tries_max}: waiting for {sleep_time_secs} '
                    f'secs for a device to be connected!')
                for sec_count in range(sleep_time_secs):
                    time.sleep(1)
                    print(f'{sec_count + 1 } seconds passed ',
                          '.' * sec_count, end='\r')
                tries += 1
            else:
                print(f'Created {len(devices)} device(s)\n')
                break
        else:
            raise Exception(f'No device found! Please connect a device and run '
                            f'the example again.')

        device_IM = system.select_device(devices)
        device_PUPIL = system.select_device(devices)
        print(f'Device used for image plane:\n\t{device_IM}')
        print(f'Device used for pupil plane:\n\t{device_PUPIL}')
        
        # Get stream nodemap to set features before streaming
        stream_nodemap_IM = device_IM.tl_stream_nodemap
        stream_nodemap_PUPIL = device_PUPIL.tl_stream_nodemap
        
        # Enable stream auto negotiate packet size
        stream_nodemap_IM['StreamAutoNegotiatePacketSize'].value = True
        stream_nodemap_PUPIL['StreamAutoNegotiatePacketSize'].value = True
        # Enable stream packet resend
        stream_nodemap_IM['StreamPacketResendEnable'].value = True
        stream_nodemap_PUPIL['StreamPacketResendEnable'].value = True
        
        nodemap_IM = device_IM.nodemap
        nodemap_PUPIL = device_PUPIL.nodemap

        # Setting width, height, x/y offsets to limit the buffer size
    
        # Setting IMAGE plane nodemap config
        nodemap_IM["Width"].value = 148
        nodemap_IM["Height"].value = 150
        nodemap_IM["OffsetX"].value = 1500
        nodemap_IM["OffsetY"].value = 1250
        # Setting PUPIL plane nodemap config TBC
        nodemap_PUPIL["Width"].value = 3072
        nodemap_PUPIL["Height"].value = 2048
        nodemap_PUPIL["OffsetX"].value = 0
        nodemap_PUPIL["OffsetY"].value = 0
        
        # Setting exposure mode and exposure time (lowest possible for the green laser)
        nodemap_IM["ExposureAuto"].value = "Off"
        nodemap_IM["ExposureTime"].value = 27.216
        nodemap_PUPIL["ExposureAuto"].value = "Off"
        nodemap_PUPIL["ExposureTime"].value = 25000.0
        
        # Gaussian PSF fitting radius estimates
        rfit_im = 10
        rfit_pup = 500

        def retrieve_pos(devicepar,nodemappar,rfit):

            with devicepar.start_stream():

                # PREPARATION #
                #-------------#
                # Create buffer 
                buffer = devicepar.get_buffer()
                # Numpy matrix containing image data
                nparray = np.array(buffer.data, dtype=np.uint8)
                nparray = nparray.reshape(buffer.height, buffer.width)
                # Width
                w = nodemappar["Width"].value
                h = nodemappar["Height"].value
                # Data
                x = np.linspace(1,w,w)
                y = np.linspace(1,h,h)
                x,y = np.meshgrid(x,y)
                # Indices of maximum
                i = np.argmax(nparray)//w
                j = np.argmax(nparray)%w   
                # FITTING #
                #---------#
                # Airy disk model
                airy = models.AiryDisk2D(amplitude=np.max(nparray),x_0=j,y_0=i,radius=rfit,bounds={"amplitude":(0,1.5*np.max(nparray)),"x_0":(0,w),"y_0":(0,h),"radius":(0.1*rfit,2*rfit)})
                # Performing least squares fitting procedure
                fit_ent = fitting.LevMarLSQFitter(calc_uncertainties=True)
                pix = fit_ent(airy,x,y,nparray)
                xfit,yfit=pix.x_0.value,pix.y_0.value
                # PLOTTING
                #fig = plt.figure(figsize=(10,10))
                #ax = fig.add_subplot(111)
                #img = ax.imshow(nparray)
                #ax.scatter(j,i, color="red",label="Max")
                #ax.scatter(xfit,yfit,color="blue",label="Fit")
                #ax.legend()
                #fig.canvas.draw()
                #fig.canvas.flush_events()
                #fig.show()
                # Requeue to release buffer memory
                devicepar.requeue_buffer(buffer)
            print("Fitted position : ", xfit,yfit)
            return [xfit,yfit]
        
        def step(xstep,ystep):
            # xstep : mm
            # ystep : mm
            def deproject(pos,theta):
                x = pos[0]
                y = pos[1]
                x_prim = x*np.cos(theta)-y*np.sin(theta)
                y_prim = x*np.sin(theta)+y*np.cos(theta)
                return [x_prim,y_prim]
            # Deprojection angles (FROM BENCH XY AXES TO CAMERA X'Y' AXES!)
            angle_IM = 0
            angle_PUPIL = 0
            # 1) Retrieve initial position
            pos_init_IM = retrieve_pos(device_IM,nodemap_IM,rfit_im)
            pos_init_PUPIL = retrieve_pos(device_PUPIL,nodemap_PUPIL,rfit_pup)
            # 2) Perform an individual step by the given dimensions, in the plane specified; with random speed.
            speed=random.uniform(0.005,25)*10**(-3)
            speeds = np.array([speed,speed,speed,speed],dtype=np.float64) # mm/s TBC
            speeds[speeds<0.005*10**(-3)] = 0.005*10**(-3)
            if pupilpar:
                steps = np.array([xstep,ystep,0,0],dtype=np.float64)
            else:
                steps = np.array([0,0,xstep,ystep],dtype=np.float64)
            # Performing the step
            _,_,_,_,_,act_err,_ = self.individual_step(False,0,steps,speeds,1,False)
            # 3) Retrieve final position
            pos_final_IM = retrieve_pos(device_IM,nodemap_IM,rfit_im)
            pos_final_PUPIL = retrieve_pos(device_PUPIL,nodemap_PUPIL,rfit_pup)
            # Deproject the coordinates
            pos_init_IM = deproject(pos_init_IM,angle_IM)
            pos_init_PUPIL = deproject(pos_init_PUPIL,angle_PUPIL)
            pos_final_IM = deproject(pos_final_IM,angle_IM)
            pos_final_PUPIL = deproject(pos_final_PUPIL,angle_PUPIL)
            # Calculating the shifts
            xshift_IM = pos_final_IM[0]-pos_init_IM[0]
            yshift_IM = pos_final_IM[1]-pos_init_IM[1]
            xshift_PUPIL = pos_final_PUPIL[0]-pos_init_PUPIL[0]
            yshift_PUPIL = pos_final_PUPIL[1]-pos_init_PUPIL[1]
            # 4) Calculating the image x and y displacements, predicted by the framework from the actuator errors.
            curr_pos = self._get_actuator_pos(1)[0]
            ttm_acc = self._actuator_displacement_to_ttm_shift(curr_pos,act_err,1)
            curr_ttm = self._actuator_position_to_ttm_angle(curr_pos,1)
            Darr = self._snap_distance_grid(curr_ttm,1)
            shifts = self._framework_numeric_int_reverse(ttm_acc,Darr,1)
            # Returning x and y shifts in physical dimensions (micrometer) - each pixel is 2.40 um
            return [np.array([pos_init_PUPIL[0],pos_init_PUPIL[1],pos_final_PUPIL[0],pos_final_PUPIL[1],pos_init_IM[0],pos_init_IM[1],pos_final_IM[0],pos_final_IM[1]],dtype=np.float64)*2.40*10**(-3),np.array([shifts[2],shifts[3],shifts[0],shifts[1]],dtype=np.float64),speed] #mm(/s)
        
        def rand_sign():
            return 1 if random.random() < 0.5 else -1
    
        # Framework performance
        # Step 1 : Align
        self.align()
        # Step 2 : Drawing random shifts and imposing the steps to the bench, note: only if the imposed state is valid (f.e. not off the slicer)
        def step_validcheck():
            valid = False
            while not valid:
                valid = True
                if pupilpar: # TBC
                    dx=rand_sign()*random.uniform(0.5,25)*10**(-3)
                    dy=rand_sign()*random.uniform(0.5,25)*10**(-3)
                else:
                    dx=rand_sign()*random.uniform(0.5,25)*10**(-3)
                    dy=rand_sign()*random.uniform(0.5,25)*10**(-3)
                try:
                    coordsx,errx,speed = step(dx,0)
                    coordsy,erry,speed = step(0,dy)
                # If individual_step throws exception (state not valid), stay in while loop.
                except ValueError:
                    valid = False
            return coordsx,coordsy,errx,erry,dx,dy,speed
        
        # Shifts data container
        acc = []
        pos = []
        for i in range(0,N):
            coordsx,coordsy,errx,erry,dx,dy,speed = step_validcheck()
            if pupilpar:
                dx_err = np.abs(dx)-np.abs(shifts[2])
                dy_err = np.abs(dy)-np.abs(shifts[3])
                acc.append(np.array([dx,dy,dx_err,dy_err,shifts_iter[0],shifts_iter[1],speed,pupilpar],dtype=np.float64))
            else:
                pos_init_x = coordsx[4:6]
                pos_final_x = coordsx[6:8]
                pos_init_y = coordsy[4:6]
                pos_final_y = coordsy[6:8]
                pos_init_x_PUP = coordsx[0:2]
                pos_final_x_PUP = coordsx[2:4]
                pos_init_y_PUP = coordsy[0:2]
                pos_final_y_PUP = coordsy[2:4]
                
                err = errx+erry
                
                dx_ach = pos_final_y[0]-pos_init_x[0]
                dy_ach = pos_final_y[1]-pos_init_x[1]
                dx_pup = pos_final_y_PUP[0]-pos_init_x_PUP[0]
                dy_pup = pos_final_y_PUP[1]-pos_init_x_PUP[1]
                
                dx_err = np.abs(dx)-np.abs(dx_ach)
                dy_err = np.abs(dy)-np.abs(dy_ach)
                dx_act_err = np.abs(dx+err[0])-np.abs(dx_ach)
                dy_act_err = np.abs(dy+err[1])-np.abs(dy_ach)
                print("Iteration "+str(i)+" : "+str([1000*dx_err,1000*dy_err])+" um errors on imposed displacements "+str([1000*dx,1000*dy])+" um.")
                acc.append(np.array([dx,dy,dx_err,dy_err,dx_pup,dy_pup,speed,pupilpar,dx_act_err,dy_act_err],dtype=np.float64))
                pos.append(np.array([pos_init_x,pos_final_x,pos_init_y,pos_final_y,pos_init_x_PUP,pos_final_x_PUP,pos_init_y_PUP,pos_final_y_PUP],dtype=np.float64))
        
        # Destroy the devices before returning
        system.destroy_device(device=device_IM)
        system.destroy_device(device=device_PUPIL)
        # Saving result
        np.save("Acc_frame", np.array(acc))
        np.save("Pos_frame",np.array(pos))
        return acc
    
    def align(self,config=1):
            print("---------------------------------------------------------------------------")
            print("Bring beam to visual aligned state.")
            print("---------------------------------------------------------------------------")
            pos_arr = np.array(self.act_pos_align[config],dtype=np.float64)
            # Necessary Displacements for Alignment
            curr_pos = self._get_actuator_pos(config)[0]
            disp_arr = pos_arr-curr_pos
            speed_arr = np.array([0.021,0.021,0.021,0.021],dtype=np.float64)
            off = self._actoffset(speed_arr,disp_arr)
            self._move_abs_ttm_act(curr_pos,disp_arr,speed_arr,off,config,False,0.010,self._get_delay(100,True)-t_write)
            return
    
    def algorithm_test(self,K,step_opt,speed_opt,dt_opt,k_opt,l_opt):
        
        def kick_loc_opt(obj,config):
            def rand_sign():
                return 1 if random.random() < 0.5 else -1
            dx=rand_sign()*random.uniform(20,50)*10**(-3)
            dy=rand_sign()*random.uniform(20,50)*10**(-3)
            print("Kicking the beam away from aligned state, by random \pm 50 um distances in image plane (dx,dy) = ", (dx,dy))
            steps = np.array([0,0,dx,dy])
            speed_arr = np.array([0.01,0.01,0.01,0.01],dtype=np.float64)
            # Kick away
            obj.individual_step(True,0,steps,speed_arr,1,False,0.010,self._get_delay(100,True)-t_write)
            # Registering start time 
            t_start = time.time()
            # Spiraling to return 
            obj.localization_spiral(False,20,0.010,config,0.10)
            obj.optimization_cross(False,True,step_opt,speed_opt,1,dt_opt,k_opt,l_opt)
            
            #obj.optimization_spiral_gradient(False,5*10**(-3),0.0011,config,0.05,8)
            #obj.optimization_spiral_gradient(False,3*10**(-3),0.0011,config,0.05,4)
            #obj.optimization_spiral_gradient(False,1*10**(-3),0.0011,config,0.05,2)
            #obj.optimization_spiral_gradient(False,0.2*10**(-3),0.0003,config,0.05,1)
            
            # Measuring end time
            t_end = time.time()
            # Time spent localizing and optimizing
            t_spent = t_end-t_start
            # Achieved ROI outputs
            
            # Delay time (total delay minus writing time)
            t_delay = self._get_delay(100,True)-t_write 
            # Start time for exposure
            t_start = self._get_time(1000*time.time(),t_delay)
            # Sleep
            time.sleep((500+t_write)*10**(-3)) 
            # Photometric output measurement 
            photo_ach = self._get_photo(Nexp,t_start,500,1)
            print("Initial photometric output : ", photo_ach)
            
            return dx,dy,t_spent,photo_ach

        # Configuration parameters
        configpar = 1 # second beam
        lamb = 1      # central wavelength
        print("---------------------------------------------------------------------------")
        print("Camera Readout")
        print("---------------------------------------------------------------------------")
        self.cam_read_test(configpar)
        print("---------------------------------------------------------------------------")
        print("Current Configuration")
        print("---------------------------------------------------------------------------")
        act_name='NTPB2'
        curr_pos = self._get_actuator_pos(configpar)[0]
        print("Current actuator positions :", self._get_actuator_pos(configpar)[0])
        
        data = []
        
        for i in range(0,K):
            self.align(configpar)
            dx,dy,t_spent,photo_ach = kick_loc_opt(self,configpar)
            data.append([dx,dy,t_spent,photo_ach])
        
        data_arr = np.array(data,dtype=np.float64)
        np.save("AlgorithmTest",data_arr)
        return 
        
    
