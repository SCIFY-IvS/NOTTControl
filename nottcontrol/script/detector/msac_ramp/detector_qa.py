"""Detector-quality maps for MSAC H2RG reset and UpTheRamp cubes.

Writes extra PNGs (and slope/noise FITS) next to the flux plot:

* ``msac_qa_reset.png`` — spatial quality of the reset (or first) frame
* ``msac_qa_ramp.png`` — slope, residual RMS, linearity of the CDS cube
* ``msac_qa_slope.fits`` / ``msac_qa_resid_rms.fits`` — per-pixel maps
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

H2RG_N_OUTPUTS = 32
H2RG_REF_WIDTH = 4
DEFAULT_FULL_FRAME = 2048


def _finite(image: np.ndarray) -> np.ndarray:
    work = np.asarray(image, dtype=np.float64)
    return work[np.isfinite(work)]


def _display_limits(image: np.ndarray) -> tuple[float, float]:
    finite = _finite(image)
    if finite.size == 0:
        return 0.0, 1.0
    lo, hi = np.percentile(finite, (5.0, 99.5))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = float(np.min(finite)), float(np.max(finite))
        if hi <= lo:
            hi = lo + 1.0
    return float(lo), float(hi)


def _stats(image: np.ndarray) -> dict[str, float]:
    finite = _finite(image)
    if finite.size == 0:
        return {
            "n": 0.0,
            "median": float("nan"),
            "mad": float("nan"),
            "std": float("nan"),
            "p01": float("nan"),
            "p99": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
        }
    med = float(np.median(finite))
    mad = float(np.median(np.abs(finite - med)))
    return {
        "n": float(finite.size),
        "median": med,
        "mad": 1.4826 * mad,
        "std": float(np.std(finite)),
        "p01": float(np.percentile(finite, 1.0)),
        "p99": float(np.percentile(finite, 99.0)),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
    }


def _safe_hist(ax, values: np.ndarray, *, bins: int, range_: tuple[float, float] | None, **kwargs) -> None:
    work = np.asarray(values, dtype=np.float64)
    work = work[np.isfinite(work)]
    if work.size == 0:
        return
    if range_ is not None:
        lo, hi = range_
        if (
            not np.isfinite(lo)
            or not np.isfinite(hi)
            or hi <= lo
            or (hi - lo) < 1e-9 * max(1.0, abs(lo), abs(hi))
        ):
            ax.axvline(
                float(np.median(work)),
                color=kwargs.get("color", "C0"),
                label=kwargs.get("label"),
            )
            return
    try:
        if range_ is None:
            ax.hist(work, bins=bins, **kwargs)
        else:
            ax.hist(work, bins=bins, range=range_, **kwargs)
    except ValueError:
        ax.axvline(
            float(np.median(work)),
            color=kwargs.get("color", "C0"),
            label=kwargs.get("label"),
        )


def _format_stats(stats: dict[str, float]) -> str:
    return (
        f"n={int(stats['n'])}\n"
        f"med={stats['median']:.4g}\n"
        f"MAD={stats['mad']:.4g}\n"
        f"std={stats['std']:.4g}\n"
        f"p01={stats['p01']:.4g}\n"
        f"p99={stats['p99']:.4g}"
    )


def h2rg_ref_mask(shape: tuple[int, int], *, width: int = H2RG_REF_WIDTH) -> np.ndarray | None:
    """True on HxRG reference pixels; None if the frame is too small."""
    height, width_img = int(shape[0]), int(shape[1])
    if height < 4 * width or width_img < 4 * width:
        return None
    mask = np.zeros((height, width_img), dtype=bool)
    mask[:width, :] = True
    mask[-width:, :] = True
    mask[:, :width] = True
    mask[:, -width:] = True
    return mask


def n_outputs_for_shape(shape: tuple[int, int]) -> int | None:
    """Guess SIDECAR output count from image width (32 for full-frame)."""
    width = int(shape[1])
    if width == DEFAULT_FULL_FRAME:
        return H2RG_N_OUTPUTS
    if width >= 128 and width % H2RG_N_OUTPUTS == 0:
        return H2RG_N_OUTPUTS
    return None


def channel_profile(image: np.ndarray, n_out: int) -> np.ndarray | None:
    """Mean ADU per output channel (vertical stripes)."""
    img = np.asarray(image, dtype=np.float64)
    height, width = img.shape
    if n_out <= 0 or width % n_out != 0:
        return None
    chan_w = width // n_out
    block = img.reshape(height, n_out, chan_w)
    with np.errstate(all="ignore"):
        means = np.nanmean(block, axis=(0, 2))
    return np.asarray(means, dtype=np.float64)


def defect_mask(image: np.ndarray, *, n_sigma: float) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(hot, cold)`` boolean maps from a robust median/MAD clip."""
    img = np.asarray(image, dtype=np.float64)
    finite = np.isfinite(img)
    stats = _stats(img)
    scale = stats["mad"]
    hot = np.zeros(img.shape, dtype=bool)
    cold = np.zeros(img.shape, dtype=bool)
    if not np.isfinite(scale) or scale <= 0:
        return hot, cold
    med = stats["median"]
    hot = finite & (img > med + n_sigma * scale)
    cold = finite & (img < med - n_sigma * scale)
    return hot, cold


