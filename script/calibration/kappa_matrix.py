import sys

# Add the path to sys.path
sys.path.append('C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/lib/')
import time
from datetime import datetime, timedelta
from nott_control import shutter_close, shutter_open
import numpy as np


redis_url = 'redis://10.33.178.176:6379'

# =============================================================================
# TODO: measure visibility
# =============================================================================
import nott_control
from nott_database import define_time, get_field

    
def build_kappa_matrix(delay, shutter_radiation, n_aper, fields, return_throughput):
    """
    Build the kappa matrix.
    This matrix calculates the splitting ratios of the combiner.
    These ratios can be normalised by the flux of the incoming beam or the sum of all the outputs.
    The process consists of closing all the shutters and open them one by one while recording the flux in the outputs.

    The flux received is biased by:
        - ambient thermal background
        - the detector noise
        - thermal emission of the shutters
        
    The two first ones are acquired with a ROI located in a plain area on the detector.
    The last one must be measured separately.

    Parameters
    ----------
    delay : float
        Acquisition time during which the shutter is open, in second.
    shutter_radiation : array
        Thermal radiation of the shutters
    n_aper : int
        Number of apertures of the combiner
    fields : list
        Name of the ROI fields of the camera to grab from the database
    return_throughput : bool
        If `True`, normalise the column of the matrix by its sum, and it is the splitting ration. If `False`, it is normalised by the flux on the corresponding photometric output: it directly gives the contribution of a beam in a given output, knowing the flux in its photometric output.

    Returns
    -------
    kappa_mat : 2d-array
        Kappa matrix of the combiner

    Notes
    -----
    Estimator of the flux in the outputs :math:`O_i` given one beam injected :math:`I_A` :

    :math:`O_i = \kappa_{A,i} \times I_A + DetBg + \sum_{k ≠ A} Sh_{k, O_i}`

    where :
        - :math:`\kappa_{A,i}` is the kappa coefficient to determine
        - :math:`DetBg` is the sum of the detector noise and the thermal background, gotten from an ROI of the detector with no signal
        - :math:`Sh_{k, O_i}` is the thermal emission of the shutter `k` collected on the output :math:`O_i`. This bias is to determine and to be removed

    To remove the contribution of all the other shutters, we have to close all the shutters to get the flux in the outputs:

    :math:`O^c_i = DetBg^c + Sh_{A, O_i} + \sum_{k ≠ A} Sh_{k, O_i}`

    Thus:
    
    :math:`O_i = \kappa_{A,i} \times I_A + DetBg + O^c_i -  DetBg^c - Sh_{A, O_i}`

    with :math:`Sh_{A, O_i}` the thermal emission of the aperture `A` and :math:`O^c_i` the flux in the output `i` when all the shutters are closed.
    It is given by the function ``get_shutter_radiation``.

    Finally, the kappa coefficients is given by:

    :math:`\kappa_{A,i} \times I_A = O_i - DetBg - (O^c_i -  DetBg^c - Sh_{A, O_i})`, that has to be normalised by `I_A` (see top of the description).
    """

    # startend = time1
    
    kappa_mat = []
    beams_pos_in_output = [0, 1, 6, 7]

    for sh in range(n_aper):
        # Measure of the bias induced by the thermal emission of all shutters and measure the flux on the outputs of the chip
        nott_control.all_shutters_close(n_aper)

        time.sleep(delay)
        start, end = define_time(delay)
        time.sleep(delay) # Wait for the lag between the camera and the database
        
        fluxes_shutters_closed = [get_field(elt, start, end, True)[1] for elt in fields]
        fluxes_shutters_closed = np.array(fluxes_shutters_closed)

        detbg_shutters_closed = fluxes_shutters_closed[-1] # Ambient thermal background and detector noise
        fluxes_shutters_closed = fluxes_shutters_closed[:-1] # Flux at the outputs
        
        # Open one shutter and measure the flux on the outputs of the chip
        print('Open shutter', sh+1, '...')
        shutter_open(str(sh+1))
        time.sleep(delay)
        start, end = define_time(delay)    
        time.sleep(delay) # Wait for the lag between the camera and the database

        fluxes = [get_field(elt, start, end, True)[1] for elt in fields]
        fluxes = np.array(fluxes)

        detbg = fluxes[-1] # Ambient thermal background and detector noise
        fluxes = fluxes[:-1] # Flux at the outputs
        
        # Estimator of the kappa coefficients
        kappa_col = fluxes - detbg - (fluxes_shutters_closed - detbg_shutters_closed) + shutter_radiation[sh]
        
        # Normalisation of the kappa coefficients
        if return_throughput:
            kappa_col /= kappa_col.sum()
        else:
            kappa_col /= kappa_col[beams_pos_in_output[sh]]
            
        kappa_mat.append(kappa_col)

        shutter_close(str(sh+1))
        
    kappa_mat = np.array(kappa_mat)
    kappa_mat = kappa_mat.T
    
    return kappa_mat

