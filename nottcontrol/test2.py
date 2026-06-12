import numpy as np
from nottcontrol.components.human_interface import HumInt



class dummy_piezo:
    def raw2values(self, vals):
        return np.array([vals])

    def send(self, *args, **kwargs):
        pass



myint = HumInt(interf=dummy_piezo())

fit_out = myint.solve_spectral_cal_prism(
    label="human_interface_test",
    roi_indices=[0, 1, 6, 7],
    dt=8.0,
    n=1,
    setup_dt=5.0,
)

print("success:", fit_out["optimizer_success"])
print("edges:", fit_out["y_hp1_obs"], fit_out["y_hp2_obs"])
print("fit:", fit_out["p0_fit"], fit_out["i1_deg_fit"], fit_out["theta_cam_fit"])

print("lambs shape:", myint.lambs.shape)
print("lambs min/max [um]:", np.nanmin(myint.lambs) * 1e6, np.nanmax(myint.lambs) * 1e6)
print("science pixels:", np.where(myint.sc_mask)[0])
print("number of science pixels:", np.sum(myint.sc_mask))