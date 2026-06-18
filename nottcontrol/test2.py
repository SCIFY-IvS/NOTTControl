import numpy as np
from nottcontrol.components.human_interface import HumInt


class dummy_piezo:
    def raw2values(self, vals):
        return np.array([vals])

    def send(self, *args, **kwargs):
        pass


myint2 = HumInt(interf=dummy_piezo())

myint2.load_spectral_cal(
    cal_file="/data/filepath2/wav_cal_latest.fits"
)

print("loaded lambs shape:", myint2.lambs.shape)
print("loaded lambs min/max [um]:", myint2.lambs.min(), myint2.lambs.max())
print("loaded science pixels:", np.where(myint2.sc_mask)[0])
print("loaded number of science pixels:", np.sum(myint2.sc_mask))