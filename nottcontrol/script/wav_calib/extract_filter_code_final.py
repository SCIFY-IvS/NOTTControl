"""
Code to  extract the edges of the 1D spectra, that was extracted using 'export_from_frames_direct'. It takes the data, smoothens it, 
estimate baseline, maximum value and then find the half-power crossing values. Then returns along with other data. 

"""

import numpy as np
import matplotlib.pyplot as plt
import json
from pathlib import Path

# == Edit these, when required.==    
NPZ_PATH = r"D:\Prism spectrograph_NOTT\calibration\diag_export_data2_broadband2_20260225_143332_dt8.000s_n1.npz"  # Only required if you are directly providing any extracted file in with same format as what export_from_frames_direct


# Select ROIs by 0-based index
SUM_ROI_INDICES = [0, 1, 6, 7]     

RUN_KEY = "run000_flux_disp"      # to be changed if you saved more runs
BASELINE_N = 12                   # pixels from each end used for baseline estimation
SMOOTH_METHOD = "savgol"          # "savgol" or "moving_avg"
SAVGOL_WINDOW = 9                 # must be odd; keep small (7,9,11)
SAVGOL_POLY = 2
MOVAVG_WINDOW = 7                 # odd recommended
DO_PLOTS = True

# TODO Put these values in config file.
LAMBDA_HP1_UM = 3.46252
LAMBDA_HP2_UM = 4.07477
# ==============================


def smooth_1d(y, method="savgol", savgol_window=9, savgol_poly=2, movavg_window=7):   #for smoothening
    y = np.asarray(y, dtype=float)

    if method == "savgol":
        try:
            from scipy.signal import savgol_filter
            win = int(savgol_window)
            if win % 2 == 0:
                win += 1
            win = min(win, len(y) if len(y) % 2 == 1 else len(y) - 1)
            if win < 5:
                return y.copy()
            poly = min(int(savgol_poly), win - 2)
            return savgol_filter(y, window_length=win, polyorder=poly, mode="interp")
        except Exception:
            method = "moving_avg"

    if method == "moving_avg":
        w = int(movavg_window)
        if w < 3:
            return y.copy()
        if w % 2 == 0:
            w += 1
        pad = w // 2
        ypad = np.pad(y, (pad, pad), mode="edge")
        kernel = np.ones(w) / w
        return np.convolve(ypad, kernel, mode="valid")

    return y.copy()


