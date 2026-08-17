#!/usr/bin/env python3
"""Plot illuminated-region ADU vs MSAC UpTheRamp file index.

Default data root (on the acquisition machine)::

    ~/frames/H2RG_ASIC/UpTheRamp/

MSAC writes each session into a subdirectory of that root. By default the
script selects the **latest** subdirectory (by modification time), then
loads **all** FITS there.

Frames are stacked in file-index order (last plane of each FITS, or all
planes of a single multi-sample cube). If a **reset frame** is present
(``_R0001`` / ``_R######`` in the filename), each science sample is
``frame - reset``. Otherwise each plane is ``frame[k] - frame[0]``.

Two reduced cubes are written next to the plot:

* full-frame ``msac_uptheramp_frame_minus_first.fits``
* illuminated-box crop ``msac_uptheramp_frame_minus_first_illum.fits``

With first-sample subtraction the zero self-subtraction plane is
**omitted** from both cubes. Reset subtraction keeps every science plane.

Illuminated box defaults to the **Photonic chip** WinMode
(``X=1024–1087``, ``Y=928–959``). The **10 brightest** pixels are
chosen once on the last CDS plane (``last − reset`` or ``last − first``)
after outlier rejection, then those same pixels are averaged on every
sample. No background ROI is subtracted. Override the box with
``--illum-roi``, ``--illum-center``, or ``--illum-size``.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

# Avoid Qt ABI clashes on nott-server (e.g. system Qt 5.15.17 vs pip 5.15.15).
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

DEFAULT_RAMP_ROOT = Path.home() / "frames" / "H2RG_ASIC" / "UpTheRamp"
DEFAULT_N_ILLUM_PIXELS = 100
DEFAULT_N_BRIGHTEST = 10
DEFAULT_ILLUM_SIZE = 20
DEFAULT_ILLUM_CENTER_X = 1045
DEFAULT_ILLUM_CENTER_Y = 943
DEFAULT_ILLUM_ROI = 2
# Match H2RG GUI WindowMode "Photonic chip" (inclusive detector pixels).
PHOTONIC_CHIP_X1 = 1024
PHOTONIC_CHIP_X2 = 1087
PHOTONIC_CHIP_Y1 = 928
PHOTONIC_CHIP_Y2 = 959
H2RG_SECTION = "H2RG DETECTOR"
# Full-frame H2RG; smaller shapes are treated as windowed readouts.
DEFAULT_FULL_FRAME = 2048
DEFAULT_SEED = 0
DEFAULT_N_SIGMA = 3.0

# MSAC names often embed counters, e.g. ``…_N000012_M000001.fits`` or
# a reset frame ``…_R0001.fits``. Prefer the science tag (M or N) that
# varies across the session; do not assume it is the trailing field.
FILE_INDEX_RE = re.compile(r"_(?P<tag>[MNR])(?P<index>\d+)", re.IGNORECASE)
TRAILING_DIGITS_RE = re.compile(r"_(\d+)\s*$")
SCIENCE_TAGS = frozenset({"M", "N"})
RESET_TAG = "R"


def _fits_in_dir(directory: Path) -> list[Path]:
    return [
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() == ".fits"
    ]


def resolve_ramp_dir(path: Path) -> Path:
    """Resolve *path* to a directory that contains FITS.

    If *path* already has ``.fits`` files, use it. Otherwise pick the
    newest subdirectory (by ``mtime``, then name) that contains FITS.
    """
    root = path.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Ramp directory not found: {root}")

    if _fits_in_dir(root):
        return root

    subdirs = [p for p in root.iterdir() if p.is_dir()]
    if not subdirs:
        raise FileNotFoundError(
            f"No FITS files and no subdirectories under {root}"
        )

    subdirs.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    for candidate in subdirs:
        if _fits_in_dir(candidate):
            logging.info("Using latest session folder: %s", candidate)
            return candidate.resolve()

    raise FileNotFoundError(
        f"No FITS files found in {root} or its subdirectories"
    )


def file_indices_from_name(name: str) -> dict[str, int]:
    """Return all ``M``/``N``/``R`` counters found in *name* (last wins per tag)."""
    stem = Path(name).stem
    found: dict[str, int] = {}
    for match in FILE_INDEX_RE.finditer(stem):
        found[match.group("tag").upper()] = int(match.group("index"))
    return found


def choose_index_tag(paths: list[Path]) -> str | None:
    """Pick ``M`` or ``N`` according to which varies most across *paths*."""
    values: dict[str, set[int]] = {"M": set(), "N": set()}
    for path in paths:
        for tag, index in file_indices_from_name(path.name).items():
            if tag in SCIENCE_TAGS:
                values[tag].add(index)

    candidates = [
        (tag, len(vals))
        for tag, vals in values.items()
        if vals
    ]
    if not candidates:
        return None
    # Prefer the tag with the most distinct values; tie-break N then M
    # (N often carries the acquisition counter when M is fixed at 1).
    candidates.sort(key=lambda item: (item[1], item[0] == "N"), reverse=True)
    tag, n_unique = candidates[0]
    logging.info(
        "File-index tags across session: M=%s N=%s → using %s (%d unique)",
        sorted(values["M"])[:8] if values["M"] else "—",
        sorted(values["N"])[:8] if values["N"] else "—",
        tag,
        n_unique,
    )
    if n_unique <= 1 and len(paths) > 1:
        logging.warning(
            "Chosen tag %s has only %d unique value(s) for %d files; "
            "check MSAC naming",
            tag,
            n_unique,
            len(paths),
        )
    return tag


def file_index_from_name(
    name: str, *, preferred_tag: str | None = None
) -> tuple[str, int] | None:
    """Return ``(tag, index)`` for plotting.

    If *preferred_tag* is set (``M``/``N``), use that counter. Otherwise use
    the last ``_M``/``_N`` field in the name, then trailing ``_######``.
    Reset ``_R`` counters are ignored here; see ``is_reset_fits``.
    """
    found = file_indices_from_name(name)
    science = {tag: index for tag, index in found.items() if tag in SCIENCE_TAGS}
    if preferred_tag:
        tag = preferred_tag.upper()
        if tag in science:
            return tag, science[tag]
    if science:
        stem = Path(name).stem
        matches = [
            match
            for match in FILE_INDEX_RE.finditer(stem)
            if match.group("tag").upper() in SCIENCE_TAGS
        ]
        if matches:
            match = matches[-1]
            return match.group("tag").upper(), int(match.group("index"))

    trailing = TRAILING_DIGITS_RE.search(Path(name).stem)
    if trailing:
        return "#", int(trailing.group(1))
    return None


def is_reset_fits(name: str) -> bool:
    """True if *name* is an MSAC reset frame (``_R0001`` / ``_R######``)."""
    found = file_indices_from_name(name)
    if RESET_TAG not in found:
        return False
    science = {tag for tag in found if tag in SCIENCE_TAGS}
    if not science:
        return True
    matches = list(FILE_INDEX_RE.finditer(Path(name).stem))
    return bool(matches) and matches[-1].group("tag").upper() == RESET_TAG


def split_science_and_reset(
    paths: list[Path],
) -> tuple[list[Path], list[Path]]:
    """Split FITS paths into science ramps and reset frames."""
    science: list[Path] = []
    resets: list[Path] = []
    for path in paths:
        if is_reset_fits(path.name):
            resets.append(path)
        else:
            science.append(path)
    return science, resets


def load_reset_reference(
    reset_paths: list[Path],
) -> tuple[np.ndarray, Path] | None:
    """Load the last plane of the first reset FITS (lowest ``R`` index)."""
    if not reset_paths:
        return None
    ranked = sorted(
        reset_paths,
        key=lambda p: (
            file_indices_from_name(p.name).get(RESET_TAG, 10**9),
            p.name.lower(),
        ),
    )
    chosen = ranked[0]
    if len(ranked) > 1:
        logging.info(
            "Found %d reset frame(s); using %s (R=%s)",
            len(ranked),
            chosen.name,
            file_indices_from_name(chosen.name).get(RESET_TAG),
        )
    cube, _header = load_ramp_cube(chosen)
    reference = np.asarray(last_plane(cube), dtype=np.float64)
    logging.info(
        "Reset reference %s: shape=%s",
        chosen.name,
        reference.shape,
    )
    return reference, chosen


def illuminated_box(
    shape: tuple[int, int],
    box_height: int,
    box_width: int,
    *,
    center_x: int,
    center_y: int,
) -> tuple[int, int, int, int]:
    """Return ``(row0, row1, col0, col1)`` for a box around ``(center_x, center_y)``."""
    height, width = shape
    if box_height <= 0 or box_width <= 0:
        raise ValueError("Illuminated box size must be positive")
    row0 = int(center_y) - box_height // 2
    col0 = int(center_x) - box_width // 2
    row1 = row0 + box_height
    col1 = col0 + box_width
    if row0 < 0 or col0 < 0 or row1 > height or col1 > width:
        raise ValueError(
            f"Illuminated box {box_height}x{box_width} at "
            f"(X={center_x}, Y={center_y}) is outside image shape {shape} "
            f"(rows[{row0}:{row1}), cols[{col0}:{col1}))"
        )
    return row0, row1, col0, col1


def load_h2rg_roi_xywh(index: int) -> tuple[int, int, int, int] | None:
    """Return ``(x, y, w, h)`` for H2RG ROI *index* from merged config, or None."""
    try:
        from nottcontrol import config
    except Exception as exc:
        logging.warning("Could not import nottcontrol config: %s", exc)
        return None
    key = f"ROI {index}"
    try:
        values = config.getarray(H2RG_SECTION, key, dtype=int)
    except Exception:
        return None
    if len(values) != 4:
        logging.warning(
            "[%s] %s has %d values (need x,y,w,h)",
            H2RG_SECTION,
            key,
            len(values),
        )
        return None
    return int(values[0]), int(values[1]), int(values[2]), int(values[3])


def illuminated_box_from_xywh(
    shape: tuple[int, int],
    x: int,
    y: int,
    w: int,
    h: int,
) -> tuple[int, int, int, int]:
    """Return ``(row0, row1, col0, col1)`` for an ``x,y,w,h`` ROI."""
    height, width = shape
    if w <= 0 or h <= 0:
        raise ValueError(f"ROI size must be positive (got w={w}, h={h})")
    row0, col0 = int(y), int(x)
    row1, col1 = row0 + int(h), col0 + int(w)
    if row0 < 0 or col0 < 0 or row1 > height or col1 > width:
        raise ValueError(
            f"ROI x={x},y={y},w={w},h={h} is outside image shape {shape} "
            f"(rows[{row0}:{row1}), cols[{col0}:{col1}))"
        )
    return row0, row1, col0, col1


def photonic_chip_xywh() -> tuple[int, int, int, int]:
    """Return ``(x, y, w, h)`` for the Photonic chip WinMode."""
    return (
        PHOTONIC_CHIP_X1,
        PHOTONIC_CHIP_Y1,
        PHOTONIC_CHIP_X2 - PHOTONIC_CHIP_X1 + 1,
        PHOTONIC_CHIP_Y2 - PHOTONIC_CHIP_Y1 + 1,
    )


def photonic_chip_label() -> str:
    return (
        f"Photonic chip (X={PHOTONIC_CHIP_X1}–{PHOTONIC_CHIP_X2}, "
        f"Y={PHOTONIC_CHIP_Y1}–{PHOTONIC_CHIP_Y2})"
    )


def photonic_chip_illum_box(
    shape: tuple[int, int],
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Return ``(image_box, detector_box)`` as ``(row0, row1, col0, col1)``.

    Full-frame cubes are cropped at the WinMode coordinates. A delivered
    frame that is already the photonic-chip size uses the whole image, with
    detector-pixel labels still at ``1024–1087``, ``928–959``.
    """
    x, y, w, h = photonic_chip_xywh()
    det_box = (y, y + h, x, x + w)
    height, width = int(shape[0]), int(shape[1])
    if height == h and width == w:
        return (0, h, 0, w), det_box
    return illuminated_box_from_xywh((height, width), x, y, w, h), det_box


def resolve_illum_center(
    shape: tuple[int, int],
    *,
    center_x: int | None,
    center_y: int | None,
    full_frame: int = DEFAULT_FULL_FRAME,
) -> tuple[int, int]:
    """Pick illuminated-box centre for full-frame vs windowed readouts.

    Explicit ``center_x`` / ``center_y`` always win. Otherwise a frame smaller
    than *full_frame* in either axis is assumed windowed with the spot at the
    image centre; full-frame uses the lab defaults (X=1045, Y=943).
    """
    height, width = int(shape[0]), int(shape[1])
    if center_x is not None and center_y is not None:
        return int(center_x), int(center_y)
    if height < full_frame or width < full_frame:
        cx = width // 2
        cy = height // 2
        logging.info(
            "Windowed frame %d×%d (< %d): illuminated centre at image mid "
            "X=%d Y=%d",
            width,
            height,
            full_frame,
            cx,
            cy,
        )
        return cx, cy
    return DEFAULT_ILLUM_CENTER_X, DEFAULT_ILLUM_CENTER_Y


def choose_pixels(
    shape: tuple[int, int],
    n_pixels: int,
    seed: int,
    *,
    row_slice: tuple[int, int],
    col_slice: tuple[int, int],
) -> np.ndarray:
    height, width = shape
    row0, row1 = row_slice
    col0, col1 = col_slice
    mask = np.zeros((height, width), dtype=bool)
    mask[row0:row1, col0:col1] = True
    coords = np.column_stack(np.nonzero(mask))
    if n_pixels > len(coords):
        raise ValueError(
            f"n_pixels ({n_pixels}) exceeds illuminated box size ({len(coords)})"
        )
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(coords), size=n_pixels, replace=False)
    return coords[pick]


def _mad_scale(values: np.ndarray) -> tuple[float, float]:
    """Return ``(median, 1.4826 * MAD)`` for *values* (finite only)."""
    work = np.asarray(values, dtype=np.float64)
    work = work[np.isfinite(work)]
    if work.size == 0:
        return float("nan"), float("nan")
    med = float(np.median(work))
    mad = float(np.median(np.abs(work - med)))
    scale = 1.4826 * mad if mad > 0 else float(np.std(work))
    if not np.isfinite(scale) or scale < 1e-12:
        scale = 0.0
    return med, scale


def isolated_hot_mask(image: np.ndarray, *, n_sigma: float) -> np.ndarray:
    """True for isolated hot spikes (brighter than every 3×3 neighbour).

    A compact waveguide spot (2+ adjacent bright pixels) is kept; a
    single-pixel cosmic or hot pixel is rejected.
    """
    img = np.asarray(image, dtype=np.float64)
    finite = np.isfinite(img)
    med, scale = _mad_scale(img)
    if not finite.any() or not np.isfinite(med):
        return np.zeros(img.shape, dtype=bool)
    padded = np.pad(
        np.where(finite, img, np.nan),
        1,
        mode="constant",
        constant_values=np.nan,
    )
    neigh_max = np.full(img.shape, -np.inf)
    height, width = img.shape
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            sl = padded[1 + dr : 1 + dr + height, 1 + dc : 1 + dc + width]
            neigh_max = np.fmax(
                neigh_max, np.where(np.isfinite(sl), sl, -np.inf)
            )
    above_bg = img > (med + n_sigma * scale) if scale > 0 else img > med
    neigh_is_bg = (
        neigh_max < (med + n_sigma * scale) if scale > 0 else ~np.isfinite(neigh_max)
    )
    return finite & above_bg & neigh_is_bg & (img > neigh_max)


def select_brightest_after_outliers(
    image: np.ndarray,
    row0: int,
    row1: int,
    col0: int,
    col1: int,
    *,
    n_brightest: int,
    n_sigma: float,
) -> tuple[np.ndarray, int]:
    """Return ``(coords_rc, n_rejected)`` for the N brightest box pixels.

    Rejects non-finite values, faint/dead pixels (low-side MAD clip), and
    isolated hot spikes, then ranks what remains on *image*.
    """
    crop = np.asarray(image[row0:row1, col0:col1], dtype=np.float64)
    finite = np.isfinite(crop)
    med, scale = _mad_scale(crop)
    dead = np.zeros(crop.shape, dtype=bool)
    if np.isfinite(med) and scale > 0:
        dead = finite & (crop < med - n_sigma * scale)
    hot = isolated_hot_mask(crop, n_sigma=n_sigma)
    keep = finite & ~dead & ~hot
    n_rejected = int(crop.size - keep.sum())
    if not keep.any():
        return np.empty((0, 2), dtype=int), n_rejected
    vals = crop[keep]
    ys, xs = np.nonzero(keep)
    order = np.argsort(vals)[::-1]
    n_used = min(max(1, int(n_brightest)), int(order.size))
    pick = order[:n_used]
    coords = np.column_stack((ys[pick] + row0, xs[pick] + col0))
    return coords, n_rejected


def sigma_clip_mean(
    values: np.ndarray,
    *,
    n_sigma: float = 3.0,
    max_iter: int = 5,
) -> tuple[float, int, int]:
    work = np.asarray(values, dtype=np.float64).ravel()
    n_total = int(work.size)
    if n_total == 0:
        return float("nan"), 0, 0
    for _ in range(max_iter):
        if work.size < 3:
            break
        mu = float(np.mean(work))
        sigma = float(np.std(work))
        if not np.isfinite(sigma) or sigma < 1e-12:
            break
        keep = np.abs(work - mu) <= n_sigma * sigma
        if bool(keep.all()):
            break
        work = work[keep]
        if work.size == 0:
            work = np.asarray(values, dtype=np.float64).ravel()
            break
    return float(np.mean(work)), int(work.size), int(n_total - work.size)


def load_ramp_cube(path: Path) -> tuple[np.ndarray, dict]:
    """Return ``(nsamples, ny, nx)`` float64 cube and primary header dict."""
    from astropy.io import fits

    with fits.open(path, memmap=False) as hdul:
        header = dict(hdul[0].header)
        data = np.asarray(hdul[0].data)

    if data.ndim == 2:
        cube = data[np.newaxis, ...]
    elif data.ndim == 3:
        naxis3 = int(header.get("NAXIS3", data.shape[0]))
        if data.shape[0] == naxis3:
            cube = data
        elif data.shape[-1] == naxis3:
            cube = np.moveaxis(data, -1, 0)
        else:
            cube = data
    else:
        raise ValueError(f"{path.name}: expected 2-D or 3-D FITS, got shape {data.shape}")

    return np.asarray(cube, dtype=np.float64), header


def list_ramp_fits(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise FileNotFoundError(f"Ramp directory not found: {directory}")
    paths = sorted(
        _fits_in_dir(directory),
        key=lambda p: (p.stat().st_mtime, p.name.lower()),
    )
    if not paths:
        raise FileNotFoundError(f"No FITS files in {directory}")
    return paths


def last_plane(cube: np.ndarray) -> np.ndarray:
    """Science-like sample: last saved ramp plane (or the only 2-D frame)."""
    return cube[-1]


def relative_to_first(cube: np.ndarray) -> np.ndarray:
    """Return ``cube[k] - cube[0]`` for every plane (float64)."""
    if cube.ndim != 3:
        raise ValueError(f"Expected (n, y, x) cube, got shape {cube.shape}")
    if cube.shape[0] < 1:
        raise ValueError("Cube has no planes")
    first = cube[0]
    return np.asarray(cube, dtype=np.float64) - first


def relative_to_reference(cube: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Return ``cube[k] - reference`` for every plane (float64)."""
    data = np.asarray(cube, dtype=np.float64)
    ref = np.asarray(reference, dtype=np.float64)
    if data.ndim != 3:
        raise ValueError(f"Expected (n, y, x) cube, got shape {data.shape}")
    if ref.ndim != 2:
        raise ValueError(f"Expected 2-D reset frame, got shape {ref.shape}")
    if ref.shape != data.shape[1:]:
        raise ValueError(
            f"Reset shape {ref.shape} does not match science {data.shape[1:]}"
        )
    return data - ref


def region_mean(
    image: np.ndarray,
    row0: int,
    row1: int,
    col0: int,
    col1: int,
    *,
    n_sigma: float,
) -> float:
    """Sigma-clipped mean of ``image[row0:row1, col0:col1]``."""
    region = np.asarray(image[row0:row1, col0:col1], dtype=np.float64).ravel()
    mean_val, _n_kept, _n_rej = sigma_clip_mean(region, n_sigma=n_sigma)
    return float(mean_val)


def subtract_roi_pedestal(
    cube: np.ndarray,
    *,
    row0: int,
    row1: int,
    col0: int,
    col1: int,
    n_sigma: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Subtract per-plane sigma-clipped ROI mean from *cube*.

    Returns ``(corrected_cube, pedestal_per_plane)``.
    """
    if cube.ndim != 3:
        raise ValueError(f"Expected (n, y, x) cube, got shape {cube.shape}")
    out = np.empty(cube.shape, dtype=np.float64)
    pedestals = np.empty(cube.shape[0], dtype=np.float64)
    for i, plane in enumerate(cube):
        ped = region_mean(plane, row0, row1, col0, col1, n_sigma=n_sigma)
        pedestals[i] = ped
        out[i] = np.asarray(plane, dtype=np.float64) - ped
    return out, pedestals


def drop_reference_plane(cube: np.ndarray) -> np.ndarray:
    """Drop plane 0 of a frame−first cube (always ~0)."""
    if cube.ndim != 3:
        raise ValueError(f"Expected (n, y, x) cube, got shape {cube.shape}")
    if cube.shape[0] < 2:
        raise ValueError(
            "Need at least 2 samples to write a cube without the zero "
            f"reference plane (got {cube.shape[0]})"
        )
    return cube[1:]


def save_cube_fits(
    path: Path,
    cube: np.ndarray,
    *,
    reference_header: dict | None = None,
    history: str,
    extra_cards: dict | None = None,
) -> None:
    """Write a ``(n, y, x)`` float32 cube to *path*."""
    from astropy.io import fits

    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(cube, dtype=np.float32)
    if data.ndim != 3:
        raise ValueError(f"Expected 3-D cube, got shape {data.shape}")

    header = fits.Header()
    if reference_header:
        for key in (
            "TELESCOP",
            "INSTRUME",
            "DETECTOR",
            "ORIGIN",
            "OBJECT",
            "DATE-OBS",
            "EXPTIME",
            "NGROUPS",
            "NREADS",
            "NDROPS",
            "DETMODE",
        ):
            if key in reference_header:
                try:
                    header[key] = reference_header[key]
                except (ValueError, TypeError):
                    pass
    header["BUNIT"] = "ADU"
    header["REDUCT"] = ("FRAME-FIRST", "Each plane = sample - first sample")
    header["SKIPREF"] = (
        True,
        "Omitted plane 0 (frame0-frame0 == 0)",
    )
    header["NAXIS"] = 3
    header["NAXIS1"] = data.shape[2]
    header["NAXIS2"] = data.shape[1]
    header["NAXIS3"] = data.shape[0]
    if extra_cards:
        for key, value in extra_cards.items():
            header[key] = value
    header.add_history(history)

    fits.PrimaryHDU(data=data, header=header).writeto(path, overwrite=True)
    logging.info(
        "Wrote CDS-relative cube (%d planes, %d×%d): %s",
        data.shape[0],
        data.shape[1],
        data.shape[2],
        path,
    )


def illuminated_mean_for_image(
    image: np.ndarray,
    pixels: np.ndarray,
    *,
    n_sigma: float,
) -> float:
    values = np.array(
        [float(image[int(r), int(c)]) for r, c in pixels],
        dtype=np.float64,
    )
    mean_val, n_kept, n_rej = sigma_clip_mean(values, n_sigma=n_sigma)
    logging.debug(
        "illum mean=%.4g (kept %d / %d, rej %d)",
        mean_val,
        n_kept,
        n_kept + n_rej,
        n_rej,
    )
    return mean_val


def pixel_values(image: np.ndarray, pixels: np.ndarray) -> np.ndarray:
    return np.array(
        [float(image[int(r), int(c)]) for r, c in pixels],
        dtype=np.float64,
    )


def _display_limits(image: np.ndarray) -> tuple[float, float]:
    finite = np.asarray(image, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return 0.0, 1.0
    lo, hi = np.percentile(finite, (5.0, 99.5))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = float(np.min(finite)), float(np.max(finite))
        if hi <= lo:
            hi = lo + 1.0
    return float(lo), float(hi)


def _draw_box(
    ax,
    row0: int,
    row1: int,
    col0: int,
    col1: int,
    *,
    color: str,
    label: str,
) -> None:
    from matplotlib.patches import Rectangle

    ax.add_patch(
        Rectangle(
            (col0 - 0.5, row0 - 0.5),
            col1 - col0,
            row1 - row0,
            fill=False,
            edgecolor=color,
            linewidth=1.2,
            label=label,
        )
    )


def plot_file_series(
    *,
    indices: np.ndarray,
    means: np.ndarray,
    names: list[str],
    index_tag: str,
    pixel_matrix: np.ndarray | None,
    output: Path,
    title: str,
    show: bool,
    full_frame: np.ndarray | None = None,
    illum_frame: np.ndarray | None = None,
    illum_box: tuple[int, int, int, int] | None = None,
    bg_box: tuple[int, int, int, int] | None = None,
    region_label: str | None = None,
    detector_box: tuple[int, int, int, int] | None = None,
    cds_label: str = "last − first",
    cds_short: str = "frame−first",
    flux_label: str = "10 brightest",
) -> None:
    show_pixels = pixel_matrix is not None and pixel_matrix.size > 0
    show_images = full_frame is not None and illum_frame is not None
    height_ratios: list[float] = []
    if show_images:
        height_ratios.append(1.4)
    height_ratios.append(1.0)
    if show_pixels:
        height_ratios.append(1.0)
    n_plot_rows = len(height_ratios)
    fig = plt.figure(figsize=(10.5, 3.6 * n_plot_rows + 0.8), layout="constrained")
    gs = fig.add_gridspec(n_plot_rows, 2, height_ratios=height_ratios, hspace=0.28, wspace=0.16)

    row = 0
    if show_images:
        ax_full = fig.add_subplot(gs[row, 0])
        ax_illum = fig.add_subplot(gs[row, 1])
        vmin, vmax = _display_limits(full_frame)
        im_full = ax_full.imshow(
            full_frame,
            origin="upper",
            cmap="gray",
            vmin=vmin,
            vmax=vmax,
            interpolation="nearest",
            aspect="equal",
        )
        ax_full.set_title(f"Full frame ({cds_label})")
        ax_full.set_xlabel("X [pix]")
        ax_full.set_ylabel("Y [pix]")
        if illum_box is not None:
            irow0, irow1, icol0, icol1 = illum_box
            box_label = region_label or (
                f"Illum X={icol0}–{icol1 - 1}, Y={irow0}–{irow1 - 1}"
            )
            _draw_box(
                ax_full,
                *illum_box,
                color="#ff6b6b",
                label=box_label,
            )
        if bg_box is not None:
            _draw_box(ax_full, *bg_box, color="#4cc9f0", label="Bg")
        if illum_box is not None or bg_box is not None:
            ax_full.legend(loc="upper right", fontsize=8, framealpha=0.8)
        fig.colorbar(im_full, ax=ax_full, fraction=0.046, pad=0.04, label="ADU")

        vmin_i, vmax_i = _display_limits(illum_frame)
        axis_box = detector_box if detector_box is not None else illum_box
        if axis_box is not None:
            irow0, irow1, icol0, icol1 = axis_box
            illum_extent = (
                icol0 - 0.5,
                icol1 - 0.5,
                irow1 - 0.5,
                irow0 - 0.5,
            )
            if region_label:
                illum_title = f"{region_label}\n({cds_label})"
            else:
                illum_title = (
                    f"Illuminated region ({cds_label})\n"
                    f"X={icol0}–{icol1 - 1}, Y={irow0}–{irow1 - 1} "
                    f"({icol1 - icol0}×{irow1 - irow0} pix)"
                )
        else:
            illum_extent = None
            illum_title = region_label or f"Illuminated region ({cds_label})"
        im_illum = ax_illum.imshow(
            illum_frame,
            origin="upper",
            cmap="gray",
            vmin=vmin_i,
            vmax=vmax_i,
            interpolation="nearest",
            aspect="equal",
            extent=illum_extent,
        )
        ax_illum.set_title(illum_title)
        ax_illum.set_xlabel("X [pix]")
        ax_illum.set_ylabel("Y [pix]")
        fig.colorbar(im_illum, ax=ax_illum, fraction=0.046, pad=0.04, label="ADU")
        row += 1

    ax_mean = fig.add_subplot(gs[row, :])
    ax_mean.plot(indices, means, "o-", markersize=5, color="C0")
    for index, mean_val, name in zip(indices, means, names):
        logging.info(
            "%s: index=%s%d  illum_mean=%.4g ADU",
            name,
            index_tag,
            int(index),
            mean_val,
        )
    ax_mean.set_ylabel(f"{flux_label} ({cds_short}) [ADU]")
    ax_mean.set_title(title)
    ax_mean.grid(True, alpha=0.3)
    if not show_pixels:
        ax_mean.set_xlabel(f"File index ({index_tag})")

    if show_pixels:
        ax_pix = fig.add_subplot(gs[row + 1, :], sharex=ax_mean)
        for i in range(pixel_matrix.shape[1]):
            ax_pix.plot(
                indices,
                pixel_matrix[:, i],
                "-",
                alpha=0.25,
                linewidth=0.7,
                color="C1",
            )
        ax_pix.set_ylabel(f"Pixel ({cds_short}) [ADU]")
        ax_pix.set_xlabel(f"File index ({index_tag})")
        ax_pix.grid(True, alpha=0.3)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    logging.info("Wrote plot: %s", output)
    if show:
        logging.info(
            "Interactive --show is disabled (Agg backend); open the PNG instead."
        )
    plt.close(fig)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot MSAC UpTheRamp FITS: full frame, illuminated crop, "
            "and illuminated-region ADU vs file index (_M / _N)."
        )
    )
    parser.add_argument(
        "--ramp-dir",
        type=Path,
        default=DEFAULT_RAMP_ROOT,
        help=(
            "MSAC UpTheRamp root or a specific session folder "
            f"(default: {DEFAULT_RAMP_ROOT}; picks the latest subfolder "
            "that contains FITS)"
        ),
    )
    parser.add_argument(
        "--file",
        type=Path,
        nargs="*",
        default=None,
        help="Specific FITS file(s). Relative paths are under --ramp-dir.",
    )
    parser.add_argument(
        "--latest",
        type=int,
        default=None,
        metavar="N",
        help="Use only the N newest science FITS (default: all files in the session)",
    )
    parser.add_argument(
        "--reset-file",
        type=Path,
        default=None,
        help=(
            "Reset FITS to subtract from each science sample. "
            "Default: the lowest-index _R###### file in the session folder, "
            "if present"
        ),
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Ignore reset frames and subtract the first science sample instead",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Plot every FITS in --ramp-dir (default behaviour)",
    )
    parser.add_argument(
        "--index-tag",
        choices=("M", "N", "auto"),
        default="auto",
        help=(
            "Which filename counter to use on the x-axis: M, N, or auto "
            "(pick the tag that varies most across files; default: auto)"
        ),
    )
    parser.add_argument(
        "--n-illum-pixels",
        type=int,
        default=DEFAULT_N_ILLUM_PIXELS,
        help=(
            "Deprecated. Flux uses --n-brightest after outlier rejection "
            f"(this flag is ignored; default was {DEFAULT_N_ILLUM_PIXELS} random pixels)"
        ),
    )
    parser.add_argument(
        "--n-brightest",
        type=int,
        default=DEFAULT_N_BRIGHTEST,
        metavar="N",
        help=(
            "Select N brightest illuminated-box pixels on the last CDS plane "
            f"after outlier rejection, and average those same pixels on every "
            f"sample (default: {DEFAULT_N_BRIGHTEST})"
        ),
    )
    parser.add_argument(
        "--illum-roi",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Use [H2RG DETECTOR] ROI N as the illuminated box. "
            "Default is the Photonic chip WinMode "
            f"(X={PHOTONIC_CHIP_X1}–{PHOTONIC_CHIP_X2}, "
            f"Y={PHOTONIC_CHIP_Y1}–{PHOTONIC_CHIP_Y2}). "
            "Ignored if --illum-center or --illum-size is set."
        ),
    )
    parser.add_argument(
        "--bg-roi",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Optional [H2RG DETECTOR] ROI N subtracted as a pedestal. "
            "Off by default."
        ),
    )
    parser.add_argument(
        "--no-bg-roi",
        action="store_true",
        help="Accepted for compatibility; background ROI is off by default",
    )
    parser.add_argument(
        "--illum-size",
        type=int,
        nargs="+",
        default=None,
        metavar="N",
        help=(
            f"Box size SIZE or HEIGHT WIDTH (overrides ROI; "
            f"legacy default was {DEFAULT_ILLUM_SIZE})"
        ),
    )
    parser.add_argument(
        "--illum-center",
        type=int,
        nargs=2,
        default=None,
        metavar=("X", "Y"),
        help=(
            "Illuminated centre X Y (overrides ROI). Legacy full-frame "
            f"default was ({DEFAULT_ILLUM_CENTER_X}, {DEFAULT_ILLUM_CENTER_Y})."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"RNG seed for pixel picks (default: {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--n-sigma",
        type=float,
        default=DEFAULT_N_SIGMA,
        help=f"Sigma-clip for illuminated mean (default: {DEFAULT_N_SIGMA})",
    )
    parser.add_argument(
        "--show-pixels",
        action="store_true",
        help="Also plot individual illuminated-pixel tracks vs file index",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output PNG path (default: inside the session data directory, "
            "next to the ramp FITS)"
        ),
    )
    parser.add_argument(
        "--cds-cube",
        type=Path,
        default=None,
        help=(
            "Full-frame FITS cube path (planes = frame - reset when a "
            "reset file is present, else frame - first; default: "
            "msac_uptheramp_frame_minus_first.fits in the session dir)"
        ),
    )
    parser.add_argument(
        "--no-cds-cube",
        action="store_true",
        help="Skip writing the full-frame reduced FITS cube",
    )
    parser.add_argument(
        "--illum-cube",
        type=Path,
        default=None,
        help=(
            "Illuminated-box crop FITS cube path (same reduction as --cds-cube; "
            "default: msac_uptheramp_frame_minus_first_illum.fits)"
        ),
    )
    parser.add_argument(
        "--no-illum-cube",
        action="store_true",
        help="Skip writing the illuminated-region crop FITS cube",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Accepted for compatibility; plot is always written to PNG (Agg backend)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format=LOG_FORMAT,
    )

    ramp_dir = resolve_ramp_dir(args.ramp_dir)
    try:
        folder_fits = list_ramp_fits(ramp_dir)
    except FileNotFoundError:
        folder_fits = []

    if args.file:
        paths: list[Path] = []
        for item in args.file:
            path = item.expanduser()
            if not path.is_absolute():
                path = ramp_dir / path
            if not path.is_file():
                raise FileNotFoundError(path)
            paths.append(path.resolve())
        science_paths, reset_from_args = split_science_and_reset(paths)
        logging.info(
            "Using %d science file(s) from --file",
            len(science_paths),
        )
    else:
        science_paths, reset_from_args = split_science_and_reset(folder_fits)
        if args.latest is not None and not args.all:
            n = max(1, int(args.latest))
            science_paths = science_paths[-n:]
        logging.info(
            "Using %d science file(s) from %s",
            len(science_paths),
            ramp_dir,
        )

    _, reset_from_folder = split_science_and_reset(folder_fits)
    if args.no_reset:
        reset_paths: list[Path] = []
    elif args.reset_file is not None:
        reset_path = args.reset_file.expanduser()
        if not reset_path.is_absolute():
            reset_path = ramp_dir / reset_path
        if not reset_path.is_file():
            raise FileNotFoundError(reset_path)
        reset_paths = [reset_path.resolve()]
    else:
        seen: dict[Path, Path] = {}
        for path in reset_from_folder + reset_from_args:
            seen[path.resolve()] = path.resolve()
        reset_paths = list(seen.values())

    reset_loaded = None if args.no_reset else load_reset_reference(reset_paths)
    if reset_loaded is not None:
        reset_frame, reset_fits_path = reset_loaded
        logging.info(
            "Subtracting reset frame %s from each science sample",
            reset_fits_path.name,
        )
    else:
        reset_frame = None
        reset_fits_path = None
        if args.no_reset:
            logging.info(
                "Ignoring reset frames (--no-reset); subtracting first science sample"
            )
        else:
            logging.info(
                "No reset frame (_R######) in the session folder; "
                "subtracting the first science sample"
            )

    paths = science_paths
    if not paths:
        raise RuntimeError(
            "No science FITS files (reset frames _R###### are not plotted)"
        )

    if args.index_tag == "auto":
        preferred_tag = choose_index_tag(paths)
    else:
        preferred_tag = args.index_tag
        logging.info("Using forced file-index tag: %s", preferred_tag)

    if args.illum_size is None:
        illum_h = illum_w = None
    elif len(args.illum_size) == 1:
        illum_h = illum_w = int(args.illum_size[0])
    elif len(args.illum_size) == 2:
        illum_h, illum_w = int(args.illum_size[0]), int(args.illum_size[1])
    else:
        raise ValueError("--illum-size accepts SIZE or HEIGHT WIDTH")

    explicit_center = args.illum_center is not None
    req_center_x = int(args.illum_center[0]) if explicit_center else None
    req_center_y = int(args.illum_center[1]) if explicit_center else None
    use_manual_illum = explicit_center or illum_h is not None
    illum_roi_index = args.illum_roi
    use_bg_roi = (not args.no_bg_roi) and args.bg_roi is not None
    bg_roi_index = int(args.bg_roi) if use_bg_roi else 0
    use_photonic = not use_manual_illum and illum_roi_index is None

    records: list[tuple[int, str, str, np.ndarray, dict]] = []
    index_tag = "M"
    ref_header: dict | None = None

    # Single multi-sample FITS → treat planes as the ramp; otherwise one
    # sample per file (last plane).
    use_planes_from_one_cube = False
    if len(paths) == 1:
        only_cube, only_header = load_ramp_cube(paths[0])
        if only_cube.shape[0] > 1:
            use_planes_from_one_cube = True
            ref_header = only_header
            parsed = file_index_from_name(
                paths[0].name, preferred_tag=preferred_tag
            )
            base_tag = parsed[0] if parsed else "P"
            index_tag = base_tag
            for iplane, plane in enumerate(only_cube):
                records.append(
                    (
                        iplane + 1,
                        base_tag,
                        f"{paths[0].name}[plane{iplane}]",
                        np.asarray(plane, dtype=np.float64),
                        only_header,
                    )
                )
            logging.info(
                "%s: using %d planes as ramp samples",
                paths[0].name,
                only_cube.shape[0],
            )

    if not use_planes_from_one_cube:
        for path in paths:
            parsed = file_index_from_name(
                path.name, preferred_tag=preferred_tag
            )
            if parsed is None:
                logging.warning(
                    "Skipping %s: no _M###### / _N###### (or trailing _######) "
                    "index",
                    path.name,
                )
                continue
            tag, index = parsed
            index_tag = tag

            cube, header = load_ramp_cube(path)
            if ref_header is None:
                ref_header = header
            logging.info(
                "%s: shape=%s  NAXIS=%s  index=%s%d",
                path.name,
                cube.shape,
                header.get("NAXIS", "?"),
                tag,
                index,
            )
            records.append(
                (
                    index,
                    tag,
                    path.name,
                    np.asarray(last_plane(cube), dtype=np.float64),
                    header,
                )
            )

    if not records:
        raise RuntimeError(
            "No usable FITS with an _M / _N file index in the name"
        )

    records.sort(key=lambda row: (row[0], row[2].lower()))
    stack = np.stack([row[3] for row in records], axis=0)
    if reset_frame is not None:
        if reset_fits_path is None:
            raise RuntimeError("Reset frame loaded without a FITS path")
        if reset_frame.shape != stack.shape[1:]:
            raise RuntimeError(
                f"Reset frame {reset_fits_path.name} shape {reset_frame.shape} "
                f"does not match science {stack.shape[1:]}"
            )
        cds_cube = relative_to_reference(stack, reset_frame)
        cds_short = "frame−reset"
        cds_label = "last − reset"
        reduct_card = ("FRAME-RESET", "Each plane = sample - reset frame")
        skip_ref = False
        reduct_history = (
            f"MSAC UpTheRamp CDS-relative cube: each plane = sample - "
            f"reset ({reset_fits_path.name})"
        )
    else:
        cds_cube = relative_to_first(stack)
        cds_short = "frame−first"
        cds_label = "last − first"
        reduct_card = ("FRAME-FIRST", "Each plane = sample - first sample")
        skip_ref = True
        reduct_history = (
            "MSAC UpTheRamp CDS-relative cube: each plane = "
            "sample - first sample (ordered by file/plane index); "
            "zero reference plane omitted"
        )
    indices = np.array([row[0] for row in records], dtype=np.int64)
    names = [row[2] for row in records]
    index_tag = records[0][1]
    ny, nx = int(stack.shape[-2]), int(stack.shape[-1])

    illum_source = "manual"
    region_label: str | None = None
    detector_box: tuple[int, int, int, int] | None = None
    if use_manual_illum:
        if illum_h is None:
            illum_h = illum_w = DEFAULT_ILLUM_SIZE
        center_x, center_y = resolve_illum_center(
            (ny, nx),
            center_x=req_center_x,
            center_y=req_center_y,
        )
        row0, row1, col0, col1 = illuminated_box(
            (ny, nx),
            illum_h,
            illum_w,
            center_x=center_x,
            center_y=center_y,
        )
    elif use_photonic:
        try:
            (row0, row1, col0, col1), detector_box = photonic_chip_illum_box(
                (ny, nx)
            )
        except ValueError as exc:
            raise RuntimeError(
                f"{photonic_chip_label()} does not fit image {ny}×{nx}: {exc}"
            ) from exc
        illum_h, illum_w = row1 - row0, col1 - col0
        drow0, drow1, dcol0, dcol1 = detector_box
        center_x = (dcol0 + dcol1) // 2
        center_y = (drow0 + drow1) // 2
        illum_source = photonic_chip_label()
        region_label = photonic_chip_label()
    else:
        roi = load_h2rg_roi_xywh(int(illum_roi_index))
        if roi is None:
            raise RuntimeError(
                f"No [{H2RG_SECTION}] ROI {illum_roi_index} in config.ini "
                "(or config.local.ini); set ROI or pass --illum-center / "
                "--illum-size"
            )
        x, y, w, h = roi
        try:
            row0, row1, col0, col1 = illuminated_box_from_xywh(
                (ny, nx), x, y, w, h
            )
        except ValueError as exc:
            raise RuntimeError(
                f"H2RG ROI {illum_roi_index}={x},{y},{w},{h} does not fit "
                f"image {ny}×{nx}: {exc}"
            ) from exc
        illum_h, illum_w = h, w
        center_x = x + w // 2
        center_y = y + h // 2
        illum_source = f"ROI {illum_roi_index}"

    bg_row0 = bg_row1 = bg_col0 = bg_col1 = 0
    if use_bg_roi:
        bg_roi = load_h2rg_roi_xywh(bg_roi_index)
        if bg_roi is None:
            raise RuntimeError(
                f"No [{H2RG_SECTION}] ROI {bg_roi_index} in config.ini "
                "(or config.local.ini); omit --bg-roi or fix the ROI"
            )
        bx, by, bw, bh = bg_roi
        try:
            bg_row0, bg_row1, bg_col0, bg_col1 = illuminated_box_from_xywh(
                (ny, nx), bx, by, bw, bh
            )
        except ValueError as exc:
            raise RuntimeError(
                f"H2RG ROI {bg_roi_index}={bx},{by},{bw},{bh} does not fit "
                f"image {ny}×{nx}: {exc}"
            ) from exc
        cds_cube, bg_pedestals = subtract_roi_pedestal(
            cds_cube,
            row0=bg_row0,
            row1=bg_row1,
            col0=bg_col0,
            col1=bg_col1,
            n_sigma=args.n_sigma,
        )
        logging.info(
            "Background ROI %d = %d,%d,%d,%d -> rows[%d:%d) cols[%d:%d); "
            "pedestal mean over ramp=%.4g ADU",
            bg_roi_index,
            bx,
            by,
            bw,
            bh,
            bg_row0,
            bg_row1,
            bg_col0,
            bg_col1,
            float(np.nanmean(bg_pedestals)),
        )

    n_brightest = max(1, int(args.n_brightest))
    pixels, n_rej = select_brightest_after_outliers(
        cds_cube[-1],
        row0,
        row1,
        col0,
        col1,
        n_brightest=n_brightest,
        n_sigma=args.n_sigma,
    )
    n_used = int(pixels.shape[0])
    if n_used == 0:
        means = np.full(cds_cube.shape[0], np.nan, dtype=np.float64)
    else:
        means = np.array(
            [float(np.mean(pixel_values(plane, pixels))) for plane in cds_cube],
            dtype=np.float64,
        )
    logging.info(
        "Illuminated box %dx%d at X=%d Y=%d (%s) -> rows[%d:%d) cols[%d:%d); "
        "flux = mean of %d pixels selected on last CDS plane "
        "(rejected %d outliers); same pixels for all samples",
        illum_h,
        illum_w,
        center_x,
        center_y,
        illum_source,
        row0,
        row1,
        col0,
        col1,
        n_used,
        n_rej,
    )
    for row, col in pixels:
        logging.info("  bright pixel X=%d Y=%d", int(col), int(row))
    pixel_matrix: np.ndarray | None = None
    if args.show_pixels:
        pixel_matrix = np.stack(
            [pixel_values(plane, pixels) for plane in cds_cube],
            axis=0,
        )

    if args.output is not None:
        output = args.output.expanduser()
        if not output.is_absolute():
            output = (ramp_dir / output).resolve()
        else:
            output = output.resolve()
    else:
        output = ramp_dir / "msac_uptheramp_illum_vs_file.png"

    def _resolve_out(path: Path | None, default_name: str) -> Path:
        if path is not None:
            out = path.expanduser()
            if not out.is_absolute():
                return (ramp_dir / out).resolve()
            return out.resolve()
        return (ramp_dir / default_name).resolve()

    write_full = not args.no_cds_cube
    write_illum = not args.no_illum_cube
    if write_full or write_illum:
        if skip_ref:
            try:
                cds_for_disk = drop_reference_plane(cds_cube)
            except ValueError as exc:
                logging.warning("Skipping CDS cube write(s): %s", exc)
                write_full = False
                write_illum = False
                cds_for_disk = None
        else:
            cds_for_disk = cds_cube
        if cds_for_disk is not None and (write_full or write_illum):
            pedestal_note = (
                f"; pedestal = mean(ROI {bg_roi_index})" if use_bg_roi else ""
            )
            reset_cards: dict = {
                "REDUCT": reduct_card,
                "SKIPREF": (
                    skip_ref,
                    (
                        "Omitted plane 0 (frame0-frame0 == 0)"
                        if skip_ref
                        else "Kept all science planes (reset subtraction)"
                    ),
                ),
            }
            if reset_fits_path is not None:
                reset_cards["RESETFIL"] = (
                    reset_fits_path.name,
                    "Reset FITS used as subtraction reference",
                )
            if write_full:
                save_cube_fits(
                    _resolve_out(
                        args.cds_cube, "msac_uptheramp_frame_minus_first.fits"
                    ),
                    cds_for_disk,
                    reference_header=ref_header,
                    history=reduct_history + pedestal_note + ".",
                    extra_cards=reset_cards,
                )
            if write_illum:
                illum_crop = cds_for_disk[:, row0:row1, col0:col1]
                illum_history = (
                    "MSAC UpTheRamp CDS-relative illuminated crop: "
                    + (
                        f"each plane = sample - reset ({reset_fits_path.name})"
                        if reset_fits_path is not None
                        else (
                            "each plane = sample - first sample; "
                            "zero reference plane omitted"
                        )
                    )
                    + "; spatial crop is the illuminated analysis box"
                    + pedestal_note
                    + "."
                )
                save_cube_fits(
                    _resolve_out(
                        args.illum_cube,
                        "msac_uptheramp_frame_minus_first_illum.fits",
                    ),
                    illum_crop,
                    reference_header=ref_header,
                    history=illum_history,
                    extra_cards={
                        **reset_cards,
                        "ILLUMROI": (
                            0
                            if use_manual_illum or use_photonic
                            else int(illum_roi_index),
                            "H2RG ROI index used for crop (0=photonic/manual)",
                        ),
                        "BGROI": (
                            bg_roi_index if use_bg_roi else 0,
                            "H2RG ROI index used as pedestal (0=none)",
                        ),
                        "ILLUMX0": (
                            (detector_box[2] if detector_box else col0),
                            "Crop col start (inclusive, detector)",
                        ),
                        "ILLUMX1": (
                            (detector_box[3] if detector_box else col1),
                            "Crop col end (exclusive, detector)",
                        ),
                        "ILLUMY0": (
                            (detector_box[0] if detector_box else row0),
                            "Crop row start (inclusive, detector)",
                        ),
                        "ILLUMY1": (
                            (detector_box[1] if detector_box else row1),
                            "Crop row end (exclusive, detector)",
                        ),
                        "ILLUMCX": (center_x, "Illuminated box centre X"),
                        "ILLUMCY": (center_y, "Illuminated box centre Y"),
                    },
                )

    flux_label = f"{n_used} brightest"
    title = (
        f"MSAC UpTheRamp — {n_brightest} brightest ({cds_short}) vs index "
        f"({illum_h}×{illum_w} @ X={center_x}, Y={center_y}; {illum_source})"
    )
    last_cds = np.asarray(cds_cube[-1], dtype=np.float64)
    plot_file_series(
        indices=indices,
        means=means,
        names=names,
        index_tag=index_tag,
        pixel_matrix=pixel_matrix,
        output=output,
        title=title,
        show=args.show,
        full_frame=last_cds,
        illum_frame=last_cds[row0:row1, col0:col1],
        illum_box=(row0, row1, col0, col1),
        bg_box=(bg_row0, bg_row1, bg_col0, bg_col1) if use_bg_roi else None,
        region_label=region_label,
        detector_box=detector_box,
        cds_label=cds_label,
        cds_short=cds_short,
        flux_label=flux_label,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI surface
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
        logging.error("%s", exc)
        raise SystemExit(1) from exc
