""" Basic math functions used by the NOTT control code """

# Import functions
import numpy as np

def compute_mean_sampling(vector):
    """ Compute mean sampling frequency of a given (time) vector """
    delta_ts = np.diff(vector)
    mean_delta_ts = np.mean(delta_ts)
    mean_fs = 1 / mean_delta_ts
    return mean_fs