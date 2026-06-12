import numpy as np
from scipy.optimize import least_squares
from scipy.interpolate import interp1d

from .diagnostics_to_edges import get_observed_edges_from_diagnostics
from .analytical_solution import run_analytical_solution


# -----------------------------------------------
# User inputs
# ------------------------------------------------

# Selected ROIs to sum for edge extraction.
# 0-based indices. For example [0, 1, 6, 7] usually corresponds to P1, P2, P3, P4.
ROI_INDICES = [0, 1, 6, 7]

SETUP_DT = 5.0


# -----------------------------------------------
# Filter edge extraction settings
# ------------------------------------------------

BASELINE_N = 12
SMOOTH_METHOD = "savgol"
SAVGOL_WINDOW = 9
SAVGOL_POLY = 2
MOVAVG_WINDOW = 7


# ---------------------------------------------------------
# Analytical model settings (i1 and cam angle varied)
# ----------------------------------------------------------

LAM_MIN = 3.440
LAM_MAX = 4.075
N_POINTS = 2000

A_DEG = 60.0
I1_DEG_INITIAL = 35

F_MM = 50.0
PIXEL_PITCH_UM = 15.0
P0_INITIAL = 250.0
THETA_CAM_INITIAL = -30.0
SIGN_OUT = -1


# -------------------------------------------
# Fit Options 
# -------------------------------------------

FIT_I1 = True         # False -> do not fit i1_deg
FIT_THETA_CAM = False   # False -> do not fit theta_cam_deg

# Bounds only matter if the corresponding fit flag is True
I1_BOUNDS = (29.0, 38)
THETA_CAM_BOUNDS = (-35.0, -28.0)

# Optional bounds for p0
P0_BOUNDS = (-1000.0, 1000.0)


# --------------------------------------
# Model edge positions
# --------------------------------------

def get_model_edge_pixels(
    p0,
    i1_deg,
    lam_hp1_um,
    lam_hp2_um,
    lam_min,
    lam_max,
    n_points,
    A_deg,
    f_mm,
    pixel_pitch_um,
    theta_cam_deg,
    sign_out,
):
    model_out = run_analytical_solution(
        lam_min=lam_min,
        lam_max=lam_max,
        n_points=n_points,
        A_deg=A_deg,
        i1_deg=i1_deg,
        f_mm=f_mm,
        pixel_pitch_um=pixel_pitch_um,
        p0=p0,
        theta_cam_deg=theta_cam_deg,
        sign_out=sign_out,
    )

    lam = model_out["lam"]
    pixel = model_out["pixel"]

    # Model gives lambda -> pixel on a grid.
    # We interpolate to get pixel exactly at the HP wavelengths.
    pixel_of_lambda = interp1d(
        lam,
        pixel,
        kind="linear",
        bounds_error=True
    )

    y_hp1_model = float(pixel_of_lambda(lam_hp1_um))
    y_hp2_model = float(pixel_of_lambda(lam_hp2_um))

    return y_hp1_model, y_hp2_model


# --------------------------------------------
# Residual function for optimisation
# --------------------------------------------

def residuals_for_fit(params, fit_i1, fit_theta_cam, obs, model_cfg):
    idx = 0

    p0 = params[idx]
    idx += 1

    if fit_i1:
        i1_deg = params[idx]
        idx += 1
    else:
        i1_deg = model_cfg["i1_deg_initial"]

    if fit_theta_cam:
        theta_cam_deg = params[idx]
        idx += 1
    else:
        theta_cam_deg = model_cfg["theta_cam_initial"]

    y_hp1_model, y_hp2_model = get_model_edge_pixels(
        p0=p0,
        i1_deg=i1_deg,
        lam_hp1_um=obs["lambda_hp1_um"],
        lam_hp2_um=obs["lambda_hp2_um"],
        lam_min=model_cfg["lam_min"],
        lam_max=model_cfg["lam_max"],
        n_points=model_cfg["n_points"],
        A_deg=model_cfg["A_deg"],
        f_mm=model_cfg["f_mm"],
        pixel_pitch_um=model_cfg["pixel_pitch_um"],
        theta_cam_deg=theta_cam_deg,
        sign_out=model_cfg["sign_out"],
    )

    m1 = y_hp1_model - obs["y_hp1_obs"]
    m2 = y_hp2_model - obs["y_hp2_obs"]

    return np.array([m1, m2], dtype=float)


# ------------------------------------
# Fitting function
# ------------------------------------

