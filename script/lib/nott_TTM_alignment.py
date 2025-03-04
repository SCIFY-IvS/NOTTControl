# -*- coding: utf-8 -*-
"""
Created on Thu Dec 12 11:51:16 2024

Collection of functions created to facilitate NOTT alignment through mirror tip/tilt motion.

@author: Thomas Mattheussen
"""

# TO DO: 
# - Generalize class initialisation to prepare the actuators for each config (once more actuators are installed)
# - Complete act_pos_align (actuator positions in state of alignment) for each config (once more actuators are installed)

# Imports
from sympy import *
import numpy as np
import sys
import time
from configparser import ConfigParser
import logging
import redis

# Add the path to sys.path
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/')

from opcua import OPCUAConnection
from components.motor import Motor

# Functions for retrieving data from REDIS
from nott_database import define_time
from nott_database import get_field

# Silent messages from opcua every time a command is sent
logger = logging.getLogger("asyncua")
logger.setLevel(logging.WARNING)

# Zemax-simulated inter-component distance grid
Dgrid = np.load("C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/TTMGrids/Dgrid.npy")

# Absolute TTM angles by which the grid of distance values (Dgrid) is simulated
TTM1Xgrid = np.load("C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/TTMGrids/Grid_TTM1X.npy")
TTM1Ygrid = np.load("C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/TTMGrids/Grid_TTM1Y.npy")
TTM2Xgrid = np.load("C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/TTMGrids/Grid_TTM2X.npy")
TTM2Ygrid = np.load("C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/TTMGrids/Grid_TTM2Y.npy")

# On-bench simulated accuracy grid (achieved-imposed) for positive/negative displacements
accurgrid_pos = np.load("C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/Grid_Accuracy_Pos.npy")
accurgrid_neg = np.load("C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/data/Grid_Accuracy_Neg.npy")

