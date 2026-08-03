import numpy as np
import os

class DataFiles:
    def __init__(self, path):
        self.deltas_per_wl = np.load(os.path.join(path, "deltas_per_wl.npy"))
        self.deltas_per_wl_std = np.load(os.path.join(path, "deltas_per_wl_std.npy"))