def fit_prism_model(
    obs,
    fit_i1=False,
    fit_theta_cam=False,
    p0_initial=256.0,
    i1_deg_initial=30.0,
    theta_cam_initial=-30.0,
    p0_bounds=(-5000.0, 5000.0),
    i1_bounds=(20.0, 45.0),
    theta_cam_bounds=(-40.0, -20.0),
    lam_min=3.440,
    lam_max=4.075,
    n_points=2000,
    A_deg=60.0,
    f_mm=50.0,
    pixel_pitch_um=15.0,
    sign_out=+1,
):
    model_cfg = {
        "lam_min": lam_min,
        "lam_max": lam_max,
        "n_points": n_points,
        "A_deg": A_deg,
        "i1_deg_initial": i1_deg_initial,
        "theta_cam_initial": theta_cam_initial,
        "f_mm": f_mm,
        "pixel_pitch_um": pixel_pitch_um,
        "sign_out": sign_out,
    }

    x0 = [p0_initial]
    lower = [p0_bounds[0]]
    upper = [p0_bounds[1]]

    if fit_i1:
        x0.append(i1_deg_initial)
        lower.append(i1_bounds[0])
        upper.append(i1_bounds[1])
    
    if fit_theta_cam:
        x0.append(theta_cam_initial)
        lower.append(theta_cam_bounds[0])
        upper.append(theta_cam_bounds[1])

    x0 = np.array(x0, dtype=float)
    lower = np.array(lower, dtype=float)
    upper = np.array(upper, dtype=float)

    sol = least_squares(
        residuals_for_fit,
        x0=x0,
        bounds=(lower, upper),
        args=(fit_i1, fit_theta_cam, obs, model_cfg),
    )

    idx = 0
    p0_fit = sol.x[idx]
    idx += 1

    if fit_i1:
        i1_deg_fit = sol.x[idx]
        idx += 1
    else:
        i1_deg_fit = i1_deg_initial

    if fit_theta_cam:
        theta_cam_fit = sol.x[idx]
        idx += 1
    else:
        theta_cam_fit = theta_cam_initial

    # Run model again using best-fit values
    model_out = run_analytical_solution(
        lam_min=lam_min,
        lam_max=lam_max,
        n_points=n_points,
        A_deg=A_deg,
        i1_deg=i1_deg_fit,
        f_mm=f_mm,
        pixel_pitch_um=pixel_pitch_um,
        p0=p0_fit,
        theta_cam_deg=theta_cam_fit,
        sign_out=sign_out,
    )

    lam_fit = model_out["lam"]
    pixel_fit = model_out["pixel"]

    # Interpolation objects for final wavelength solution
    pixel_to_lambda = interp1d(
        pixel_fit,
        lam_fit,
        kind="linear",
        bounds_error=False,
        fill_value=np.nan,
    )

    lambda_to_pixel = interp1d(
        lam_fit,
        pixel_fit,
        kind="linear",
        bounds_error=False,
        fill_value=np.nan,
    )

    y_hp1_model_fit = float(lambda_to_pixel(obs["lambda_hp1_um"]))
    y_hp2_model_fit = float(lambda_to_pixel(obs["lambda_hp2_um"]))

    m1 = y_hp1_model_fit - obs["y_hp1_obs"]
    m2 = y_hp2_model_fit - obs["y_hp2_obs"]

    return {
        "channel": obs["channel"],
        "roi_indices_0based": obs["roi_indices_0based"],
        "summed_channels": obs["summed_channels"],
        "calibration_time": obs["calibration_time"],
        "label": obs["label"],
        "dt_diagnose": obs["dt_diagnose"],
        "n_repeats": obs["n_repeats"],
        "output_top_idx": obs["output_top_idx"],
        "output_height": obs["output_height"],
        "lambda_hp1_um": obs["lambda_hp1_um"],
        "lambda_hp2_um": obs["lambda_hp2_um"],
        "y_hp1_obs": obs["y_hp1_obs"],
        "y_hp2_obs": obs["y_hp2_obs"],
        "y_hp1_model_fit": y_hp1_model_fit,
        "y_hp2_model_fit": y_hp2_model_fit,
        "p0_fit": p0_fit,
        "i1_deg_fit": i1_deg_fit,
        "theta_cam_fit": theta_cam_fit,
        "m1": m1,
        "m2": m2,
        "lam_fit": lam_fit,
        "pixel_fit": pixel_fit,
        "pixel_to_lambda": pixel_to_lambda,
        "lambda_to_pixel": lambda_to_pixel,
        "optimizer_success": sol.success,
        "optimizer_message": sol.message,
        "cost": sol.cost,
    }


