#!/usr/bin/env python3
"""
Extract calibrated 1D spectra from each ROI using frames.py.

This module is used by the wavelength calibration pipeline. It takes
science and dark frames, builds the ROI geometry, and returns the
dispersed flux for each ROI in memory.


Main outputs per acquisition:
- stamps
- fluxes_broad
- fluxes_broad_err
- snrs_broad
- flux_disp
- flux_disp_err
- snr_disp
- metadata (channels, ROI mapping, output geometry, wavelength config)
"""
from __future__ import annotations

from astropy.time import Time
from platform import system

import time
import numpy as np
from nottcontrol import config as nott_config
from nottcontrol import redisclient
import nottcontrol.components.human_interface as human_interface
import nottcontrol.components.pypiezo as pypiezo



class dummy_piezo(object):
    def raw2values(self, vals):
        return np.array([vals])

    def send(self, *args, **kwargs):
        pass

# Small helpers

def _safe_to_list(x):
    try:
        return list(x)
    except Exception:
        return x


def _timestamps_from_frame_ids(ids):
    stamps = []
    for frame_id in ids:
        hms = int(frame_id.split("_")[1])
        stamps.append(hms)
    stamps = np.asarray(stamps)
    return stamps - stamps[0]


# A minimal Diagnostics like class

class FrameSpectrumExporter:

    def __init__(
        self,
        use_geom=True,
        snr_thresh=5.0,
        setup_dt=5.0,
        human_interf=None,
        redis_client=None,
        piezo_interf=None,
    ):
        self.use_geom = bool(use_geom)
        self.snr_thresh = float(snr_thresh)
        self.setup_dt = float(setup_dt)

        if piezo_interf is None:
            piezo_interf = dummy_piezo()

        if redis_client is None:
            redis_client = redisclient.RedisClient(human_interface.dburl)

        if human_interf is None:
            human_interf = human_interface.HumInt(
                interf=piezo_interf,
                db_server=redis_client,
                shutter_pad=10,
                pad=0.08,
                offset=5.0,
            )

        self.piezo_interf = piezo_interf
        self.redis_client = redis_client
        self.human_interf = human_interf

        self._setup_output_geometry()

    def _setup_output_geometry(self):
        """
        - take initial science + dark frames
        - determine channels / ROI mapping
        - define output mask
        - determine output_top_idx and output_height from photometric channels
        """
        print(
            f"Creating initial setup frames "
            f"(science {self.setup_dt:.1f}s + dark {self.setup_dt:.1f}s)..."
        )

        self.human_interf.shutter_set([1, 1, 1, 1], wait=True)
        sci_frames = self.human_interf.science_frame_sequence(self.setup_dt)
        dark_frames = self.human_interf.dark_frame_sequence(self.setup_dt)

        self.Nroi = len(sci_frames.rois_data)
        self.dark_frames = dark_frames

        channels_roi, channels_data = sci_frames.link_to_channels
        self.channels_roi = channels_roi
        self.channels_data = channels_data
        self.channels = list(channels_roi.keys())

        cal_mean, cal_mean_std = sci_frames.calib_master(dark_frames)
        cal_snr = np.divide(
            cal_mean,
            cal_mean_std,
            out=np.zeros_like(cal_mean, dtype=float),
            where=(cal_mean_std != 0),
        )

        if self.use_geom:
            self.outputs_pos = np.ones_like(cal_snr, dtype=bool)
        else:
            self.outputs_pos = (cal_snr >= self.snr_thresh)

        # Determine output vertical span from photometric channels, same idea as
        # Diagnostics.__init__.
        photo_idx = []
        for channel_label in self.channels: 
            if str(channel_label).startswith("P"):
                photo_idx.append(self.channels_roi[channel_label].idx - 1)

        if len(photo_idx) == 0:
            raise RuntimeError("No photometric channels found; cannot determine output geometry.")

        photo_outputs_pos = self.outputs_pos[photo_idx]
        output_pxs = np.argwhere(photo_outputs_pos)
        row_ind = output_pxs[:, 1]

        self.output_top_idx = int(np.min(row_ind))
        self.output_height = int(np.max(row_ind)) - self.output_top_idx + 1

    def diagnose(self, dt):

        sci_frames = self.human_interf.science_frame_sequence(dt)
        cal_mean, cal_mean_std, cal_seq, cal_seq_std = sci_frames.calib(self.dark_frames)

        # Apply output mask, mirroring Diagnostics.diagnose().
        cal_mean = cal_mean * self.outputs_pos
        cal_mean_std = cal_mean_std * self.outputs_pos

        cal_mean_snr = np.divide(
            cal_mean,
            cal_mean_std,
            out=np.zeros_like(cal_mean, dtype=float),
            where=(cal_mean_std != 0),
        )

        cal_seq = cal_seq * self.outputs_pos[:, np.newaxis, :, :]
        cal_seq_snr = np.divide(
            cal_seq,
            cal_seq_std,
            out=np.zeros_like(cal_seq, dtype=float),
            where=(cal_seq_std != 0),
        )

        # Time series of broadband flux
        fluxes_broad = cal_seq.sum(axis=(2, 3))
        snrs_broad = cal_seq_snr.sum(axis=(2, 3))
        fluxes_broad_err = np.sqrt((cal_seq_std ** 2).sum(axis=(1, 2)))

        # Dispersed flux (row-per-row in master frame)
        row_slice = slice(self.output_top_idx, self.output_top_idx + self.output_height)
        flux_disp = cal_mean.sum(axis=2)[:, row_slice]
        snr_disp = cal_mean_snr.sum(axis=2)[:, row_slice]
        flux_disp_err = np.sqrt((cal_mean_std ** 2).sum(axis=2))[:, row_slice]

        stamps = _timestamps_from_frame_ids(sci_frames.ids)

        return (
            stamps,
            fluxes_broad,
            fluxes_broad_err,
            snrs_broad,
            flux_disp,
            flux_disp_err,
            snr_disp,
        )