class alignment:
    
    def __init__(self):
        """    
        Terminology
        ----------
        X = Shift in the x-direction, in the pupil plane (cold stop)
        Y = Shift in the y-direction, in the pupil plane (cold stop)
        x = Shift in the x-direction, in the image plane (chip input)
        y = Shift in the y-direction, in the image plane (chip input)
        (a1X,a2X) = TTM1 X and TTM2 X angular offsets respectively.
        (a1Y,a2Y) = TTM1 Y and TTM2 Y angular offsets respectively.
        Note : A TTM X angle should be interpreted as an angle about the X-axis.
               Therefore, a TTM X angle induces a positional Y shift & vice versa.
        (D1,...,D8) = Inter-component distances traveled by the beam throughout the system
        di,dc = Injection & cold stop lens thicknesses
        P1 = Injection lens front surface optical power
        R1,R2,Rsl = OAP1,OAP2,Slicer curvature radii
               
        Description
        ----------
        The function does the following:
            (1) Define Sympy symbols
            (2) Define general component transformations
            (3) Chain together the transformations, encountered by a beam as it 
                travels through NOTT. This procedure is done independently for the
                transverse X and Y dimensions. The result are four equations, each linking
                one of (X,Y,x,y) to the relevant angular offsets (TTM Y for X/x-direction shifts & vice versa).
            (4) Translate the obtained four equations into one single matrix equation b=Ma, with b the shifts and a the angular offsets.
            (5) Defines matrix M and vector of symbolic shifts b. 
                Defines vector N, which comprises the symbolic expressions for CS/IM shifts as a function of TTM angles in non-matrix form.
                N = M*b
            (6) Prepares all actuators for use
                   
        Defines
        -------
        The function initializes global variables M, N and b, which are then used in all other functions.
        M : (4,4) matrix of symbolic Sympy expressions
        N : (1,4) matrix of symbolic Sympy expressions
        b : (4,1) matrix of symbolic Sympy expressions
                   
        """
        print("Defining symbolic framework...")
        #-------------#
        # (1) Symbols #
        #-------------#
        X,x,Y,y = symbols("X x Y y")
        a1X,a2X,a1Y,a2Y = symbols("a_1^X a_2^X a_1^Y a_2^Y") 
        D1, D2, D3, D4, D5, D6, D7, D8 = symbols("D_1 D_2 D_3 D_4 D_5 D_6 D_7 D_8")
        di, dc, ni, nc, P1, f1, f2, fsl = symbols("d_i d_c n_i n_c P_1 f_{OAP_1} f_{OAP_2} f_{sl}")
        
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
        '''
        # Preparing actuators for use, only config 1 installed as of now.
        print("Preparing actuators")
        # Retrieving OPCUA url from config.ini
        configpars = ConfigParser()
        configpars.read('../../config.ini')
        url =  configpars['DEFAULT']['opcuaaddress']
        # Opening OPCUA connection
        opcua_conn = OPCUAConnection(url)
        opcua_conn.connect()
        # Actuator names
        act_names = ['NTTA'+str(2),'NTPA'+str(2),'NTTB'+str(2),'NTPB'+str(2)]
        # Actuator motor objects
        act1 = Motor(opcua_conn, 'ns=4;s=MAIN.nott_ics.TipTilt.'+act_names[0],act_names[0])
        act2 = Motor(opcua_conn, 'ns=4;s=MAIN.nott_ics.TipTilt.'+act_names[1],act_names[1])
        act3 = Motor(opcua_conn, 'ns=4;s=MAIN.nott_ics.TipTilt.'+act_names[2],act_names[2])
        act4 = Motor(opcua_conn, 'ns=4;s=MAIN.nott_ics.TipTilt.'+act_names[3],act_names[3])
        actuators = np.array([act1,act2,act3,act4])
        # Resetting and initializing each actuator
        for i in range(0,4):
            actuators[i].reset()
            time.sleep(1)
            actuators[i].init()
            # Wait for the actuator to be ready
            ready = False
            while not ready:
                time.sleep(0.01)
                substatus = opcua_conn.read_nodes(['ns=4;s=MAIN.nott_ics.TipTilt.'+act_names[i]+'.stat.sSubstate'])
                ready = (substatus[0] == 'READY')
        
        # Closing OPCUA connection
        opcua_conn.disconnect()
        '''
    def _framework_numeric_int(self,shifts,D,lam=1):
        """
        Description
        -----------
        The function numerically evaluates the symbolic framework by input positional shifts (X,Y,x,y),
        thus returning thereto necessary angular offsets (dTTM1X,dTTM1Y,dTTM2X,dTTM2Y).
        
        Context
        -------
        The function is called in the context of internal NOTT alignment, f.e. scanning the image plane for beam injection.
        
        Parameters
        ----------
        shifts : (1,4) numpy array of floats (mm)
            User-desired positional shifts (X,Y,x,y) in cold stop (X,Y) and image (x,y) plane 
        D : (1,8) numpy array of floats (mm)
            Eight inter-component distance values (D1,...,D8) traveled by the reference beam 
        lam : single integer
            NOTT wavelength channel number (0 = 3.5 micron ; 1 = 3.8 micron ; 2 = 4.0 micron)
        Do note : Distance grid Dgrid is simulated for the central wavelength in Zemax.
            
        Returns
        -------
        ttm_offsets_flip : (1,4) numpy array of floats (radian)
        The angular TTM offsets (dTTM1X,dTTM1Y,dTTM2X,dTTM2Y) necessary to achieve the input shifts 
            
        """
        # Symbols
        X,x,Y,y = symbols("X x Y y")
        a1X,a2X,a1Y,a2Y = symbols("a_1^X a_2^X a_1^Y a_2^Y") 
        D1, D2, D3, D4, D5, D6, D7, D8 = symbols("D_1 D_2 D_3 D_4 D_5 D_6 D_7 D_8")
        di, dc, ni, nc, P1, f1, f2, fsl = symbols("d_i d_c n_i n_c P_1 f_{OAP_1} f_{OAP_2} f_{sl}")
        
        #------------------------#
        # Zemax parameter values #
        #------------------------#
        
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
        niarr = [2.4189, 2.4176, 2.4168] 
        ncarr = [1.4140, 1.4115, 1.4096]
        # Injection lens curvature radius (front surface)
        Rinj = 28.195
        # Optical power front injection lens surface (1/mm)
        Parr = (niarr - np.ones(3)) / Rinj
        
        # Copy of symbolic framework
        Mcopy = self.M.copy()
        bcopy = self.b.copy()
        # Substituting parameter values into the symbolic matrix
        subspar = [(D1,D[0]),(D2,D[1]),(D3,D[2]),(D4,D[3]),(D5,D[4]),(D6,D[5]),(D7,D[6]),(D8,D[7]),(di,dinj),(dc,dcryo),(ni,niarr[lam]),(nc,ncarr[lam]),(P1,Parr[lam]),(f1,fOAP1),(f2,fOAP2),(fsl,fsli)]
        Mcopy = Mcopy.subs(subspar)
        
        # Inverting the (now numeric) matrix 
        Minv = Mcopy.inv()
        
        # Multiplying by symbolic shifts 
        frame = Minv*bcopy
        
        # Parameters
        params = (X,Y,x,y)
        
        # Lambdify
        f = lambdify(params,frame.T.tolist()[0], modules="numpy")
        
        # Numeric evaluation
        ttm_offsets = f(shifts[0],shifts[1],shifts[2],shifts[3])
        
        # Flipping X and Y angles to comply with function output
        ttm_offsets_flip = np.array([ttm_offsets[1],ttm_offsets[0],ttm_offsets[3],ttm_offsets[2]],dtype=np.float64)
        
        return ttm_offsets_flip
    
    def _framework_numeric_int_reverse(self,ttm_offsets,D,lam=1):
        """
        Description
        -----------
        The function numerically evaluates the symbolic framework by input TTM angular offsets (dTTM1X,dTTM1Y,dTTM2X,dTTM2Y),
        returning the positional shifts (X,Y,x,y) that the offsets induce.

        Parameters
        ----------
        ttm_offsets : (1,4) numpy array of floats (rad)
            User-desired TTM angular offsets (dTTM1X,dTTM1Y,dTTM2X,dTTM2Y)
        D : (1,8) numpy array of floats (mm)
            Eight inter-component distance values (D1,...,D8) traveled by the reference beam 
        lam : single integer
            NOTT wavelength channel number (0 = 3.5 micron ; 1 = 3.8 micron ; 2 = 4.0 micron)
        Do note : Distance grid Dgrid is simulated for the central wavelength in Zemax.

        Returns
        -------
        shifts : (1,4) numpy array of floats (mm)
            Induced positional shifts in CS/IM planes (X,Y,x,y).

        """
        # Symbols
        X,x,Y,y = symbols("X x Y y")
        a1X,a2X,a1Y,a2Y = symbols("a_1^X a_2^X a_1^Y a_2^Y") 
        D1, D2, D3, D4, D5, D6, D7, D8 = symbols("D_1 D_2 D_3 D_4 D_5 D_6 D_7 D_8")
        di, dc, ni, nc, P1, f1, f2, fsl = symbols("d_i d_c n_i n_c P_1 f_{OAP_1} f_{OAP_2} f_{sl}")
        
        #------------------------#
        # Zemax parameter values #
        #------------------------#
        
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
        niarr = [2.4189, 2.4176, 2.4168] 
        ncarr = [1.4140, 1.4115, 1.4096]
        # Injection lens curvature radius (front surface)
        Rinj = 28.195
        # Optical power front injection lens surface (1/mm)
        Parr = (niarr - np.ones(3)) / Rinj
        
        # Copy of symbolic framework
        Ncopy = self.N.copy()
        # Substituting parameter values into the symbolic matrix
        subspar = [(D1,D[0]),(D2,D[1]),(D3,D[2]),(D4,D[3]),(D5,D[4]),(D6,D[5]),(D7,D[6]),(D8,D[7]),(di,dinj),(dc,dcryo),(ni,niarr[lam]),(nc,ncarr[lam]),(P1,Parr[lam]),(f1,fOAP1),(f2,fOAP2),(fsl,fsli),(a1X,ttm_offsets[0]),(a1Y,ttm_offsets[1]),(a2X,ttm_offsets[2]),(a2Y,ttm_offsets[3])]
        shifts = np.array([Ncopy[0].subs(subspar),Ncopy[1].subs(subspar),Ncopy[2].subs(subspar),Ncopy[3].subs(subspar)],dtype=np.float64)
        return shifts
    
    def _framework_numeric_sky(self,dTTM1X,dTTM1Y,D,lam=1,CS=True):
        """
        Description
        -----------
        The function numerically evaluates the symbolic framework expression by substituting the input dTTM1X & dTTM1Y angular offsets.
        Then, the shifts (X,Y,x,y) are determined as a function of the remaining angular offsets (dTTM2X,dTTM2Y).
        Based on parameter CS, a choice is made : if True, (dTTM2X,dTTM2Y) are determined such that (X,Y)=(0,0).
                                                  if False, (dTTM2X,dTTM2Y) are determined such that (x,y)=(0,0).
                                                  No non-trivial combination of (dTTM2X,dTTM2Y) exists that guarantees both.
                                                  
        Context
        -------
        The function is relevant in the context of on-sky scanning. There, TTM1 takes the role of the scanner; a TTM1 angular offset changes the on-sky angle of the picked up FOV.
        A desired on-sky angular offset should then be translated to a necessary TTM1 angular offset, which is to be imposed to the system.
        Thereafter, the TTM2 angular offsets should be calculated that make it such that the scanning has no effect on alignment in a user-specified plane (CS/IM).
        
        Parameters
        ----------
        dTTM1X,dTTM1Y : two float values
            User-desired TTM1 angular offsets, calculated from desired on-sky angles by étendue conservation.
        D : (1,8) numpy array of floats
            Eight inter-component distance values (D1,...,D8) traveled by the reference beam (mm)
        lam : single integer
            NOTT wavelength channel number (0 = 3.5 micron ; 1 = 3.8 micron ; 2 = 4.0 micron)
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
        # Symbols
        X,x,Y,y = symbols("X x Y y")
        a1X,a2X,a1Y,a2Y = symbols("a_1^X a_2^X a_1^Y a_2^Y") 
        D1, D2, D3, D4, D5, D6, D7, D8 = symbols("D_1 D_2 D_3 D_4 D_5 D_6 D_7 D_8")
        di, dc, ni, nc, P1, f1, f2, fsl = symbols("d_i d_c n_i n_c P_1 f_{OAP_1} f_{OAP_2} f_{sl}")
        
        #------------------------#
        # Zemax parameter values #
        #------------------------#
        
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
        niarr = [2.4189, 2.4176, 2.4168] 
        ncarr = [1.4140, 1.4115, 1.4096]
        # Injection lens curvature radius (front surface)
        Rinj = 28.195
        # Optical power front injection lens surface (1/mm)
        Parr = (niarr - np.ones(3)) / Rinj
        
        # Copy of symbolic framework
        Mcopy = self.M.copy()
        
        # Substituting parameter values into the symbolic matrix
        subspar = np.array([(D1,D[0]),(D2,D[1]),(D3,D[2]),(D4,D[3]),(D5,D[4]),(D6,D[5]),(D7,D[6]),(D8,D[7]),(di,dinj),(dc,dcryo),(ni,niarr[lam]),(nc,ncarr[lam]),(P1,Parr[lam]),(f1,fOAP1),(f2,fOAP2),(fsl,fsli)])
        Mcopy = Mcopy.subs(subspar)
        
        # Inverting the (now numeric) matrix
        frame = Mcopy.inv()
        
        # Evaluating
        a2X,a2Y = symbols('a_2^X a_2^Y')
        c = Matrix([dTTM1Y,dTTM1X,a2Y,a2X])
        
        # Sol contains (X,Y,x,y) pupil and image plane positions as a function of TTM2X and TTM2Y offsets
        sol = frame.solve(c)
        
        if CS:
            dTTM2X = list(solveset(sol[1],a2X).args)[0]
            dTTM2Y = list(solveset(sol[0],a2Y).args)[0]
            x = sol[2].subs(np.array([(a2X,dTTM2X),(a2Y,dTTM2Y)]))
            y = sol[3].subs(np.array([(a2X,dTTM2X),(a2Y,dTTM2Y)]))
                            
            ttm_offsets = np.array([dTTM1X,dTTM1Y,dTTM2X,dTTM2Y],dtype=np.float64)
            shifts = np.array([0,0,x,y],dtype=np.float64)
            
            return ttm_offsets,shifts
        else:
            dTTM2X = list(solveset(sol[3],a2X).args)[0]
            dTTM2Y = list(solveset(sol[2],a2Y).args)[0]
            X = sol[0].subs(np.array([(a2X,dTTM2X),(a2Y,dTTM2Y)]))
            Y = sol[1].subs(np.array([(a2X,dTTM2X),(a2Y,dTTM2Y)]))
                            
            ttm_offsets = np.array([dTTM1X,dTTM1Y,dTTM2X,dTTM2Y],dtype=np.float64)
            shifts = np.array([X,Y,0,0],dtype=np.float64)
            
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
        Entrance pupil (UT) beam diameter : 8.2 m 
        Exit pupil (TTM positions) beam diameter : 12 mm 
        
        Parameters
        ----------
        sky_angles : (1,4) numpy array of floats (radian)
            An array of on-sky angular offsets 
            
        Returns
        -------
        ttm_angles : (1,4) numpy array of floats (radian)
            An array of TTM angular offsets

        """
        Dentr = 8.2 
        Dexit = 12 * 10**(-3)
        
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
        Dentr = 8.2 
        Dexit = 12 * 10**(-3)
        
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
            Configuration number (= VLTI input beam) (0,1,2,3)
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference)

        Returns
        -------
        D_snap : (1,8) numpy array of float values (mm)
            An array of Zemax-simulated distances (D1,...,D8) corresponding to the grid point closest to ttm_angles

        """
        
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
    
        a = np.argmin(np.abs(TTM1Ygrid[config] - ttm_angles[1]))
        b = np.argmin(np.abs(TTM2Ygrid[config] - ttm_angles[3]))
        c = np.argmin(np.abs(TTM1Xgrid[config] - ttm_angles[0]))
        d = np.argmin(np.abs(TTM2Xgrid[config] - ttm_angles[2]))
        
        D_snap = Dgrid[config,:,a,b,c,d]
  
        return D_snap

    def _snap_accuracy_grid(self,speed,disp):
        """
        Description
        -----------
        For given actuators speeds and displacements, linear interpolation of the closest four accuracy grid points is performed to 
        return an accuracy value for each of the four actuators.
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
            # Sign of displacement
            sign=1
            if disp[i] != 0:
                sign = np.sign(disp[i])
            # Simulation ranges of grid
            disp_range = sign*np.linspace(0.005,0.030,11)
            speed_range = np.geomspace(0.005/100,0.030,11)
            # Determining closest neighbouring grid points
            disp_diff = np.abs(disp_range - disp[i])
            speed_diff = np.abs(speed_range - speed[i])
            i1,i2 = sorted(range(len(disp_diff)), key=lambda sub: disp_diff[sub])[:2]
            j1,j2 = sorted(range(len(speed_diff)), key=lambda sub: speed_diff[sub])[:2]
            # Weights
            v1,v2 = [disp_diff[i1],disp_diff[i2]]/(disp_diff[i1]+disp_diff[i2])
            w1,w2 = [speed_diff[j1],speed_diff[j2]]/(speed_diff[j1]+speed_diff[j2])
            if sign > 0:
                # Accuracy interpolation
                a_disp = v1*accurgrid_pos[i1,j1]+v2*accurgrid_pos[i2,j1]
                a_speed = w1*accurgrid_pos[i1,j1]+w2*accurgrid_pos[i1,j2]
                # Average
                a_snap[i] = (a_disp+a_speed)/2
            if sign < 0:
                # Accuracy interpolation
                a_disp = v1*accurgrid_neg[i1,j1]+v2*accurgrid_neg[i2,j1]
                a_speed = w1*accurgrid_neg[i1,j1]+w2*accurgrid_neg[i1,j2]
                # Average
                a_snap[i] = (a_disp+a_speed)/2
        
        return a_snap

    def _get_actuator_pos(self,config):
        """
        Description
        -----------
        The function retrieves the current absolute on-bench actuator positions, for the specified configuration, by communication with opcua.
        
        Parameters
        ----------
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3)
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference)

        Returns
        -------
        pos : (1,4) numpy array of float values (mm)
            Current actuator positions for the specified configuration (=beam)

        """
    
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
    
        # Retrieving OPCUA url from config.ini
        configpars = ConfigParser()
        configpars.read('../../config.ini')
        url =  configpars['DEFAULT']['opcuaaddress']
        # Opening OPCUA connection
        opcua_conn = OPCUAConnection(url)
        opcua_conn.connect()
        # Retrieving actuator positions via OPCUA  
        pos1 = opcua_conn.read_node('ns=4;s=MAIN.nott_ics.TipTilt.NTTA'+str(config+1)+'.stat.lrPosActual')
        pos2 = opcua_conn.read_node('ns=4;s=MAIN.nott_ics.TipTilt.NTPA'+str(config+1)+'.stat.lrPosActual')
        pos3 = opcua_conn.read_node('ns=4;s=MAIN.nott_ics.TipTilt.NTTB'+str(config+1)+'.stat.lrPosActual')
        pos4 = opcua_conn.read_node('ns=4;s=MAIN.nott_ics.TipTilt.NTPB'+str(config+1)+'.stat.lrPosActual')
        pos = np.array([pos1,pos2,pos3,pos4],dtype=np.float64)
        # Closing OPCUA connection
        opcua_conn.disconnect()
        
        return pos
    
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
        d1_ca : TTM1 center-to-actuator distance (mm)
        d2_ca : TTM2 center-to-actuator distance (mm)

        Returns
        -------
        ttm_angles : (1,4) array of floats (radian)
            The TTM (TTM1X,TTM1Y,TTM2X,TTM2Y) angles.

        """
        # Center-to-actuator distances
        d1_ca = 2.5*25.4 
        d2_ca = 1.375*25.4
        # Zemax optimal coupling angles (rad)
        ttm_angles_optim = np.array([[0.10,32,-0.11,-41],[4.7,-98,4.9,30],[-2.9,134,-3.1,-107],[3.7,115,3.3,-141]],dtype=np.float64)*10**(-6)
        ttm_config = ttm_angles_optim[config]
        # Actuator positions in a state of alignment (TBC for configs other than two)  (mm)
        act_pos_align = np.array([[0,0,0,0],[5.17,5.44,3.41,3.845],[0,0,0,0],[0,0,0,0]],dtype=np.float64)
        act_config = act_pos_align[config]
    
        # TTM1X
        xsum_align = act_config[0]+act_config[1]
        xsum_input = pos[0]+pos[1]
        TTM1X = ttm_config[0] - np.arcsin((xsum_align-xsum_input)/(2*d1_ca))
        # TTM1Y
        xdiff_align = act_config[1]-act_config[0]
        xdiff_input = pos[1]-pos[0]
        TTM1Y = +ttm_config[1] + np.arcsin((xdiff_input-xdiff_align)/(2*d1_ca))
        # TTM2X
        TTM2X = ttm_config[2] - np.arcsin((pos[3]-act_config[3])/d2_ca)
        # TTM2Y
        TTM2Y = +ttm_config[3] + np.arcsin((pos[2]-act_config[2])/d2_ca)
        
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
        d1_ca : TTM1 center-to-actuator distance (mm)
        d2_ca : TTM2 center-to-actuator distance (mm)

        Returns
        -------
        pos : (1,4) numpy array of floats (mm)
            The actuator (x1,x2,x3,x4) positions.
        """
        # Center-to-actuator distances
        d1_ca = 2.5*25.4 
        d2_ca = 1.375*25.4
        # Zemax optimal coupling angles (rad)
        ttm_angles_optim = np.array([[0.10,32,-0.11,-41],[4.7,-98,4.9,30],[-2.9,134,-3.1,-107],[3.7,115,3.3,-141]],dtype=np.float64)*10**(-6)
        ttm_config = ttm_angles_optim[config]
        # Actuator positions in a state of alignment (TBC for configs other than two) (mm)
        act_pos_align = np.array([[0,0,0,0],[5.17,5.44,3.41,3.845],[0,0,0,0],[0,0,0,0]],dtype=np.float64)
        act_config = act_pos_align[config]
    
        # TTM1
        xsum_align = (act_config[0]+act_config[1])/2
        xdiff_align = (act_config[1]-act_config[0])/2
        xsum = xsum_align - d1_ca*np.sin(ttm_config[0]-ttm_angles[0])
        xdiff = xdiff_align - d1_ca*np.sin(ttm_config[1]-ttm_angles[1])
        x1 = xsum-xdiff
        x2 = xsum+xdiff
        
        # TTM2 
        x3 = act_config[2] - d2_ca*np.sin(ttm_config[3]-ttm_angles[3])
        x4 = act_config[3] + d2_ca*np.sin(ttm_config[2]-ttm_angles[2])
        
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
        
        Constants 
        ---------
        d1_ca : TTM1 center-to-actuator distance (mm)
        d2_ca : TTM2 center-to-actuator distance (mm)

        Remarks
        -------
        For the set of TTM1s : The two actuators are installed at 45° angles to the transverse X/Y dimensions.
                               Hence, to achieve TTM1X/TTM1Y angular offsets, the motion of the two actuators is necessarily coupled.
        For the set of TTM2s : The two actuators are installed in agreement with the transverse X/Y dimensions.
                               To achieve a TTM2X/TTM2Y angular offset, the corresponding actuator can act independently.
        Returns
        -------
        displacements : (1,4) numpy array of float values (mm)
            The actuator displacements (x1,x2,x3,x4) necessary to achieve the demanded angular offsets.
            dx1 : Displacement of the TTM1 actuator that is closest to the bench edge
            dx2 : Displacement of the TTM1 actuator that is furthest from the bench edge
            dx3 : Displacement of the TTM2 actuator whose motion is in the X plane, thus inducing TTM2 Y angles.
            dx4 : Displacement of the TTM2 actuator whose motion is in the Y plane, thus inducing TTM2 X angles.
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
            Absolute actuator positions.
        act_disp : (1,4) numpy array of floats (mm)
            Actuator displacements.

        Returns
        -------
        ttm_shifts : (1,4) numpy array of floats (rad)
            Induced TTM angular offsets 

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
        low_speed = np.array([0.005/100],dtype=np.float64)[0]
        up = np.array([0.030],dtype=np.float64)[0]
        bool_speed = np.logical_and(act_speed < low_speed,act_speed != 0).any() or (act_speed > up).any()
        if (bool_speed):
            raise ValueError("One/multiple speed value(s) are invalid. The supported speed range spans [0.05,30] um/s.")
        
        # Snap accuracies
        accur_snap = np.array(self._snap_accuracy_grid(act_speed,act_disp),dtype=np.float64)
        
        return accur_snap

    def _valid_state(self,bool_slicer,ttm_angles_final,act_displacements,act_pos,config):
        """
        Description
        -----------
        The function carries out several checks concerning the validity of a TTM configuration.
        A final configuration can be invalid in four ways:
            (1) The final configuration would displace the beam off the slicer.
            (2) The requested angular TTM offset is lower than what is achievable by the TTM resolution.
            --> In this case, the invalid displacements are not carried out, the others are.
            (3) The requested final TTM configuration is beyond the limits of what the actuator travel ranges can achieve
            (4) The requested final TTM configuration is beyond the current range supported by Dgrid (pm 1000 microrad for TTM1, pm 500 microrad for TTM2).
        Only a configuration that is not invalid in one of the four above ways will be considered as valid.

        Parameters
        ----------
        bool_slicer : single Boolean
            see individual_step
        ttm_angles_final : (1,4) numpy array of float values (radian)
            Final configuration of (TTM1X,TTM1Y,TTM2X,TTM2Y) angles
        act_displacements : (1,4) numpy array of float values (mm)
            Actuator displacements (dx1,dx2,dx3,dx4) necessary to go from TTM_init to TTM_final
        act_pos : (1,4) numpy array of float values (mm)
            Current absolute actuator positions (x1,x2,x3,x4) for the TTMs corresponding to beam "config"
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3)
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference)

        Returns
        -------
        Valid : A Boolean value denoting whether the final configurations is valid.
                Boolean True = valid , Boolean False = invalid
        i : a (1,4) numpy array of integers
            Indicates what conditions are violated by the configuration.
        disp_copy : (1,4) numpy array of floats
            New displacements (replaced by zero where condition three is invalid)

        """
    
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
    
        # Zemax optimal coupling angles 
        ttm_angles_optim = np.array([[0.10,32,-0.11,-41],[4.7,-98,4.9,30],[-2.9,134,-3.1,-107],[3.7,115,3.3,-141]],dtype=np.float64)*10**(-6)
        ttm_config = ttm_angles_optim[config]
    
        Valid = True
        i = np.array([0,0,0,0])
        
        disp_copy = act_displacements.copy()
        
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
        if (config == 1):
            valid1 = (TTM2Y_shift >= -TTM1Y_shift-587*10**(-6) and TTM2Y_shift <= -TTM1Y_shift+508*10**(-6))
        if (config == 2):
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
                disp_copy[j] = 0

        
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
                valid3 = (act_pos[j] >= disp)
    
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
        
        if not valid4:
            i[3] = 1
            Valid = valid4
    
        return Valid,i,disp_copy

    def _move_abs_ttm_act(self,init_pos,disp,speeds,pos_offset,config):
        """
        Description
        -----------
        The function moves all actuators (1,2,3,4) in a configuration "config" (=beam) by given displacements "disp", at speeds "speeds", taking into account offsets "pos_offset".
        Actuator naming convention within a configuration : 
            1 : TTM1 actuator that is closest to the bench edge
            2 : TTM1 actuator that is furthest from the bench edge
            3 : TTM2 actuator whose motion is in the X plane, thus inducing TTM2 Y angles.
            4 : TTM2 actuator whose motion is in the Y plane, thus inducing TTM2 X angles.
    
        Parameters
        ----------
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3)
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference)       
        init_pos : (1,4) numpy array of float values (mm)
            Positions from which the actuators should be moved.
        disp : (1,4) numpy array of float values (mm)
            Displacements by which the actuators should be moved.
        speeds : (1,4) numpy array of float values (mm/s)
            Speeds by which the actuators should move.
        pos_offset : (1,4) numpy array of float values (mm)
            offsets to be accounted for when moving.
            To be characterized on-bench.

        Returns
        -------
        None.

        """
        
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
        
        # Retrieving OPCUA url from config.ini
        configpars = ConfigParser()
        configpars.read('../../config.ini')
        url =  configpars['DEFAULT']['opcuaaddress']
        # Opening OPCUA connection
        opcua_conn = OPCUAConnection(url)
        opcua_conn.connect()
        # Actuator motor objects
        act1 = Motor(opcua_conn, 'ns=4;s=MAIN.nott_ics.TipTilt.NTTA'+str(config+1),'NTTA'+str(config+1))
        act2 = Motor(opcua_conn, 'ns=4;s=MAIN.nott_ics.TipTilt.NTPA'+str(config+1),'NTPA'+str(config+1))
        act3 = Motor(opcua_conn, 'ns=4;s=MAIN.nott_ics.TipTilt.NTTB'+str(config+1),'NTTB'+str(config+1))
        act4 = Motor(opcua_conn, 'ns=4;s=MAIN.nott_ics.TipTilt.NTPB'+str(config+1),'NTPB'+str(config+1))
        actuators = np.array([act1,act2,act3,act4])
        
        # Actuator names 
        act_names = ['NTTA'+str(config+1),'NTPA'+str(config+1),'NTTB'+str(config+1),'NTPB'+str(config+1)]
        
        # Desired final positions
        final_pos = init_pos + disp
        
        # Looping over all four actuators
        for i in range(0,4):
            start_time = time.time()

            # Only continue for actuators upon which displacement is imposed
            if (final_pos[i] != init_pos[i]):
                # Incorporating offsets
                final_pos[i] -= pos_offset[i] # in mm

                # Performing the movement
                #-------------------------#
                actuators[i].enable()
                time.sleep(0.050)
            
                # Executing move
                parent = opcua_conn.client.get_node('ns=4;s=MAIN.nott_ics.TipTilt.'+act_names[i])
                method = parent.get_child("4:RPC_MoveAbs")
                arguments = [final_pos[i], speeds[i]]
                parent.call_method(method, *arguments)
            
                # Wait for the actuator to be ready
                on_destination = False
                while not on_destination:
                    time.sleep(0.01)
                    status, state = opcua_conn.read_nodes(['ns=4;s=MAIN.nott_ics.TipTilt.'+act_names[i]+'.stat.sStatus', 'ns=4;s=MAIN.nott_ics.TipTilt.'+act_names[i]+'.stat.sState'])
                    on_destination = (status == 'STANDING' and state == 'OPERATIONAL')
                ach_pos = self._get_actuator_pos(config)[i]
                print("Moving actuator "+act_names[i]+" from "+str(init_pos[i])+" to "+str(final_pos[i])+" at speed "+str(speeds[i])+" mm/s took "+str(np.round(time.time()-start_time,2))+" seconds and achieved position ", str(ach_pos))
            
        # Close OPCUA connection
        opcua_conn.disconnect()
        return

    ###################
    # Individual Step #
    ###################

    def individual_step(self,bool_slicer,sky,steps,speeds,config):
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

        Parameters
        ----------
        bool_slicer : single boolean
            True : individual_step is called by a method that displaces the beam off the slicer (localization spiral)
            False : individual_step is called by a method that should not displace the beam off the slicer (optimization)
        sky : single integer
            sky == 0 : User specifies desired (dX,dY,dx,dy) shifts in the CS(X,Y) and IM(x,y) plane
            sky == 1 : User specifies on-sky angular shifts (dskyX,dskyY) and wishes for TTM1 to facilitate this on-sky shift while keeping the CS position fixed.
            sky == -1 : User specifies on-sky angular shifts (dskyX,dskyY) and wishes for TTM1 to facilitate this on-sky shift while keeping the IM position fixed. 
        steps : (1,4) numpy array of float values
            sky == 0 : steps = (dX,dY,dx,dy)
            sky != 0 : steps = (dskyX,dskyY,0,0)
        speeds : (1,4) numpy array of float values
            Speeds by which the actuators (1,2,3,4) will move (mm/s)
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3)
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference) 

        Returns
        -------
        None.

        """
        
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
    
        # Register current actuator displacements
        act_curr = self._get_actuator_pos(config)
        
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
            print("This step would lead to CS(X,Y) and IM(x,y) shifts (dX,dY,dx,dy) = ",shifts_par)
        else:
            TTM_offsets = self._framework_numeric_int(steps,D_arr,1) # Current Dgrid only supports central wavelength
            print("This step would lead to CS(X,Y) and IM(x,y) shifts (dX,dY,dx,dy) = ",steps)
        
        # Calculating the necessary actuator displacements
        act_disp = self._ttm_shift_to_actuator_displacement(TTM_curr,TTM_offsets,config)
    
        # Final TTM configuration
        TTM_final = TTM_curr + TTM_offsets
    
        # Before imposing the displacements to the actuators, the state validity is checked.
        valid,cond,act_disp = self._valid_state(bool_slicer,TTM_final,act_disp,act_curr,config)
        if not valid:
            raise ValueError("The requested change does not yield a valid configuration. Out of conditions (1,2,3,4) the ones in following array indicate what conditions were violated : "+str(cond)+
                            "\n Conditions :\n (1) The final configuration would displace the beam off the slicer."+
                            "\n (2) The requested angular TTM offset is lower than what is achievable by the TTM resolution."+
                            "\n (3) The requested final TTM configuration is beyond the limits of what the actuator travel ranges can achieve."+
                            "\n (4) The requested final TTM configuration is beyond the current range supported by Dgrid (pm 1000 microrad for TTM1, pm 500 microrad for TTM2).")
    
        # Only push actuator motion if it would yield a valid state
        if valid:
            pos_offset = self._actoffset(speeds,act_disp) 
            self._move_abs_ttm_act(act_curr,act_disp,speeds,pos_offset,config)
            print("Step performed")
        
        return
   
    ############
    # Scanning #
    ############    

    def localization_spiral(self,sky,step,speed,config):
        """
        Description
        -----------
        The function traces a square spiral in the user-specified plane (either image or on-sky plane) to locate the internal beam / on-sky source.
        Once a point in the spiral yields a camera average > 5 * Noise, the spiral is stopped.
        For on-sky spiralling, a time out is incorporated. Once the spiral arm reaches a dimension of 10*step, the spiralling procedure is quit.
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
            If sky == False : dummy parameter, 20 micron (waveguide dimension) is taken by default.
        speed : single float value
            Actuator speed by which a spiral step should occur
            Note: Parameter to be removed once an optimal speed is recovered (which balances efficiency and accuracy)
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3)
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference) 

        Returns
        -------
        None.
        
        """
        
        if sky:
            sky = 1
        else:
            sky = 0
        
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
        
        if (speed > 2.32*10**(-3) or speed <= 0):
            raise ValueError("Given actuator speed is beyond the accepted range (0,30] um/s")
        
        if sky : 
            d = step
        else:
            d = 20*10**(-3) #(mm)
        
        # REDIS field names of photometric outputs' ROIs
        names = ["roi1_avg","roi2_avg","roi7_avg","roi8_avg"]
        fieldname = names[config]
        
        # Initial position noise measurement
        t_start,t_stop = define_time(0.100) # 100 ms back in time
        noise = get_field("roi9_avg",t_start,t_stop,True)[1] # Index 1 to get the temporal mean of spatial mean roi9_avg
        # Initial position photometric output measurement
        photoconfig = get_field(fieldname,t_start,t_stop,True)[1]
    
        if (photoconfig > 5*noise):
            raise Exception("Localization spiral not started. Initial configuration is already in a state of injection (photometric output > 5*noise).")
                           
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
        # Boundary stop condition for on-sky spiralling
        Nsteps_skyb = 10
        
        while not stop:
        
            # Carrying out step(s)
            for i in range(0,Nsteps):
                # Step
                speeds = np.array(np.ones(4)*speed, dtype=np.float64)
                self.individual_step(True,sky,moves[move],speeds,config)
                # REDIS writing time
                time.sleep(0.110)
                # New position noise measurement
                t_start,t_stop = define_time(0.100) # 100 ms back in time
                noise = get_field("roi9_avg",t_start,t_stop,True)[1] # Index 1 to get the mean roi9 value
                # New position photometric output measurements
                photoconfig = get_field(fieldname,t_start,t_stop,True)[1]
                
                if (photoconfig > 5*noise):
                    print("A state of injection (photo > 5*noise) has been reached.")
                    return
                
            # Setting up next move
            if move < 3:
                move += 1
            else:
                move = 0
            
            # Counting the amount of performed move type switches
            Nswitch += 1
        
            if (Nswitch % 2 == 0):
                Nsteps += 1
            
            # Implementing boundary stop condition for on-sky spiralling
            if (sky and Nsteps >= Nsteps_skyb):
                raise TimeoutError("The on-sky spiral scanning algorithm timed out. Consider repointing closer to source.")
            
        return

    def optimization_spiral(self,sky,step,speed,config):
        """
        Description
        -----------
        The function traces a square spiral in the user-specified plane (either image or on-sky plane).
        The spiral is stopped once it has covered an area that is two steps wide in each direction (up,down,left,right).
        For each point along the spiral, the corresponding TTM configuration and camera average is stored.
        The brightness-weighted TTM configuration is calculated and pushed to the bench by inducing the necessary actuator motion.
        
        Parameters
        ----------
        sky : single boolean
            If True : spiral on-sky
            If False : spiral in image plane
        step : single float value
            The dimension by which the spiral should make its steps.
            If sky == True : on-sky angular step (radian) 
            If sky == False : dummy parameter, 5 micron is taken by default.
        speed : single float value
            Actuator speed by which a spiral step should occur
            Note: Parameter to be removed once optimal speed is obtained.
        config : single integer
            Configuration number (= VLTI input beam) (0,1,2,3)
            Nr. 0 corresponds to the innermost beam, Nr. 3 to the outermost one (see figure 3 in Garreau et al. 2024 for reference) 

        Remarks
        -------
        The function is expected to be called after the "localization_spiral" function has been called. It is thus expected that a first, broad-scope alignment has already been performed.
        If sky == True : Before calling this function, it is expected that the TTMs have already been aligned such that the on-sky source is imaged onto the chip input.
        If sky == False : Before calling this function, it is expected that the TTMs have already been aligned such that the internal VLTI beam is injected into the chip input.

        Returns
        -------
        None.

        """
        
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")
        
        if (speed > 1.22*10**(-3) or speed <= 0):
            raise ValueError("Given actuator speed is beyond the accepted range (0,1.22] um/s")
        
        if sky : 
            d = step
        else:
            d = 5*10**(-3) #(mm)
                
        # Exposures
        exps = []
        # TTM configs 
        TTM = []
      
        # REDIS field name of relevant ROI
        names = ["roi1_avg","roi2_avg","roi7_avg","roi8_avg"]
        fieldname = names[config]
            
        t_start,t_stop = define_time(0.100) # 100 ms back in time
        # Initial position photometric output measurement
        photoconfig = get_field(fieldname,t_start,t_stop,True)[1]
        # Adding to the stack of exposures
        exps.append(photoconfig)
    
        # Storing initial TTM configuration
        act_curr = self._get_actuator_pos(config)
        TTM_curr = self._actuator_position_to_ttm_angle(act_curr,config)
        TTM.append(TTM_curr)
    
        #                          STOP
        #                           x
        #                           |
        #           x---x---x---x   x
        #           |           |   |
        #           x   x---x   x   x
        ##########  |   |   |   |   |
        # Spiral #  x   x   x   x   x
        ##########  |   |       |   |
        #           x   x---x---x   x
        #           |               |
        #           x---x---x---x---x    
        
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
        
            # Carrying out step(s)
            for i in range(0,Nsteps):
                # Step
                speeds = np.array(np.ones(4)*speed, dtype=np.float64)
                self.individual_step(False,sky,moves[move],speeds,config)
                # REDIS writing time
                time.sleep(0.110)
                # Storing camera value and TTM configuration
                # 1) Camera value
                t_start,t_stop = define_time(0.100) # 100 ms back in time
                photoconfig = get_field(fieldname,t_start,t_stop,True)[1]
                # Adding to the stack of exposures
                exps.append(photoconfig)
                # 2) TTM configuration
                act_curr = self._get_actuator_pos(config)
                TTM_curr = self._actuator_position_to_ttm_angle(act_curr,config)
                TTM.append(TTM_curr)
        
            # Setting up next move
            if move < 3:
                move += 1
            else:
                move = 0
            
            # Stop condition
            if (Nsteps == 5):
                stop = True
            
            # Counting the amount of performed move type switches
            Nswitch += 1
        
            if (Nswitch % 2 == 0):
                Nsteps += 1
        
        # Calculating the brightness-weighted configuration
        exp_total = np.sum(exps)
    
        # Brightness-weighting
        TTM_final = np.array([0,0,0,0],dtype=np.float64)
        for i in range(0, len(exps)):
            TTM_final += (exps[i] / exp_total)*TTM[i]
        
        # Bringing the bench to the brightness-weighted final position
        TTM_start = TTM[-1] # current configuration
        TTM_shifts = TTM_final - TTM_start
        
        act_disp = self._ttm_shift_to_actuator_displacement(TTM_start,TTM_shifts,config)
        act_curr = self._get_actuator_pos(config)
        act_final = act_curr + act_disp
        
        speeds = np.array([0.01,0.01,0.01,0.01],dtype=np.float64) #TBD
        pos_offset = self._actoffset(speeds,act_disp) 
        
        # Carrying out the motion
        self._move_abs_ttm_act(act_curr,act_disp,speed,pos_offset,config)
            
        return
    
    ##########################################
    # Performance characterization / Testing #
    ##########################################
    
    def cam_read_test(self,config):
    # Function to test the readout of the camera ROIs from the REDIS database
        
        if (config < 0 or config > 3):
            raise ValueError("Please enter a valid configuration number (0,1,2,3)")    
    
        # REDIS field names of photometric outputs' ROIs
        names = ["roi1_avg","roi2_avg","roi7_avg","roi8_avg"]
        fieldname = names[config]
        # Readout 100 ms back in time
        t_start,t_stop = define_time(0.100) 
        # Current position noise measurement
        noise = get_field("roi9_avg",t_start,t_stop,True)[1] # Index 1 to get the temporal mean of spatial mean roi9_avg
        # Current position photometric output measurement
        photoconfig = get_field(fieldname,t_start,t_stop,True)[1]
        # Print out values
        print("Current noise (ROI9) average : ", noise)
        print("Demanded photometric output average : ", photoconfig)
        return
    
    # All functions below serve purpose in the context of actuator performance characterization
    # Characterization is done with actuator act_name
    
    def _move_abs_ttm_act_single(self,pos,speed,act_name,offset,config=1):        

        start_time = time.time()
        # Retrieving OPCUA url from config.ini
        configpars = ConfigParser()
        configpars.read('../../config.ini')
        url =  configpars['DEFAULT']['opcuaaddress']
        # Opening OPCUA connection
        opcua_conn = OPCUAConnection(url)
        opcua_conn.connect()
        # Actuator names 
        act_names = ['NTTA'+str(config+1),'NTPA'+str(config+1),'NTTB'+str(config+1),'NTPB'+str(config+1)]
        # Index of act_name
        act_index = 0
        for i in range(0, 4):
            if act_names[i] == act_name:
                act_index = i
        # Actuator motor object 
        act = Motor(opcua_conn, 'ns=4;s=MAIN.nott_ics.TipTilt.'+act_name,act_name)
        
        # List of time stamps
        time_arr = []
        # List of positions
        pos_arr = []
        # Performing the movement
        #-------------------------#
        # Preparing actuator (sleep times TBD)
        #act.reset()
        #time.sleep(0.100)
        #act.init()
        #time.sleep(0.050)
        act.enable()
        time.sleep(0.050)
            
        # Current position
        curr_pos = self._get_actuator_pos(config)[act_index]
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
            # Printing status, state and saving position & time every 10 ms (=2xREDIS sampling)
            time.sleep(0.01)
            status, state = opcua_conn.read_nodes(['ns=4;s=MAIN.nott_ics.TipTilt.'+act_name+'.stat.sStatus', 'ns=4;s=MAIN.nott_ics.TipTilt.'+act_name+'.stat.sState'])
            #print("Status:", status, "|| State:", state)
            on_destination = (status == 'STANDING' and state == 'OPERATIONAL')
            #print(act_name+" pos: ", str(self._get_actuator_pos(config)[3])+" mm")
            # Save current time
            time_arr.append(time.time())
            # Save current position
            pos_arr.append(self._get_actuator_pos(config)[3])
                
        # Time spent
        end_time = time.time()
        spent_time = end_time-start_time
        # ACTUAL Position achieved
        final_pos = self._get_actuator_pos(config)[3]
        print("----------------------------------------------------------------------------------------------------------------------------")
        print("Moving actuator "+act_name+" from "+str(curr_pos)+" mm to "+str(imposed_pos)+" mm at speed "+str(speed)+" mm/s took "+str(spent_time)+" seconds")
        print("Actual actuator position reached :"+str(final_pos)+" mm")
        print("----------------------------------------------------------------------------------------------------------------------------")   
        # Close OPCUA connection
        opcua_conn.disconnect()
        
        return spent_time,imposed_pos,final_pos,time_arr,pos_arr
    
    def act_response_test_single(self,act_displacement,speed,act_name,offset,config=1):
        # Function to probe the actuator response (x,t) for given speed and displacement
        
        # STEP 1 : Reset actuator position if begin/end is reached (depending on the direction) and neutralize backlash
        # Current position (index 3 for NTPB)
        curr_pos = self._get_actuator_pos(config)[3]
        pos_backlash = curr_pos
        # Actuator travel range [0,6] mm
        act_range = 6 
        # Validity booleans
        valid_end = True
        valid_start = True
        # Exceeding upper limit of range?
        if act_displacement > 0:
            valid_end = (act_range - curr_pos >= act_displacement)
        # Exceeding lower limit of range?
        else:
            valid_start = (curr_pos >= -act_displacement)
        
        if not valid_end:
            # Reset to start position
            curr_pos = 0.1
            # Neutralize backlash by imposing 2 micron shift (=10xresolution)
            pos_backlash = curr_pos+2*10**(-3)
        if not valid_start:
            # Reset to end position
            curr_pos = act_range-0.1
            # Neutralize backlash by imposing 2 micron shift (=10xresolution)
            pos_backlash = curr_pos-2*10**(-3)
            
        # Impose the reset (motions need not be accurate here ==> fast speed)
        if not valid_start or not valid_end:
            # Resetting actuator
            _,_,_,_,_ = self._move_abs_ttm_act_single(curr_pos,0.2,act_name,False)
            # Neutralizing backlash
            _,_,_,_,_ = self._move_abs_ttm_act_single(pos_backlash,0.001,act_name,False)
            print("Actuator range reset, backlash neutralized")
          
        # STEP 2: Imposing the desired actuator displacement
        curr_pos = self._get_actuator_pos(config)[3]
        imposed_pos_d = curr_pos + act_displacement
        spent_time,imposed_pos,final_pos,time_arr,pos_arr = self._move_abs_ttm_act_single(imposed_pos_d,speed,act_name,offset)
        
        return np.array([spent_time,imposed_pos,final_pos],dtype=np.float64),time_arr,pos_arr

    def act_response_test_multi(self,act_displacements,len_speeds,act_name,offset,config=1):
        # Function to probe the actuator response for a range of displacements and speeds
        # !!! To be used for displacements in ONE CONSISTENT DIRECTION (i.e. only positive / only negative displacements)
        
        # Actuator names 
        act_names = ['NTTA'+str(config+1),'NTPA'+str(config+1),'NTTB'+str(config+1),'NTPB'+str(config+1)]
        # Index of act_name
        act_index = 0
        for i in range(0, 4):
            if act_names[i] == act_name:
                act_index = i
        
        # Bring actuator to middle of range
        init_pos = self._get_actuator_pos(config)[act_index]
        init_disp = 3 - init_pos
        _ = self.act_response_test_single(init_disp,0.1,act_name,False)
        
        # Matrix containing time spent moving actuators, actuator accuracy (achieved-imposed) and image shift accuracy (achieved-imposed) for all displacement x speed combinations
        matrix_acc = np.zeros((6,len(act_displacements),len_speeds))
        # Lists containing time and position series of the movement
        times = []
        positions = []
        # Carrying out the test for each combination
        for i in range(0, len(act_displacements)):
            disp = act_displacements[i] #mm
            speeds = np.geomspace(0.005/100,0.030,len_speeds) #mm/s #logspace
            for j in range(0, len(speeds)):
                acc_arr,time_arr,pos_arr = self.act_response_test_single(act_displacements[i],speeds[j],act_name,offset)
                matrix_acc[0][i][j] = acc_arr[0]
                matrix_acc[1][i][j] = acc_arr[2]-acc_arr[1]
                times.append(time_arr)
                positions.append(pos_arr)
                
                # Calculating ttm shift accuracy from actuator displacement accuracy
                act_acc = acc_arr[2]-acc_arr[1]
                curr_pos = self._get_actuator_pos(config)
                act_disp = np.array([0,0,0,act_acc],dtype=np.float64)
                
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
    
    def act_backlash_test_multi(self,act_displacements,len_speeds,act_name,config=1):
        # Function to probe the backlash, remaining after incorporation of the empirical actuator offsets, for a range of displacements and speeds.
        # For each speed v and displacement dx, the actuator is moved by \pm dx at speed v and then the same displacement is reversed. The backlash is
        # characterised by how well the initial position (before any displacement) and the final position (after two displacements) agree.
        
        # Actuator names 
        act_names = ['NTTA'+str(config+1),'NTPA'+str(config+1),'NTTB'+str(config+1),'NTPB'+str(config+1)]
        # Index of act_name
        act_index = 0
        for i in range(0, 4):
            if act_names[i] == act_name:
                act_index = i
        
        # Bring actuator to middle of range
        init_pos = self._get_actuator_pos(config)[act_index]
        init_disp = 3 - init_pos
        _ = self.act_response_test_single(init_disp,0.1,act_name,False)
        # Matrix containing time spent moving actuators, backlash (final pos - initial pos) and image shift accuracy (final-initial) for all displacement x speed combinations
        matrix_acc = np.zeros((6,len(act_displacements),len_speeds))
        # Carrying out the test for each combination
        for i in range(0, len(act_displacements)):
            disp = act_displacements[i] # mm
            speeds = np.geomspace(0.005/100,0.030,len_speeds) #mm/s #logspace
            for j in range(0, len(speeds)):
                # Current position
                init_pos = self._get_actuator_pos(config)[act_index]
                # Step 1
                arr1,_,_ = self.act_response_test_single(act_displacements[i],speeds[j],act_name,True)
                # Step 2
                arr2,_,_ = self.act_response_test_single(-act_displacements[i],speeds[j],act_name,True)
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
                curr_pos = self._get_actuator_pos(config)
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
    