#************************************
#main warpper 
#*************************************

def run_wavelength_calibration(
    label="Wav_test",
    roi_indices=ROI_INDICES,
    dt=2.0,
    n=1,
    snr_thresh=5.0,
    use_geom=True,
    custom_lambs=False,
    pad_seconds=0.0,
    setup_dt=SETUP_DT,
    baseline_n=BASELINE_N,
    smooth_method=SMOOTH_METHOD,
    savgol_window=SAVGOL_WINDOW,
    savgol_poly=SAVGOL_POLY,
    movavg_window=MOVAVG_WINDOW,
    fit_i1=FIT_I1,
    fit_theta_cam=FIT_THETA_CAM,
    p0_initial=P0_INITIAL,
    i1_deg_initial=I1_DEG_INITIAL,
    theta_cam_initial=THETA_CAM_INITIAL,
    p0_bounds=P0_BOUNDS,
    i1_bounds=I1_BOUNDS,
    theta_cam_bounds=THETA_CAM_BOUNDS,
    lam_min=LAM_MIN,
    lam_max=LAM_MAX,
    n_points=N_POINTS,
    A_deg=A_DEG,
    f_mm=F_MM,
    pixel_pitch_um=PIXEL_PITCH_UM,
    sign_out=SIGN_OUT,
):
    obs, meta, all_runs, edge_out = get_observed_edges_from_diagnostics(
        label=label,
        roi_indices=roi_indices,
        dt=dt,
        n=n,
        snr_thresh=snr_thresh,
        use_geom=use_geom,
        custom_lambs=custom_lambs,
        pad_seconds=pad_seconds,
        setup_dt=setup_dt,
        baseline_n=baseline_n,
        smooth_method=smooth_method,
        savgol_window=savgol_window,
        savgol_poly=savgol_poly,
        movavg_window=movavg_window,
    )
    print("obs edges debug")
    print(obs)


    fit_out = fit_prism_model(
        obs=obs,
        fit_i1=fit_i1,
        fit_theta_cam=fit_theta_cam,
        p0_initial=p0_initial,
        i1_deg_initial=i1_deg_initial,
        theta_cam_initial=theta_cam_initial,
        p0_bounds=p0_bounds,
        i1_bounds=i1_bounds,
        theta_cam_bounds=theta_cam_bounds,
        lam_min=lam_min,
        lam_max=lam_max,
        n_points=n_points,
        A_deg=A_deg,
        f_mm=f_mm,
        pixel_pitch_um=pixel_pitch_um,
        sign_out=sign_out,
    )

    return fit_out


# -------------------------------------
# main
# --------------------------------------

if __name__ == "__main__":
    fit_out = run_wavelength_calibration(
        label="Wav_test",
        roi_indices=ROI_INDICES,
        dt=2.0,
        n=1,
        setup_dt=SETUP_DT,
    )

    print("\n=== FIT SUMMARY ===")
    print(f"Calibration time: {fit_out['calibration_time']}")
    print(f"Channel: {fit_out['channel']}")
    print(f"Summed ROI indices 0-based: {fit_out['roi_indices_0based']}")
    print(f"Summed channels: {fit_out['summed_channels']}")
    print(f"Observed HP1 pixel : {fit_out['y_hp1_obs']:.4f}")
    print(f"Observed HP2 pixel : {fit_out['y_hp2_obs']:.4f}")
    print(f"Model HP1 pixel    : {fit_out['y_hp1_model_fit']:.4f}")
    print(f"Model HP2 pixel    : {fit_out['y_hp2_model_fit']:.4f}")
    print()
    print(f"Best-fit p0        : {fit_out['p0_fit']:.6f}")
    print(f"Best-fit i1_deg    : {fit_out['i1_deg_fit']:.6f}")
    print(f"Best-fit theta_cam : {fit_out['theta_cam_fit']:.6f}")
    print()
    print(f"Residual m1 (HP1)  : {fit_out['m1']:.6f} pix")
    print(f"Residual m2 (HP2)  : {fit_out['m2']:.6f} pix")
    print()
    print(f"Optimizer success  : {fit_out['optimizer_success']}")
    print(f"Message            : {fit_out['optimizer_message']}")
    print(f"Cost               : {fit_out['cost']:.6e}")

    # Example: wavelength at a chosen detector pixel
    test_pixel = 50
    lam_at_test_pixel = float(fit_out["pixel_to_lambda"](test_pixel))
    print()
    print(f"Example: wavelength at pixel {test_pixel:.1f} = {lam_at_test_pixel:.6f} micron")