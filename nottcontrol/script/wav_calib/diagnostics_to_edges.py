
"""
This code block passes the 1D array thats stored in memory (from export frames_direct) to extract_filter_code_final

to get the edges of the filter. Then it returns all the data including the metadata to be passed on to final wavelength calibration code

"""

from .export_from_frames_direct import run_diagnostics_export
from .extract_filter_code_final import extract_filter_edges_from_arrays


def get_observed_edges_from_diagnostics(
    label,
    roi_indices,
    dt=2.0,
    n=1,
    snr_thresh=5.0,
    use_geom=True,
    pad_seconds=0.0,
    setup_dt=5.0,
    baseline_n=12,
    smooth_method="savgol",
    savgol_window=9,
    savgol_poly=2,
    movavg_window=7,
    lambda_hp1_um=3.46252,
    lambda_hp2_um=4.07477,

):
    # run diagnostics
    meta, all_runs = run_diagnostics_export(
        label=label,
        dt=dt,
        n=n,
        snr_thresh=snr_thresh,
        use_geom=use_geom,
        pad_seconds=pad_seconds,
        setup_dt=setup_dt,
    )

    if len(all_runs) == 0:
        raise ValueError("Diagnostics returned no runs.")

    # use first run
    spectra = all_runs[0]["flux_disp"]
    channels = meta["channels"]

    # extrct edgess from spectra
    out = extract_filter_edges_from_arrays(
        spectra=spectra,
        channels=channels,
        roi_indices=roi_indices,
        baseline_n=baseline_n,
        smooth_method=smooth_method,
        savgol_window=savgol_window,
        savgol_poly=savgol_poly,
        movavg_window=movavg_window,
        source_name=label,
        run_key="run000_flux_disp",
        lambda_hp1_um=lambda_hp1_um,
        lambda_hp2_um=lambda_hp2_um,
    )

    row = out["result"]

    obs = {
        "channel": row["channel"],
        "roi_indices_0based": row["roi_indices_0based"],
        # "roi_indices_1based": row["roi_indices_1based"],
        "summed_channels": row["summed_channels"],
        "y_hp1_obs": row["y_hp1"],
        "y_hp2_obs": row["y_hp2"],
        "y_peak_obs": row["y_peak"],
        "width_obs": row["width_pix"],
        "lambda_hp1_um": out["lambda_hp1_um"],
        "lambda_hp2_um": out["lambda_hp2_um"],
        "calibration_time": meta.get("calibration_time"),
        "label": meta.get("label"),
        "dt_diagnose": meta.get("dt_diagnose"),
        "n_repeats": meta.get("n_repeats"),
        "output_top_idx": meta.get("output_top_idx"),
        "output_height": meta.get("output_height"),
    }

    return obs, meta, all_runs, out