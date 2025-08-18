import numpy as np
import os

class DataFiles:
    def __init__(self, path):
        # Zemax-simulated inter-component distance grid
        self.Dgrid = np.load(os.path.join(path,"TTMgrids/Dgrid.npy"))
        # Absolute TTM angles by which the grid of distance values (Dgrid) is simulated
        self.TTM1Xgrid = np.load(os.path.join(path, "TTMgrids/Grid_TTM1X.npy"))
        self.TTM1Ygrid = np.load(os.path.join(path, "TTMgrids/Grid_TTM1Y.npy"))
        self.TTM2Xgrid = np.load(os.path.join(path, "TTMgrids/Grid_TTM2X.npy"))
        self.TTM2Ygrid = np.load(os.path.join(path, "TTMgrids/Grid_TTM2Y.npy"))
        # On-bench simulated accuracy grid (achieved-imposed) for positive/negative displacements
        self.accurgrid_pos = np.load(os.path.join(path, "Grid_Accuracy_Pos.npy"))
        self.accurgrid_neg = np.load(os.path.join(path, "Grid_Accuracy_Neg.npy"))