def estimate_baseline(s, n=12):   #baseline esetimation
    s = np.asarray(s, dtype=float)
    n = max(1, min(int(n), len(s) // 3))
    left = np.median(s[:n])
    right = np.median(s[-n:])
    return 0.5 * (left + right)


def crossing_subpixel(x0, y0, x1, y1, level):   #sub-pixel estimation, in case value falls between 2 pixels
    if y1 == y0:
        return 0.5 * (x0 + x1)
    t = (level - y0) / (y1 - y0)
    return x0 + t * (x1 - x0)


def find_halfpower_crossings(s_raw, baseline_n=12, smooth_kwargs=None):   #HP values

    if smooth_kwargs is None:
        smooth_kwargs = {}

    s_raw = np.asarray(s_raw, dtype=float)
    x = np.arange(len(s_raw), dtype=float)

    s_sm = smooth_1d(s_raw, **smooth_kwargs)
    base = estimate_baseline(s_sm, n=baseline_n)

    s_bs = s_sm - base
    peak_idx = int(np.nanargmax(s_bs))
    peak_val = s_sm[peak_idx]

    S50 = base + 0.5 * (peak_val - base)

    diff = s_sm - S50
    sign = np.sign(diff)
    sign[sign == 0] = 1
    flips = np.where(sign[:-1] != sign[1:])[0]

    if len(flips) < 2:
        return base, peak_val, S50, np.nan, np.nan, float(peak_idx)

    left_candidates = flips[flips < peak_idx]
    right_candidates = flips[flips >= peak_idx]

    if len(left_candidates) == 0 or len(right_candidates) == 0:
        iL = flips[0]
        iR = flips[-1]
    else:
        iL = left_candidates[-1]
        iR = right_candidates[0]

    y_hp1 = crossing_subpixel(x[iL], s_sm[iL], x[iL + 1], s_sm[iL + 1], S50)
    y_hp2 = crossing_subpixel(x[iR], s_sm[iR], x[iR + 1], s_sm[iR + 1], S50)

    return base, peak_val, S50, float(y_hp1), float(y_hp2), float(peak_idx)


#---------------------------------------
# The following function works directly with arrays (in memory)
#---------------------------------------
def extract_filter_edges_from_arrays(
    spectra,
    channels=None,
    roi_indices=None,
    baseline_n=12,
    smooth_method="savgol",
    savgol_window=9,
    savgol_poly=2,
    movavg_window=7,
    source_name=None,
    run_key=None,
    lambda_hp1_um=LAMBDA_HP1_UM,
    lambda_hp2_um=LAMBDA_HP2_UM,
):
    spectra = np.asarray(spectra, dtype=float)
    Nroi = spectra.shape[0]

    if channels is None:
        channels = [f"ROI{i+1}" for i in range(Nroi)]
    else:
        channels = list(channels)


    if roi_indices is None:
        raise ValueError(
            "roi_indices must be provided. "
            "These are the ROI indices that will be summed."
        )
    
    roi_indices = list(roi_indices)

    for roi0 in roi_indices:
        if roi0 < 0 or roi0 >= Nroi:
            raise IndexError(f"ROI index {roi0} is outside valid range 0..{Nroi-1}")

    summed_spectrum = np.nansum(spectra[roi_indices, :], axis=0)


    smooth_kwargs = dict(
        method=smooth_method,
        savgol_window=savgol_window,
        savgol_poly=savgol_poly,
        movavg_window=movavg_window
    )



    base, peak, S50, y1, y2, ypk = find_halfpower_crossings(
            summed_spectrum,
            baseline_n=baseline_n,
            smooth_kwargs=smooth_kwargs
    )
        
    width = (y2 - y1) if np.isfinite(y1) and np.isfinite(y2) else np.nan
        
    summed_channels = [
        channels[roi0] if roi0 < len(channels) else f"ROI{roi0+1}"
        for roi0 in roi_indices
    ]

    
    result = {
        "channel": "summed_ROIs",
        "roi_indices_0based": roi_indices,
        "roi_indices_1based": [roi0 + 1 for roi0 in roi_indices],
        "summed_channels": summed_channels,
        "y_hp1": y1,
        "y_hp2": y2,
        "y_peak": ypk,
        "baseline": base,
        "peak": peak,
        "S50": S50,
        "width_pix": width,
}

    return {
        "source_name": source_name,
        "run_key": run_key,
        "channels": channels,
        "Nroi": Nroi,
        "summed_spectrum": summed_spectrum,
        "result": result,
        "lambda_hp1_um": lambda_hp1_um,
        "lambda_hp2_um": lambda_hp2_um,
    } 


# -----------------------------------
# This fucntion works from a saved .npz file (if had saved outputs), mainly for verification purposes
# -------------------------------------

def extract_filter_edges(
    npz_path,
    run_key="run000_flux_disp",
    roi_indices=None,
    baseline_n=12,
    smooth_method="savgol",
    savgol_window=9,
    savgol_poly=2,
    movavg_window=7,
    lambda_hp1_um=LAMBDA_HP1_UM,
    lambda_hp2_um=LAMBDA_HP2_UM,
):
    npz_path = Path(npz_path)
    if not npz_path.exists():
        raise FileNotFoundError(f"File not found: {npz_path}")

    data = np.load(npz_path, allow_pickle=True)
    meta = json.loads(data["meta_json"].item())

    channels = meta.get("channels", [])
    spectra = data[run_key]

    out = extract_filter_edges_from_arrays(
        spectra=spectra,
        channels=channels,
        roi_indices=roi_indices,
        baseline_n=baseline_n,
        smooth_method=smooth_method,
        savgol_window=savgol_window,
        savgol_poly=savgol_poly,
        movavg_window=movavg_window,
        source_name=str(npz_path),
        run_key=run_key,
        lambda_hp1_um=lambda_hp1_um,
        lambda_hp2_um=lambda_hp2_um,
    )

    # Keep backward compatible key name for file based workflow
    out["npz_path"] = str(npz_path)

    return out



#--------------------------
# The following part is only relevant for direct runs (to see output for example); can be useful for debugging. Ignore otherwise 
#--------------------------------

if __name__ == "__main__":
    out = extract_filter_edges(
        npz_path=NPZ_PATH,
        run_key=RUN_KEY,
        roi_indices=SUM_ROI_INDICES,
        baseline_n=BASELINE_N,
        smooth_method=SMOOTH_METHOD,
        savgol_window=SAVGOL_WINDOW,
        savgol_poly=SAVGOL_POLY,
        movavg_window=MOVAVG_WINDOW,
        lambda_hp1_um=LAMBDA_HP1_UM,
        lambda_hp2_um=LAMBDA_HP2_UM,
    )

    print("Loaded:", Path(out["npz_path"]).name)
    print("Channels:", out["channels"])
    print("Nroi:", out["Nroi"])

    
    row = out["result"]


    print("\nHalf-power extraction from summed ROIs:")
    print("Summed ROI indices 0-based:", row["roi_indices_0based"])
    # print("Summed ROI indices 1-based:", row["roi_indices_1based"])
    print("Summed channels:", row["summed_channels"])

    print(
        f"y_HP1={row['y_hp1']:.2f}, "
        f"y_HP2={row['y_hp2']:.2f}, "
        f"y_peak={row['y_peak']:.2f}, "
        f"baseline={row['baseline']:.2f}, "
        f"peak={row['peak']:.2f}, "
        f"S50={row['S50']:.2f}, "
        f"width_pix={row['width_pix']:.2f}"
    )


    if DO_PLOTS:
        s_raw = out["summed_spectrum"]
        x = np.arange(len(s_raw))


        smooth_kwargs = dict(
            method=SMOOTH_METHOD,
            savgol_window=SAVGOL_WINDOW,
            savgol_poly=SAVGOL_POLY,
            movavg_window=MOVAVG_WINDOW
        )


        s_sm = smooth_1d(s_raw, **smooth_kwargs)


        plt.figure(figsize=(9, 5))
        plt.plot(x, s_raw, label="summed raw spectrum")
        # plt.plot(x, s_sm, label=f"smoothed ({SMOOTH_METHOD})")

        if np.isfinite(row["y_hp1"]):
            plt.axvline(row["y_hp1"], linestyle="--", label="y_HP1")
        if np.isfinite(row["y_hp2"]):
            plt.axvline(row["y_hp2"], linestyle="--", label="y_HP2")

        plt.title("Summed ROI spectrum")
        plt.xlabel("Vertical pixel index")
        plt.ylabel("Flux, summed selected ROIs")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.show()


    print("\nMap half-power pixels to filter wavelengths (from filter report):")
    print("  HP1 (50% left)  = 3462.52 nm = 3.46252 µm")
    print("  HP2 (50% right) = 4074.77 nm = 4.07477 µm")