def fit_ramp(cube: np.ndarray, sample_index: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-pixel linear fit of *cube* vs *sample_index*.

    Returns ``(slope, intercept, residual_rms)`` each ``(ny, nx)``.
    """
    data = np.asarray(cube, dtype=np.float64)
    t = np.asarray(sample_index, dtype=np.float64).reshape(-1)
    if data.ndim != 3:
        raise ValueError(f"Expected (n, y, x) cube, got shape {data.shape}")
    if t.size != data.shape[0]:
        raise ValueError(f"sample_index length {t.size} != nplanes {data.shape[0]}")
    if t.size < 2:
        nan = np.full(data.shape[1:], np.nan, dtype=np.float64)
        return nan, nan, nan
    t_mean = float(np.mean(t))
    tt = t - t_mean
    sxx = float(np.dot(tt, tt))
    if sxx <= 0:
        nan = np.full(data.shape[1:], np.nan, dtype=np.float64)
        return nan, nan, nan
    y_mean = np.mean(data, axis=0)
    sxy = np.tensordot(tt, data, axes=(0, 0))
    slope = sxy / sxx
    intercept = y_mean - slope * t_mean
    pred = intercept + slope * t[:, None, None]
    resid = data - pred
    rms = np.sqrt(np.mean(resid * resid, axis=0))
    return slope, intercept, rms


def _draw_box(
    ax,
    box: tuple[int, int, int, int] | None,
    *,
    color: str,
    linestyle: str = "-",
) -> None:
    if box is None:
        return
    from matplotlib.patches import Rectangle

    row0, row1, col0, col1 = box
    ax.add_patch(
        Rectangle(
            (col0 - 0.5, row0 - 0.5),
            col1 - col0,
            row1 - row0,
            fill=False,
            edgecolor=color,
            linewidth=1.0,
            linestyle=linestyle,
        )
    )


def _overlay_pixels(ax, pixels: np.ndarray | None) -> None:
    if pixels is None or pixels.size == 0:
        return
    ax.scatter(
        pixels[:, 1],
        pixels[:, 0],
        s=12,
        c="#ff6b6b",
        marker="o",
        linewidths=0.4,
        edgecolors="white",
        zorder=5,
    )


def _save_png(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    logging.info("Wrote detector QA plot: %s", path)


def save_map_fits(path: Path, image: np.ndarray, *, bunit: str, history: str) -> None:
    from astropy.io import fits

    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(image, dtype=np.float32)
    header = fits.Header()
    header["BUNIT"] = bunit
    header.add_history(history)
    fits.PrimaryHDU(data=data, header=header).writeto(path, overwrite=True)
    logging.info("Wrote detector QA map: %s", path)


def plot_reset_qa(
    image: np.ndarray,
    *,
    output: Path,
    title: str,
    n_sigma: float,
    illum_box: tuple[int, int, int, int] | None = None,
    extra_box: tuple[int, int, int, int] | None = None,
) -> dict[str, float]:
    """Spatial quality of a reset (or first-sample) frame. Returns summary stats."""
    img = np.asarray(image, dtype=np.float64)
    stats = _stats(img)
    hot, cold = defect_mask(img, n_sigma=n_sigma)
    n_hot = int(hot.sum())
    n_cold = int(cold.sum())
    ref = h2rg_ref_mask(img.shape)
    n_out = n_outputs_for_shape(img.shape)
    chan = channel_profile(img, n_out) if n_out else None
    col_mean = np.nanmean(img, axis=0)
    row_mean = np.nanmean(img, axis=1)
    vmin, vmax = _display_limits(img)

    fig = plt.figure(figsize=(12.5, 8.2), layout="constrained")
    gs = fig.add_gridspec(2, 3, hspace=0.28, wspace=0.22)
    fig.suptitle(title, fontsize=12)

    ax_im = fig.add_subplot(gs[0, 0])
    im = ax_im.imshow(
        img,
        origin="upper",
        cmap="gray",
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest",
        aspect="equal",
    )
    _draw_box(ax_im, illum_box, color="#ff6b6b")
    _draw_box(ax_im, extra_box, color="#4cc9f0", linestyle="--")
    ax_im.set_title("Reset / reference frame")
    ax_im.set_xlabel("X [pix]")
    ax_im.set_ylabel("Y [pix]")
    fig.colorbar(im, ax=ax_im, fraction=0.046, pad=0.04, label="ADU")

    ax_hist = fig.add_subplot(gs[0, 1])
    finite = _finite(img)
    if finite.size:
        lo, hi = np.percentile(finite, (0.5, 99.5))
        if hi <= lo:
            hi = lo + 1.0
        _safe_hist(
            ax_hist,
            finite,
            bins=80,
            range_=(lo, hi),
            color="C0",
            histtype="stepfilled",
            alpha=0.7,
        )
    ax_hist.set_title("Histogram")
    ax_hist.set_xlabel("ADU")
    ax_hist.set_ylabel("Pixels")
    ax_hist.text(
        0.98,
        0.98,
        _format_stats(stats) + f"\nhot={n_hot} cold={n_cold}",
        transform=ax_hist.transAxes,
        va="top",
        ha="right",
        fontsize=8,
        family="monospace",
        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
    )

    ax_def = fig.add_subplot(gs[0, 2])
    defect = np.zeros(img.shape + (3,), dtype=np.float64)
    defect[..., :] = np.clip((img - vmin) / max(vmax - vmin, 1e-9), 0, 1)[..., None]
    defect[hot] = (1.0, 0.2, 0.2)
    defect[cold] = (0.2, 0.5, 1.0)
    ax_def.imshow(defect, origin="upper", interpolation="nearest", aspect="equal")
    ax_def.set_title(f"Defects ({n_sigma:.1f}σ MAD): hot red, cold blue")
    ax_def.set_xlabel("X [pix]")
    ax_def.set_ylabel("Y [pix]")

    ax_col = fig.add_subplot(gs[1, 0])
    ax_col.plot(np.arange(col_mean.size), col_mean, color="C0", linewidth=0.8)
    ax_col.set_title("Column mean (channel stripes)")
    ax_col.set_xlabel("X [pix]")
    ax_col.set_ylabel("ADU")
    ax_col.grid(True, alpha=0.3)

    ax_row = fig.add_subplot(gs[1, 1])
    ax_row.plot(row_mean, np.arange(row_mean.size), color="C1", linewidth=0.8)
    ax_row.set_title("Row mean (banding)")
    ax_row.set_xlabel("ADU")
    ax_row.set_ylabel("Y [pix]")
    ax_row.invert_yaxis()
    ax_row.grid(True, alpha=0.3)

    ax_ch = fig.add_subplot(gs[1, 2])
    if chan is not None:
        ax_ch.bar(np.arange(chan.size), chan, color="C2", width=0.85)
        ax_ch.set_title(f"Per-output mean ({chan.size} channels)")
        ax_ch.set_xlabel("Output")
        ax_ch.set_ylabel("ADU")
        p2p = float(np.nanmax(chan) - np.nanmin(chan))
        ax_ch.text(
            0.02,
            0.98,
            f"ch p-p={p2p:.4g} ADU",
            transform=ax_ch.transAxes,
            va="top",
            fontsize=8,
        )
        stats["channel_p2p"] = p2p
    elif ref is not None:
        ref_stats = _stats(img[ref])
        sci_stats = _stats(img[~ref])
        ax_ch.bar(
            [0, 1],
            [sci_stats["median"], ref_stats["median"]],
            color=["C0", "C3"],
            tick_label=["Active", "Ref pix"],
        )
        ax_ch.set_title("Active vs reference median")
        ax_ch.set_ylabel("ADU")
        stats["ref_median"] = ref_stats["median"]
        stats["active_median"] = sci_stats["median"]
    else:
        work = np.where(np.isfinite(img), img, np.nan)
        work = work - np.nanmedian(work)
        spec = np.abs(np.fft.fftshift(np.fft.fft2(np.nan_to_num(work))))
        ax_ch.imshow(
            np.log10(spec + 1.0),
            origin="upper",
            cmap="magma",
            interpolation="nearest",
            aspect="equal",
        )
        ax_ch.set_title("log|FFT| (spatial)")
        ax_ch.set_xlabel("fx")
        ax_ch.set_ylabel("fy")

    _save_png(fig, output)
    logging.info(
        "Reset QA: median=%.4g ADU  MAD=%.4g  std=%.4g  hot=%d  cold=%d",
        stats["median"],
        stats["mad"],
        stats["std"],
        n_hot,
        n_cold,
    )
    stats["n_hot"] = float(n_hot)
    stats["n_cold"] = float(n_cold)
    return stats


def plot_ramp_qa(
    cube: np.ndarray,
    sample_index: np.ndarray,
    *,
    output: Path,
    title: str,
    illum_box: tuple[int, int, int, int] | None = None,
    extra_box: tuple[int, int, int, int] | None = None,
    pixels: np.ndarray | None = None,
    slope_fits: Path | None = None,
    rms_fits: Path | None = None,
) -> dict[str, float]:
    """Ramp quality: per-pixel slope, residual RMS, and linearity."""
    data = np.asarray(cube, dtype=np.float64)
    t = np.asarray(sample_index, dtype=np.float64)
    nplane = int(data.shape[0])
    last = data[-1]
    slope, _intercept, rms = fit_ramp(data, t)
    vmin_s, vmax_s = _display_limits(slope)
    vmin_r, vmax_r = _display_limits(rms)
    vmin_l, vmax_l = _display_limits(last)

    illum_slope = None
    if illum_box is not None:
        r0, r1, c0, c1 = illum_box
        illum_slope = slope[r0:r1, c0:c1]
        med_illum = np.array(
            [float(np.nanmedian(plane[r0:r1, c0:c1])) for plane in data],
            dtype=np.float64,
        )
    else:
        med_illum = None
    med_extra = None
    if extra_box is not None:
        er0, er1, ec0, ec1 = extra_box
        med_extra = np.array(
            [float(np.nanmedian(plane[er0:er1, ec0:ec1])) for plane in data],
            dtype=np.float64,
        )
    med_all = np.array(
        [float(np.nanmedian(plane)) for plane in data],
        dtype=np.float64,
    )

    fig = plt.figure(figsize=(12.5, 8.4), layout="constrained")
    gs = fig.add_gridspec(2, 3, hspace=0.28, wspace=0.22)
    fig.suptitle(title, fontsize=12)

    ax_s = fig.add_subplot(gs[0, 0])
    im_s = ax_s.imshow(
        slope,
        origin="upper",
        cmap="magma",
        vmin=vmin_s,
        vmax=vmax_s,
        interpolation="nearest",
        aspect="equal",
    )
    _draw_box(ax_s, illum_box, color="#ff6b6b")
    _draw_box(ax_s, extra_box, color="#4cc9f0", linestyle="--")
    _overlay_pixels(ax_s, pixels)
    ax_s.set_title("Slope [ADU / sample]")
    ax_s.set_xlabel("X [pix]")
    ax_s.set_ylabel("Y [pix]")
    fig.colorbar(im_s, ax=ax_s, fraction=0.046, pad=0.04)

    ax_rms = fig.add_subplot(gs[0, 1])
    im_rms = ax_rms.imshow(
        rms,
        origin="upper",
        cmap="viridis",
        vmin=vmin_r,
        vmax=vmax_r,
        interpolation="nearest",
        aspect="equal",
    )
    _draw_box(ax_rms, illum_box, color="#ff6b6b")
    _draw_box(ax_rms, extra_box, color="#4cc9f0", linestyle="--")
    ax_rms.set_title("Residual RMS [ADU]")
    ax_rms.set_xlabel("X [pix]")
    ax_rms.set_ylabel("Y [pix]")
    fig.colorbar(im_rms, ax=ax_rms, fraction=0.046, pad=0.04)

    ax_last = fig.add_subplot(gs[0, 2])
    im_l = ax_last.imshow(
        last,
        origin="upper",
        cmap="gray",
        vmin=vmin_l,
        vmax=vmax_l,
        interpolation="nearest",
        aspect="equal",
    )
    _draw_box(ax_last, illum_box, color="#ff6b6b")
    _draw_box(ax_last, extra_box, color="#4cc9f0", linestyle="--")
    _overlay_pixels(ax_last, pixels)
    ax_last.set_title("Last CDS sample")
    ax_last.set_xlabel("X [pix]")
    ax_last.set_ylabel("Y [pix]")
    fig.colorbar(im_l, ax=ax_last, fraction=0.046, pad=0.04, label="ADU")

    ax_h = fig.add_subplot(gs[1, 0])
    s_all = _finite(slope)
    lo = hi = None
    if s_all.size:
        lo, hi = np.percentile(s_all, (1.0, 99.0))
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            span = max(abs(float(np.mean(s_all))), 1.0) * 1e-3
            lo, hi = float(np.mean(s_all)) - span, float(np.mean(s_all)) + span
        n_bins = min(80, max(10, int(np.sqrt(s_all.size))))
        _safe_hist(
            ax_h,
            s_all,
            bins=n_bins,
            range_=(lo, hi),
            color="0.55",
            histtype="stepfilled",
            alpha=0.7,
            label="full frame",
            density=True,
        )
    if illum_slope is not None:
        s_ill = _finite(illum_slope)
        if s_ill.size:
            hist_kw: dict = {
                "bins": min(40, max(8, s_ill.size)),
                "color": "C0",
                "histtype": "step",
                "linewidth": 1.4,
                "label": "photonic box",
                "density": True,
            }
            if lo is not None and hi is not None:
                hist_kw["range_"] = (lo, hi)
            else:
                hist_kw["range_"] = None
            _safe_hist(ax_h, s_ill, **hist_kw)
    ax_h.set_title("Slope histogram")
    ax_h.set_xlabel("ADU / sample")
    ax_h.set_ylabel("Density")
    ax_h.legend(fontsize=8)
    ax_h.grid(True, alpha=0.3)

    ax_lin = fig.add_subplot(gs[1, 1])
    ax_lin.plot(t, med_all, "o-", color="0.45", markersize=4, label="median full")
    if med_illum is not None:
        ax_lin.plot(t, med_illum, "s-", color="C0", markersize=5, label="median box")
    if med_extra is not None:
        ax_lin.plot(
            t,
            med_extra,
            "d--",
            color="#4cc9f0",
            markersize=5,
            label="median ROI",
        )
    if pixels is not None and pixels.size:
        pix_mean = np.array(
            [float(np.mean(data[i, pixels[:, 0], pixels[:, 1]])) for i in range(nplane)],
            dtype=np.float64,
        )
        ax_lin.plot(t, pix_mean, "^-", color="C3", markersize=5, label="10 brightest")
    ax_lin.set_title("Linearity (median vs sample)")
    ax_lin.set_xlabel("Sample index")
    ax_lin.set_ylabel("ADU")
    ax_lin.legend(fontsize=8)
    ax_lin.grid(True, alpha=0.3)

    ax_ch = fig.add_subplot(gs[1, 2])
    n_out = n_outputs_for_shape(slope.shape)
    chan = channel_profile(slope, n_out) if n_out else None
    if chan is not None:
        ax_ch.bar(np.arange(chan.size), chan, color="C4", width=0.85)
        ax_ch.set_title("Slope per output")
        ax_ch.set_xlabel("Output")
        ax_ch.set_ylabel("ADU / sample")
        ax_ch.grid(True, alpha=0.3, axis="y")
    else:
        col_s = np.nanmean(slope, axis=0)
        ax_ch.plot(np.arange(col_s.size), col_s, color="C4", linewidth=0.9)
        ax_ch.set_title("Slope column mean")
        ax_ch.set_xlabel("X [pix]")
        ax_ch.set_ylabel("ADU / sample")
        ax_ch.grid(True, alpha=0.3)

    _save_png(fig, output)

    slope_stats = _stats(slope)
    rms_stats = _stats(rms)
    summary = {
        "nplane": float(nplane),
        "slope_median": slope_stats["median"],
        "slope_mad": slope_stats["mad"],
        "resid_rms_median": rms_stats["median"],
    }
    if illum_slope is not None:
        box_stats = _stats(illum_slope)
        summary["slope_illum_median"] = box_stats["median"]
        summary["slope_illum_mad"] = box_stats["mad"]
        logging.info(
            "Ramp QA: n=%d  slope_med=%.4g ADU/sample  "
            "illum_slope_med=%.4g  resid_rms_med=%.4g ADU",
            nplane,
            slope_stats["median"],
            box_stats["median"],
            rms_stats["median"],
        )
        if np.isfinite(box_stats["median"]) and abs(box_stats["median"]) < max(
            1e-6, 0.1 * box_stats["mad"] if np.isfinite(box_stats["mad"]) else 1e-3
        ):
            logging.warning(
                "Photonic-box median slope is consistent with zero — "
                "pixels may not be integrating"
            )
    else:
        logging.info(
            "Ramp QA: n=%d  slope_med=%.4g ADU/sample  resid_rms_med=%.4g ADU",
            nplane,
            slope_stats["median"],
            rms_stats["median"],
        )

    if slope_fits is not None:
        save_map_fits(
            slope_fits,
            slope,
            bunit="ADU / sample",
            history="Per-pixel linear slope of CDS-relative UpTheRamp cube",
        )
    if rms_fits is not None:
        save_map_fits(
            rms_fits,
            rms,
            bunit="ADU",
            history="Per-pixel residual RMS after linear UpTheRamp fit",
        )
    return summary


def run_detector_qa(
    *,
    out_dir: Path,
    cds_cube: np.ndarray,
    sample_index: np.ndarray,
    reset_frame: np.ndarray | None,
    reset_name: str | None,
    first_science: np.ndarray | None,
    illum_box: tuple[int, int, int, int] | None,
    pixels: np.ndarray | None,
    n_sigma: float,
    cds_short: str,
    extra_box: tuple[int, int, int, int] | None = None,
) -> None:
    """Write reset and ramp QA products into *out_dir*."""
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if reset_frame is not None:
        reset_title = f"H2RG reset QA — {reset_name or 'reset frame'}"
        reset_image = reset_frame
    elif first_science is not None:
        reset_title = "H2RG reference QA — first science sample (no reset file)"
        reset_image = first_science
    else:
        reset_image = None
        reset_title = ""

    if reset_image is not None:
        plot_reset_qa(
            reset_image,
            output=out_dir / "msac_qa_reset.png",
            title=reset_title,
            n_sigma=n_sigma,
            illum_box=illum_box,
            extra_box=extra_box,
        )
    else:
        logging.warning("Detector QA: no reset or first-sample frame to analyse")

    if cds_cube.shape[0] < 2:
        logging.warning("Detector QA: need ≥2 ramp samples for slope maps")
        return

    plot_ramp_qa(
        cds_cube,
        sample_index,
        output=out_dir / "msac_qa_ramp.png",
        title=f"H2RG ramp QA — {cds_short}",
        illum_box=illum_box,
        extra_box=extra_box,
        pixels=pixels,
        slope_fits=out_dir / "msac_qa_slope.fits",
        rms_fits=out_dir / "msac_qa_resid_rms.fits",
    )