# Export layer (same output structure as before)

def _build_meta(diag, label, dt, n, use_geom, snr_thresh):
    meta = {
        "label": label,
        "calibration_time": Time.now().isot,
        "dt_diagnose": float(dt),
        "n_repeats": int(n),
        "use_geom": bool(use_geom),
        "snr_thresh": float(snr_thresh),
        "output_top_idx": int(getattr(diag, "output_top_idx", -1)),
        "output_height": int(getattr(diag, "output_height", -1)),
        "Nroi": int(getattr(diag, "Nroi", -1)),
        "channels": _safe_to_list(getattr(diag, "channels", [])),
    }

    try:
        ch_roi = {}
        for ch in diag.channels:
            ch_roi[ch] = int(diag.channels_roi[ch].idx)
        meta["channel_to_roi_idx_1based"] = ch_roi
    except Exception:
        meta["channel_to_roi_idx_1based"] = {}

    return meta

def run_direct_export(  #f
    label,
    dt=2.0,
    n=1,
    snr_thresh=5.0,
    use_geom=True,
    pad_seconds=0.0,
    setup_dt=5.0,
):
    diag = FrameSpectrumExporter(
        use_geom=use_geom,
        snr_thresh=snr_thresh,
        setup_dt=setup_dt,
    )

    meta = _build_meta(
        diag=diag,
        label=label,
        dt=dt,
        n=n,
        use_geom=use_geom,
        snr_thresh=snr_thresh,
    )

    all_runs = []
    for k in range(int(n)):
        print(f"\nRunning direct diagnose {k+1}/{n} for dt={dt}s ...")
        (
            stamps,
            fluxes_broad,
            fluxes_broad_err,
            snrs_broad,
            flux_disp,
            flux_disp_err,
            snr_disp,
        ) = diag.diagnose(dt=dt)

        run = {
            "stamps": np.array(stamps),
            "fluxes_broad": np.array(fluxes_broad),
            "fluxes_broad_err": np.array(fluxes_broad_err),
            "snrs_broad": np.array(snrs_broad),
            "flux_disp": np.array(flux_disp),
            "flux_disp_err": np.array(flux_disp_err),
            "snr_disp": np.array(snr_disp),
        }

        print(
            "  stamps:", run["stamps"].shape,
            "flux_disp:", run["flux_disp"].shape,
            "fluxes_broad:", run["fluxes_broad"].shape,
        )
        print("  flux_disp finite fraction:", np.isfinite(run["flux_disp"]).mean())

        all_runs.append(run)

        if pad_seconds > 0 and (k < n - 1):
            time.sleep(float(pad_seconds))

    return meta, all_runs


def run_diagnostics_export(                         #for saving the data in memory, when called
    label,
    dt=2.0,
    n=1,
    snr_thresh=5.0,
    use_geom=True,
    pad_seconds=0.0,   
    setup_dt=5.0,
):
    return run_direct_export(
        label=label,
        dt=dt,
        n=n,
        snr_thresh=snr_thresh,
        use_geom=use_geom,
        pad_seconds=pad_seconds,
        setup_dt=setup_dt,
    )