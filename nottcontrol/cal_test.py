
import numpy as np
from nottcontrol.script.wav_calib.wavelength_calib import run_wavelength_calibration

fit_out = run_wavelength_calibration(
    label="quick_wav_test",
    roi_indices=[0, 1, 6, 7],
    dt=8.0,
    n=1,
    setup_dt=5.0,
    use_geom=True,
)

print("time:", fit_out["calibration_time"])
print("summed channels:", fit_out["summed_channels"])
print("edges:", fit_out["y_hp1_obs"], fit_out["y_hp2_obs"])
print("fit:", fit_out["p0_fit"], fit_out["i1_deg_fit"], fit_out["theta_cam_fit"])
print("residuals:", fit_out["m1"], fit_out["m2"])
print("success:", fit_out["optimizer_success"])

pixels = np.arange(fit_out["output_height"])
lambs_um = fit_out["pixel_to_lambda"](pixels)

print("output_height:", fit_out["output_height"])
print("lambda min/max:", np.nanmin(lambs_um), np.nanmax(lambs_um))
print("finite pixels:", np.isfinite(lambs_um).sum())

# check useful science-band pixels
science = (lambs_um >= 3.5) & (lambs_um <= 4.0)

print("science pixels:", np.where(science)[0])
print("science wavelengths:", lambs_um[science])
print("number of science pixels:", np.sum(science))