def get_shutter_radiation(n_aper, delay, fields):
    """
    Measure the thermal radiation of the shutters, individually, in all the outputs.

    Parameters
    ----------
    n_aper: int
        Number of apertures
    delay: float
        Time range to grab, in second
    fields: list
        Name of the ROI to grab from the database.

    Returns
    -------
    shutter_rads: array
        Thermal emission of a given aperture (row) in all the outputs (columns)

    Notes
    -----
    Estimator of the thermal radiation of the shutter `A` in output `i`:

    :math:`Sh_{A,i} = O_{A,i} - detbg - (O^o_{A,i} - detbg^o)`

    with:
        - :math:`O_{A,i}` the flux in the output `i` when only the aperture `A` is closed
        - `detbg` the detector noise and ambient thermal background, measured in a ROI with no signal, when the aperture `A` is closed the others are closed
        - :math:`O^o_{A,i}` the flux in the output `i` when only the aperture `A` and the other ones are open
        - :math:`detbg^o` the detector noise and ambient thermal background, measured in a ROI with no signal, when the aperture `A` is open
    """

    shutter_rads = []

    nott_control.all_shutters_open(n_aper)
    for sh in range(n_aper):
        # Measure of the bias induced by the background and measure the flux on the outputs of the chip, when all the apertures are open

        time.sleep(delay)
        start, end = define_time(delay)
        time.sleep(delay) # Wait for the lag between the camera and the database

        fluxes_bg = [get_field(elt, start, end, True)[1] for elt in fields]
        fluxes_bg = np.array(fluxes_bg)        
        shift_bg = fluxes_bg[-1]
        fluxes_bg = fluxes_bg[:-1]
        
        # Close one shutter and measure the flux on the outputs of the chip
        print('Close shutter', sh+1, '...')
        shutter_close(str(sh+1))
        time.sleep(delay)
        start, end = define_time(delay)    
        time.sleep(delay)    # Wait for the lag between the camera and the database     
        
        fluxes = [get_field(elt, start, end, True)[1] for elt in fields]
        fluxes = np.array(fluxes)       
        detbg = fluxes[-1]
        fluxes = fluxes[:-1]

        
        shutter_rad = fluxes - detbg - (fluxes_bg - shift_bg)
        
        shutter_rads.append(shutter_rad)

        # Reopen the aperture
        shutter_open(str(sh+1))
        print('Done')
        
        
    shutter_rads = np.array(shutter_rads)
    
    return shutter_rads


P1='roi1_avg' # define all the ROI output
P2='roi2_avg'
I1='roi3_avg'
I2='roi4_avg'
I3='roi5_avg'
I4='roi6_avg'
P3='roi7_avg'
P4='roi8_avg'
detbg='roi9_avg'
fields = [P1, P2, I1, I2, I3, I4, P3, P4, detbg]

delay = 2
n_aper = 4
return_throughput = False

nott_control.all_shutters_open(n_aper)

# duration = 2.
# time.sleep(0.5)
# start, end = define_time(duration)
# time.sleep(0.5)
# flux = get_field(P1, start, end, False)

# print(flux)

# print('Block the source and press Enter to continue')
# input()
# print('NEW: Measuring shuter radiations')
# shutters_radiation = get_shutter_radiation(n_aper, delay, fields)
# print('Done')
# print('Unblock the source and press Enter to continue')
# input()
# print('NEW: Measuring kappa matrix')
# kappa = build_kappa_matrix(delay, shutters_radiation, n_aper, fields, return_throughput)
# print('Done')
# print(kappa.shape)
# np.save('kappa', kappa)
# print(kappa)

# print('THROUGHPUT')
# print('Block the source and press Enter to continue')
# input()
# print('NEW: Measuring shuter radiations')
# shutters_radiation = get_shutter_radiation(n_aper, delay, fields)
# print('Done')
# print('Unblock the source and press Enter to continue')
# input()
# print('NEW: Measuring kappa matrix')
# kappa = build_kappa_matrix(delay, shutters_radiation, n_aper, fields, True)
# print('Done')
# print(kappa.shape)
# np.save('kappa_throughput', kappa)
# print(kappa)

# print('Recup')
# import pickle
# import os

# def save_data(data, path, name):
#     print('MSG - Save data in:', path+name)
#     list_saved_files = [elt for elt in os.listdir(path) if name in elt]
#     count_file = len(list_saved_files) + 1
#     name_file = name+'_%03d.pkl'%(count_file)
#     dbfile = open(path + name_file, 'wb')
#     pickle.dump(data, dbfile)
#     dbfile.close()

# path = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/calibration/'
# name = 'kappa_matrix_ts'
# start = datetime(2024, 9, 5, 12, 56, 00)
# end = datetime(2024, 9, 5, 12, 58, 30)

# start = round(start.timestamp()*1000)
# end = round(end.timestamp()*1000)

# dic_data = {}

# for f in fields:
#     out = get_field(f, start, end, False)
#     dic_data[f] = out

# save_data(dic_data, path, name)