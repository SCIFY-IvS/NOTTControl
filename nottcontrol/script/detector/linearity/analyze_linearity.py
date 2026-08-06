#!/usr/bin/env python3
"""H2RG detector linearity: dark-subtracted flux vs DIT.

Default acquisition blocks follow the lab log (Full frame):

    closed 301-305 / open 306-310   DIT ~1475 ms
    closed 311-315 / open 316-320   DIT ~2951 ms
    closed 321-325 / open 326-330   DIT ~4425 ms
    closed 331-335 / open 336-340   DIT ~5901 ms
    closed 341-345 / open 346-350   DIT ~1475 ms (beamsplitter in)

For each block the script computes ``mean(open) - mean(closed)``, writes that
2-D float32 image to FITS, writes a cube of ``open[i] - mean(closed)`` for
each open frame, writes a global ``mean(all open) - mean(all closed)``
image over the shutter-open blocks, and plots fixed random pixels vs DIT.

Frames before 301 are ignored. Illuminated pixels are drawn from a 20×20 box
centred at image coordinates (X=1045, Y=943).
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from nottcontrol.camera.macie.fits_science import (
    load_fits_data,
    science_image_from_cube,
)

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

# Prefer the on-server FITS tree; fall back to the local T7 backup mirror.
SERVER_DATA_ROOT = Path("/data/nott")
LOCAL_DATA_ROOT = Path("/Volumes/T7 Data/Data/nott")
DEFAULT_START = 301
DEFAULT_END = 340
DEFAULT_BS_START = 341
DEFAULT_BS_END = 350
DEFAULT_GROUP_SIZE = 10
DEFAULT_N_CLOSED = 5
DEFAULT_N_OPEN = 5
DEFAULT_N_PIXELS = 100
DEFAULT_N_ILLUM_PIXELS = 100
DEFAULT_ILLUM_SIZE = 20
# Illuminated spot centre in image coordinates (X=column, Y=row).
DEFAULT_ILLUM_CENTER_X = 1045
DEFAULT_ILLUM_CENTER_Y = 943
DEFAULT_SEED = 0

# Acquisition log (Full-frame linearity, 2026-08-06):
#   closed N / open N per DIT; beamsplitter-in on the last block.
DEFAULT_BLOCK_SPECS: tuple[tuple[int, int, int, int, str], ...] = (
    (301, 305, 306, 310, "open"),
    (311, 315, 316, 320, "open"),
    (321, 325, 326, 330, "open"),
    (331, 335, 336, 340, "open"),
    (341, 345, 346, 350, "beamsplitter"),
)

FRAME_RE = re.compile(
    r"^nott_(?P<day>\d{8})_(?P<frame>\d+)(?P<science>_science)?\.fits$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FrameFile:
    path: Path
    frame: int
    is_science: bool


@dataclass(frozen=True)
class BlockSpec:
    closed_start: int
    closed_end: int
    open_start: int
    open_end: int
    label: str = "open"

    @property
    def frame_start(self) -> int:
        return min(self.closed_start, self.open_start)

    @property
    def frame_end(self) -> int:
        return max(self.closed_end, self.open_end)

    @property
    def n_closed(self) -> int:
        return self.closed_end - self.closed_start + 1

    @property
    def n_open(self) -> int:
        return self.open_end - self.open_start + 1


@dataclass(frozen=True)
class DitBlock:
    dit_s: float
    frame_start: int
    frame_end: int
    closed_start: int
    closed_end: int
    open_start: int
    open_end: int
    difference: np.ndarray
    closed_mean: np.ndarray
    open_mean: np.ndarray
    open_darksub: np.ndarray
    n_closed: int
    n_open: int
    label: str = "open"


def utc_day_string(day: str | None) -> str:
    if day is not None:
        datetime.strptime(day, "%Y%m%d")
        return day
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def default_data_root() -> Path:
    """Resolve the FITS root: server ``/data/nott``, else local T7 mirror."""
    env = os.environ.get("NOTT_DATA_ROOT", "").strip()
    if env:
        return Path(env)

    try:
        from nottcontrol import config

        configured = config.get(
            "H2RG DETECTOR", "linux_fits_directory", fallback=""
        ).strip()
        if configured:
            configured_path = Path(configured)
            if configured_path.is_dir():
                return configured_path
    except Exception:
        pass

    if SERVER_DATA_ROOT.is_dir():
        return SERVER_DATA_ROOT
    if LOCAL_DATA_ROOT.is_dir():
        return LOCAL_DATA_ROOT
    # Prefer the server path in error messages when neither exists yet.
    return SERVER_DATA_ROOT


def resolve_data_dir(
    *,
    data_dir: Path | None,
    data_root: Path | None,
    day: str | None,
) -> Path:
    if data_dir is not None:
        return data_dir
    root = data_root or default_data_root()
    return root / utc_day_string(day)


def parse_frame_file(path: Path) -> FrameFile | None:
    match = FRAME_RE.match(path.name)
    if match is None:
        return None
    return FrameFile(
        path=path,
        frame=int(match.group("frame")),
        is_science=match.group("science") is not None,
    )


def discover_frames(
    data_dir: Path,
    *,
    start: int,
    end: int,
    prefer_science: bool = True,
) -> list[FrameFile]:
    catalog = build_frame_catalog(data_dir, prefer_science=prefer_science)
    return frames_for_range(catalog, start, end)


def build_frame_catalog(
    data_dir: Path,
    *,
    prefer_science: bool = True,
) -> dict[int, FrameFile]:
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory does not exist: {data_dir}")

    by_frame: dict[int, list[FrameFile]] = {}
    for path in sorted(data_dir.iterdir()):
        if not path.is_file():
            continue
        parsed = parse_frame_file(path)
        if parsed is None:
            continue
        by_frame.setdefault(parsed.frame, []).append(parsed)

    catalog: dict[int, FrameFile] = {}
    for frame, candidates in by_frame.items():
        if prefer_science:
            science = [c for c in candidates if c.is_science]
            catalog[frame] = science[0] if science else candidates[0]
        else:
            raw = [c for c in candidates if not c.is_science]
            catalog[frame] = raw[0] if raw else candidates[0]
    return catalog


def frames_for_range(
    catalog: dict[int, FrameFile],
    start: int,
    end: int,
) -> list[FrameFile]:
    missing = [n for n in range(start, end + 1) if n not in catalog]
    if missing:
        preview = ", ".join(str(n) for n in missing[:12])
        more = "" if len(missing) <= 12 else f" … (+{len(missing) - 12} more)"
        raise FileNotFoundError(f"Missing frames: {preview}{more}")
    return [catalog[n] for n in range(start, end + 1)]


def default_block_specs() -> list[BlockSpec]:
    return [
        BlockSpec(c0, c1, o0, o1, label)
        for c0, c1, o0, o1, label in DEFAULT_BLOCK_SPECS
    ]


def read_dit_seconds(header: dict) -> float:
    for key in ("EXPTIME", "DIT", "INTTIME", "TINT"):
        if key in header and header[key] is not None:
            value = float(header[key])
            # GUI / science FITS store EXPTIME in seconds. If a keyword looks
            # like milliseconds (> 100 and name suggests time), keep as-is only
            # when the key is EXPTIME-like in seconds — EXPTIME is always seconds.
            if key in ("INTTIME", "TINT") and value > 50:
                return value / 1000.0
            return value
    raise KeyError("No DIT/EXPTIME keyword found in FITS header")


def load_image(path: Path, *, reduction: str) -> tuple[np.ndarray, float]:
    data, header = load_fits_data(path)
    image = science_image_from_cube(data, header, reduction=reduction)  # type: ignore[arg-type]
    image = np.asarray(image, dtype=np.float64)
    if image.ndim != 2:
        raise ValueError(f"Expected 2-D image from {path}, got shape {image.shape}")
    dit_s = read_dit_seconds(header)
    return image, dit_s


def average_stack(images: list[np.ndarray]) -> np.ndarray:
    return np.mean(np.stack(images, axis=0), axis=0)


def build_dit_block_from_spec(
    catalog: dict[int, FrameFile],
    spec: BlockSpec,
    *,
    reduction: str,
) -> DitBlock:
    closed_files = frames_for_range(catalog, spec.closed_start, spec.closed_end)
    open_files = frames_for_range(catalog, spec.open_start, spec.open_end)
    signal_name = "BS-in" if spec.label == "beamsplitter" else "Open"

    closed_images: list[np.ndarray] = []
    open_images: list[np.ndarray] = []
    closed_dits: list[float] = []

    for item in closed_files:
        image, dit_s = load_image(item.path, reduction=reduction)
        closed_images.append(image)
        closed_dits.append(dit_s)
        logging.info(
            "Closed frame %06d  DIT=%.6g s  %s",
            item.frame,
            dit_s,
            item.path.name,
        )

    for item in open_files:
        image, dit_s = load_image(item.path, reduction=reduction)
        open_images.append(image)
        logging.info(
            "%-6s frame %06d  DIT=%.6g s  %s",
            signal_name,
            item.frame,
            dit_s,
            item.path.name,
        )

    # DIT from shutter-closed frames only (open headers can be stale at block edges).
    dit_ref = float(np.median(closed_dits))
    dit_spread = float(np.max(closed_dits) - np.min(closed_dits))
    if dit_spread > max(1e-6, 0.01 * abs(dit_ref)):
        logging.warning(
            "Closed-frame DIT varies in %d–%d: min=%.6g s max=%.6g s",
            spec.closed_start,
            spec.closed_end,
            min(closed_dits),
            max(closed_dits),
        )

    closed_mean = average_stack(closed_images)
    open_mean = average_stack(open_images)
    difference = open_mean - closed_mean
    open_darksub = np.stack(
        [np.asarray(img, dtype=np.float64) - closed_mean for img in open_images],
        axis=0,
    )
    block = DitBlock(
        dit_s=dit_ref,
        frame_start=spec.frame_start,
        frame_end=spec.frame_end,
        closed_start=spec.closed_start,
        closed_end=spec.closed_end,
        open_start=spec.open_start,
        open_end=spec.open_end,
        difference=difference,
        closed_mean=closed_mean,
        open_mean=open_mean,
        open_darksub=open_darksub,
        n_closed=spec.n_closed,
        n_open=spec.n_open,
        label=spec.label,
    )
    logging.info(
        "Block closed %d–%d / %s %d–%d [%s]: DIT=%.6g s  "
        "mean(open)-mean(closed)=%.4g ADU",
        spec.closed_start,
        spec.closed_end,
        signal_name,
        spec.open_start,
        spec.open_end,
        spec.label,
        dit_ref,
        float(np.mean(difference)),
    )
    return block


def build_blocks_from_specs(
    catalog: dict[int, FrameFile],
    specs: list[BlockSpec],
    *,
    reduction: str,
) -> list[DitBlock]:
    return [
        build_dit_block_from_spec(catalog, spec, reduction=reduction)
        for spec in specs
    ]


def build_dit_block(
    group: list[FrameFile],
    *,
    n_closed: int,
    n_open: int,
    reduction: str,
    label: str,
    signal_name: str,
) -> DitBlock:
    """Legacy sequential group helper (closed then open in one contiguous range)."""
    if len(group) != n_closed + n_open:
        raise ValueError(
            f"Expected {n_closed + n_open} frames for label={label!r}, got {len(group)}"
        )
    closed_files = group[:n_closed]
    open_files = group[n_closed:]
    spec = BlockSpec(
        closed_start=closed_files[0].frame,
        closed_end=closed_files[-1].frame,
        open_start=open_files[0].frame,
        open_end=open_files[-1].frame,
        label=label,
    )
    catalog = {item.frame: item for item in group}
    return build_dit_block_from_spec(catalog, spec, reduction=reduction)


def build_dit_blocks(
    frames: list[FrameFile],
    *,
    group_size: int,
    n_closed: int,
    n_open: int,
    reduction: str,
    label: str = "open",
    signal_name: str = "Open",
) -> list[DitBlock]:
    if group_size != n_closed + n_open:
        raise ValueError(
            f"group_size ({group_size}) must equal n_closed+n_open "
            f"({n_closed}+{n_open})"
        )
    if len(frames) % group_size != 0:
        raise ValueError(
            f"Frame count {len(frames)} is not divisible by group size {group_size}"
        )

    blocks: list[DitBlock] = []
    for offset in range(0, len(frames), group_size):
        group = frames[offset : offset + group_size]
        blocks.append(
            build_dit_block(
                group,
                n_closed=n_closed,
                n_open=n_open,
                reduction=reduction,
                label=label,
                signal_name=signal_name,
            )
        )
    return blocks


def illuminated_box(
    shape: tuple[int, int],
    box_height: int,
    box_width: int,
    *,
    center_x: int,
    center_y: int,
) -> tuple[int, int, int, int]:
    """Return ``(row0, row1, col0, col1)`` for a box around ``(center_x, center_y)``.

    Image coordinates: X = column, Y = row. ``row1`` / ``col1`` are exclusive.
    """
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


def save_block_cubes(
    blocks: list[DitBlock],
    output_dir: Path,
    *,
    day_label: str,
) -> list[Path]:
    """Write dark-subtracted mean image + per-open-frame cube FITS per DIT block."""
    from astropy.io import fits

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for block in blocks:
        dit_ms = block.dit_s * 1000.0
        label_slug = re.sub(r"[^A-Za-z0-9]+", "_", block.label).strip("_") or "block"
        stem = (
            f"linearity_{day_label}_{label_slug}_"
            f"dit{dit_ms:.0f}ms_"
            f"c{block.closed_start:06d}-{block.closed_end:06d}_"
            f"o{block.open_start:06d}-{block.open_end:06d}"
        )

        header = fits.Header()
        header["IMTYPE"] = ("DARKSUB", "mean(open/BS) - mean(closed)")
        header["EXPTIME"] = (block.dit_s, "DIT / photon collection time (s)")
        header["DITMS"] = (dit_ms, "DIT (ms)")
        header["FRMSTART"] = (block.frame_start, "First frame number in block")
        header["FRMEND"] = (block.frame_end, "Last frame number in block")
        header["CLSTART"] = (block.closed_start, "First shutter-closed frame")
        header["CLEND"] = (block.closed_end, "Last shutter-closed frame")
        header["OPSTART"] = (block.open_start, "First open/BS frame")
        header["OPEND"] = (block.open_end, "Last open/BS frame")
        header["LABEL"] = (block.label, "Block type: open or beamsplitter")
        header["NCLOSED"] = (block.n_closed, "Number of shutter-closed frames averaged")
        header["NOPEN"] = (block.n_open, "Number of open/BS frames averaged")
        header["COMMENT"] = "Image = mean(open/BS) - mean(closed)."

        mean_path = output_dir / f"{stem}.fits"
        fits.PrimaryHDU(
            data=np.asarray(block.difference, dtype=np.float32),
            header=header,
        ).writeto(mean_path, overwrite=True)
        written.append(mean_path)
        logging.info(
            "Wrote dark-sub mean FITS: %s  %s",
            mean_path.name,
            block.difference.shape,
        )

        cube = np.asarray(block.open_darksub, dtype=np.float32)
        if cube.ndim != 3:
            raise ValueError(
                f"Expected open_darksub cube (n,y,x), got shape {cube.shape}"
            )
        cube_header = header.copy()
        cube_header["IMTYPE"] = (
            "OPEN-DARK",
            "Each plane = open/BS frame - mean(closed)",
        )
        cube_header["NAXIS"] = 3
        cube_header["NAXIS1"] = cube.shape[2]
        cube_header["NAXIS2"] = cube.shape[1]
        cube_header["NAXIS3"] = cube.shape[0]
        cube_header["COMMENT"] = (
            "Cube plane k = open/BS frame k - mean(closed) for this DIT block."
        )
        cube_path = output_dir / f"{stem}_opencube.fits"
        fits.PrimaryHDU(data=cube, header=cube_header).writeto(
            cube_path, overwrite=True
        )
        written.append(cube_path)
        logging.info(
            "Wrote open dark-sub cube: %s  %s",
            cube_path.name,
            cube.shape,
        )
    return written


def save_combined_open_minus_closed(
    blocks: list[DitBlock],
    output_dir: Path,
    *,
    day_label: str,
) -> Path | None:
    """Write ``mean(all open) - mean(all closed)`` over *blocks* (equal frame weight)."""
    from astropy.io import fits

    if not blocks:
        return None

    # Rebuild global means with one vote per frame (n_closed / n_open may differ).
    closed_acc: np.ndarray | None = None
    open_acc: np.ndarray | None = None
    n_closed = 0
    n_open = 0
    frame_lo = min(b.frame_start for b in blocks)
    frame_hi = max(b.frame_end for b in blocks)
    dit_ms_list = [b.dit_s * 1000.0 for b in blocks]

    for block in blocks:
        if closed_acc is None:
            closed_acc = np.zeros_like(block.closed_mean, dtype=np.float64)
            open_acc = np.zeros_like(block.open_mean, dtype=np.float64)
        closed_acc += block.closed_mean * block.n_closed
        open_acc += block.open_mean * block.n_open
        n_closed += block.n_closed
        n_open += block.n_open

    assert closed_acc is not None and open_acc is not None
    if n_closed < 1 or n_open < 1:
        raise ValueError("Need at least one closed and one open frame for combined diff")

    combined = open_acc / n_open - closed_acc / n_closed
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"linearity_{day_label}_open_minus_closed_avg.fits"

    header = fits.Header()
    header["IMTYPE"] = ("OPEN-CL-AVG", "mean(all open) - mean(all closed)")
    header["NBLOCKS"] = (len(blocks), "Number of DIT blocks included")
    header["NCLOSED"] = (n_closed, "Total shutter-closed frames averaged")
    header["NOPEN"] = (n_open, "Total open frames averaged")
    header["FRMSTART"] = (frame_lo, "First frame number among blocks")
    header["FRMEND"] = (frame_hi, "Last frame number among blocks")
    header["DITMSMIN"] = (float(min(dit_ms_list)), "Min block DIT (ms)")
    header["DITMSMAX"] = (float(max(dit_ms_list)), "Max block DIT (ms)")
    header["COMMENT"] = (
        "Global mean(open)-mean(closed) over shutter-open linearity blocks "
        "(beamsplitter-in excluded). Equal weight per frame."
    )

    fits.PrimaryHDU(
        data=np.asarray(combined, dtype=np.float32),
        header=header,
    ).writeto(path, overwrite=True)
    logging.info(
        "Wrote combined open−closed average: %s  shape=%s  "
        "n_closed=%d n_open=%d  mean=%.4g ADU",
        path.name,
        combined.shape,
        n_closed,
        n_open,
        float(np.mean(combined)),
    )
    return path


def choose_pixels(
    shape: tuple[int, int],
    n_pixels: int,
    seed: int,
    *,
    row_slice: tuple[int, int] | None = None,
    col_slice: tuple[int, int] | None = None,
    exclude_row_slice: tuple[int, int] | None = None,
    exclude_col_slice: tuple[int, int] | None = None,
) -> np.ndarray:
    """Pick ``n_pixels`` random coordinates, optionally restricted to / excluding a box."""
    height, width = shape
    row0, row1 = row_slice if row_slice is not None else (0, height)
    col0, col1 = col_slice if col_slice is not None else (0, width)
    if not (0 <= row0 < row1 <= height and 0 <= col0 < col1 <= width):
        raise ValueError(
            f"Invalid pixel box rows=[{row0},{row1}) cols=[{col0},{col1}) "
            f"for shape {shape}"
        )

    mask = np.zeros((height, width), dtype=bool)
    mask[row0:row1, col0:col1] = True
    if exclude_row_slice is not None and exclude_col_slice is not None:
        er0, er1 = exclude_row_slice
        ec0, ec1 = exclude_col_slice
        mask[er0:er1, ec0:ec1] = False

    coords = np.column_stack(np.nonzero(mask))
    if n_pixels > len(coords):
        raise ValueError(
            f"n_pixels ({n_pixels}) exceeds available region size ({len(coords)})"
        )
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(coords), size=n_pixels, replace=False)
    return coords[pick]


def sigma_clip_mean(
    values: np.ndarray,
    *,
    n_sigma: float = 3.0,
    max_iter: int = 5,
) -> tuple[float, int, int]:
    """Return ``(mean, n_kept, n_rejected)`` after iterative sigma clipping."""
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


def pixel_fluxes(block: DitBlock, pixels: np.ndarray) -> np.ndarray:
    return np.array(
        [float(block.difference[int(row), int(col)]) for row, col in pixels],
        dtype=np.float64,
    )


def plot_mean_series(
    ax,
    *,
    pixels: np.ndarray,
    open_blocks: list[DitBlock],
    open_dits_ms: np.ndarray,
    beamsplitter_blocks: list[DitBlock] | None,
    n_sigma: float,
    color: str,
    label: str,
    bs_label: str | None = None,
    marker: str = "o",
    bs_marker: str = "s",
    log_prefix: str = "Mean",
) -> None:
    means: list[float] = []
    for block in open_blocks:
        mean_val, n_kept, n_rej = sigma_clip_mean(
            pixel_fluxes(block, pixels), n_sigma=n_sigma
        )
        means.append(mean_val)
        logging.info(
            "%s at DIT=%.3g ms: %.4g ADU "
            "(kept %d / %d pixels, rejected %d, clip=%.1fσ)",
            log_prefix,
            block.dit_s * 1000.0,
            mean_val,
            n_kept,
            n_kept + n_rej,
            n_rej,
            n_sigma,
        )

    ax.plot(
        open_dits_ms,
        means,
        marker=marker,
        linewidth=2.0,
        markersize=8,
        color=color,
        label=label,
        zorder=6,
    )

    if beamsplitter_blocks:
        bs_legend = bs_label
        for block in beamsplitter_blocks:
            mean_val, n_kept, n_rej = sigma_clip_mean(
                pixel_fluxes(block, pixels), n_sigma=n_sigma
            )
            logging.info(
                "%s (BS) at DIT=%.3g ms: %.4g ADU "
                "(kept %d / %d pixels, rejected %d, clip=%.1fσ)",
                log_prefix,
                block.dit_s * 1000.0,
                mean_val,
                n_kept,
                n_kept + n_rej,
                n_rej,
                n_sigma,
            )
            ax.scatter(
                [block.dit_s * 1000.0],
                [mean_val],
                marker=bs_marker,
                s=64,
                color=color,
                edgecolors="k",
                linewidths=0.5,
                zorder=7,
                label=bs_legend,
            )
            bs_legend = None


def plot_pixel_linearity(
    open_blocks: list[DitBlock],
    full_pixels: np.ndarray,
    *,
    illum_pixels: np.ndarray | None = None,
    beamsplitter_blocks: list[DitBlock] | None = None,
    clip_sigma: float = 3.0,
    output: Path | None,
    show: bool,
    title: str,
) -> Path | None:
    if not open_blocks and not beamsplitter_blocks:
        raise ValueError("No DIT blocks to plot")

    all_blocks = list(open_blocks) + list(beamsplitter_blocks or [])
    shape = all_blocks[0].difference.shape
    for block in all_blocks[1:]:
        if block.difference.shape != shape:
            raise ValueError(
                "All dark-subtracted images must share the same shape so the "
                f"same pixels can be used; got {shape} and {block.difference.shape}"
            )

    ordered_open: list[DitBlock] = []
    open_dits_ms = np.array([], dtype=np.float64)
    if open_blocks:
        open_dits_ms = (
            np.array([block.dit_s for block in open_blocks], dtype=np.float64) * 1000.0
        )
        order = np.argsort(open_dits_ms)
        open_dits_ms = open_dits_ms[order]
        ordered_open = [open_blocks[i] for i in order]

    fig, ax = plt.subplots(figsize=(9, 6))

    plot_mean_series(
        ax,
        pixels=full_pixels,
        open_blocks=ordered_open,
        open_dits_ms=open_dits_ms,
        beamsplitter_blocks=beamsplitter_blocks,
        n_sigma=clip_sigma,
        color="C0",
        label="non illuminated pixels",
        bs_label="beamsplitter in (non illuminated)",
        marker="o",
        bs_marker="s",
        log_prefix="Non-illuminated mean",
    )

    if illum_pixels is not None and len(illum_pixels) > 0:
        plot_mean_series(
            ax,
            pixels=illum_pixels,
            open_blocks=ordered_open,
            open_dits_ms=open_dits_ms,
            beamsplitter_blocks=beamsplitter_blocks,
            n_sigma=clip_sigma,
            color="C3",
            label="Illuminated pixels",
            bs_label="beamsplitter in (illuminated)",
            marker="^",
            bs_marker="D",
            log_prefix="Illuminated mean",
        )

    ax.set_xlabel("DIT (ms)")
    ax.set_ylabel("Dark-subtracted signal (ADU)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()

    saved: Path | None = None
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=150)
        saved = output
        logging.info("Wrote plot: %s", output)

    if show:
        plt.show()
    else:
        plt.close(fig)
    return saved

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detector linearity: mean(open)-mean(closed) vs DIT for random pixels."
        ),
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory containing the FITS frames (overrides --data-root/--day)",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help=(
            "Parent of YYYYMMDD folders (default: NOTT_DATA_ROOT, else "
            f"{SERVER_DATA_ROOT} if present, else {LOCAL_DATA_ROOT})"
        ),
    )
    parser.add_argument(
        "--day",
        metavar="YYYYMMDD",
        default=None,
        help="UTC day folder under --data-root (default: today UTC)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=DEFAULT_START,
        help=f"First frame number (default: {DEFAULT_START})",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=DEFAULT_END,
        help=f"Last shutter-open frame number inclusive (default: {DEFAULT_END})",
    )
    parser.add_argument(
        "--bs-start",
        type=int,
        default=DEFAULT_BS_START,
        help=(
            f"First beamsplitter-in block frame (default: {DEFAULT_BS_START}; "
            "5 closed + 5 beamsplitter-in)"
        ),
    )
    parser.add_argument(
        "--bs-end",
        type=int,
        default=DEFAULT_BS_END,
        help=f"Last beamsplitter-in block frame inclusive (default: {DEFAULT_BS_END})",
    )
    parser.add_argument(
        "--no-beamsplitter",
        action="store_true",
        help="Skip the beamsplitter-in block",
    )
    parser.add_argument(
        "--group-size",
        type=int,
        default=DEFAULT_GROUP_SIZE,
        help=f"Frames per DIT block (default: {DEFAULT_GROUP_SIZE})",
    )
    parser.add_argument(
        "--n-closed",
        type=int,
        default=DEFAULT_N_CLOSED,
        help=f"Shutter-closed frames at start of each block (default: {DEFAULT_N_CLOSED})",
    )
    parser.add_argument(
        "--n-open",
        type=int,
        default=DEFAULT_N_OPEN,
        help=f"Shutter-open frames at end of each block (default: {DEFAULT_N_OPEN})",
    )
    parser.add_argument(
        "--n-pixels",
        type=int,
        default=DEFAULT_N_PIXELS,
        help=(
            f"Number of random full-array pixels to plot "
            f"(default: {DEFAULT_N_PIXELS})"
        ),
    )
    parser.add_argument(
        "--n-illum-pixels",
        type=int,
        default=DEFAULT_N_ILLUM_PIXELS,
        help=(
            f"Number of random pixels inside the illuminated center box "
            f"(default: {DEFAULT_N_ILLUM_PIXELS})"
        ),
    )
    parser.add_argument(
        "--illum-size",
        type=int,
        nargs="+",
        metavar="PIX",
        default=None,
        help=(
            "Illuminated box size in pixels: SIZE or HEIGHT WIDTH "
            f"(default: {DEFAULT_ILLUM_SIZE}x{DEFAULT_ILLUM_SIZE})"
        ),
    )
    parser.add_argument(
        "--illum-center",
        type=int,
        nargs=2,
        metavar=("X", "Y"),
        default=None,
        help=(
            "Illuminated box centre in image coordinates X Y "
            f"(default: {DEFAULT_ILLUM_CENTER_X} {DEFAULT_ILLUM_CENTER_Y})"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"RNG seed for pixel selection (default: {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--clip-sigma",
        type=float,
        default=3.0,
        help="Sigma-clip threshold for illuminated-pixel averaging (default: 3)",
    )
    parser.add_argument(
        "--reduction",
        choices=("CDS", "Ramp", "Fowler", "SingleFrame"),
        default="Ramp",
        help=(
            "Ramp reduction when loading raw cubes "
            "(ignored for already-reduced *_science.fits; default: Ramp)"
        ),
    )
    parser.add_argument(
        "--prefer-raw",
        action="store_true",
        help="Prefer raw ramp FITS over *_science.fits when both exist",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output PNG path (default: <script_dir>/linearity_<day>.png)",
    )
    parser.add_argument(
        "--fits-dir",
        type=Path,
        default=None,
        help=(
            "Directory for dark-subtracted mean FITS and open-frame cubes "
            "(default: <script_dir>/linearity_<day>_darksub)"
        ),
    )
    parser.add_argument(
        "--no-fits",
        action="store_true",
        help="Do not write dark-subtracted FITS images / open cubes",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the plot interactively",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Optional log file path",
    )
    return parser.parse_args(argv)


def configure_logging(log_file: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=handlers)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_file)

    try:
        data_dir = resolve_data_dir(
            data_dir=args.data_dir,
            data_root=args.data_root,
            day=args.day,
        )
    except ValueError as exc:
        logging.error("%s", exc)
        return 1

    logging.info("Data directory: %s", data_dir)

    specs = default_block_specs()
    if args.no_beamsplitter:
        specs = [spec for spec in specs if spec.label != "beamsplitter"]
    for spec in specs:
        logging.info(
            "Plan [%s]: closed %d–%d, open/BS %d–%d",
            spec.label,
            spec.closed_start,
            spec.closed_end,
            spec.open_start,
            spec.open_end,
        )

    try:
        catalog = build_frame_catalog(
            data_dir,
            prefer_science=not args.prefer_raw,
        )
        all_blocks = build_blocks_from_specs(
            catalog,
            specs,
            reduction=args.reduction,
        )
    except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
        logging.error("%s", exc)
        return 1

    open_blocks = [block for block in all_blocks if block.label != "beamsplitter"]
    bs_blocks = [block for block in all_blocks if block.label == "beamsplitter"]

    shape_ref = all_blocks[0]
    shape = shape_ref.difference.shape
    for block in all_blocks[1:]:
        if block.difference.shape != shape:
            logging.error(
                "Image shape mismatch: frames %d–%d have %s, expected %s. "
                "The same random pixels must be used for every image.",
                block.frame_start,
                block.frame_end,
                block.difference.shape,
                shape,
            )
            return 1

    try:
        if args.illum_size is None:
            illum_h = illum_w = DEFAULT_ILLUM_SIZE
        elif len(args.illum_size) == 1:
            illum_h = illum_w = int(args.illum_size[0])
        elif len(args.illum_size) == 2:
            illum_h, illum_w = (int(args.illum_size[0]), int(args.illum_size[1]))
        else:
            raise ValueError("--illum-size accepts SIZE or HEIGHT WIDTH")
        if args.illum_center is None:
            center_x, center_y = DEFAULT_ILLUM_CENTER_X, DEFAULT_ILLUM_CENTER_Y
        else:
            center_x, center_y = (int(args.illum_center[0]), int(args.illum_center[1]))
        row0, row1, col0, col1 = illuminated_box(
            shape,
            illum_h,
            illum_w,
            center_x=center_x,
            center_y=center_y,
        )
    except ValueError as exc:
        logging.error("%s", exc)
        return 1

    # Cap illuminated sample count to the box area.
    illum_area = (row1 - row0) * (col1 - col0)
    n_illum = min(args.n_illum_pixels, illum_area)

    non_illum_pixels = choose_pixels(
        shape,
        args.n_pixels,
        args.seed,
        exclude_row_slice=(row0, row1),
        exclude_col_slice=(col0, col1),
    )
    illum_pixels = choose_pixels(
        shape,
        n_illum,
        args.seed + 1,
        row_slice=(row0, row1),
        col_slice=(col0, col1),
    )
    logging.info(
        "Non-illuminated pixels: %d (seed=%d); first few: %s",
        args.n_pixels,
        args.seed,
        ", ".join(f"({r},{c})" for r, c in non_illum_pixels[:5]),
    )
    logging.info(
        "Illuminated %dx%d at X=%d Y=%d → rows[%d:%d) cols[%d:%d): %d pixels "
        "(seed=%d); first few: %s",
        illum_h,
        illum_w,
        center_x,
        center_y,
        row0,
        row1,
        col0,
        col1,
        n_illum,
        args.seed + 1,
        ", ".join(f"({r},{c})" for r, c in illum_pixels[:5]),
    )

    day_label = args.day or data_dir.name
    output = args.output
    if output is None and not args.show:
        output = Path(__file__).resolve().parent / f"linearity_{day_label}.png"

    if not args.no_fits:
        fits_dir = args.fits_dir or (
            Path(__file__).resolve().parent / f"linearity_{day_label}_darksub"
        )
        # Replace previous outputs for this day so old wrong products disappear.
        if fits_dir.exists():
            for old in fits_dir.glob(f"linearity_{day_label}_*.fits"):
                old.unlink()
        old_cubes = Path(__file__).resolve().parent / f"linearity_{day_label}_cubes"
        if old_cubes.exists() and args.fits_dir is None:
            for old in old_cubes.glob(f"linearity_{day_label}_*.fits"):
                old.unlink()
            try:
                old_cubes.rmdir()
            except OSError:
                pass
        try:
            save_block_cubes(
                all_blocks,
                fits_dir,
                day_label=day_label,
            )
            save_combined_open_minus_closed(
                open_blocks,
                fits_dir,
                day_label=day_label,
            )
        except OSError as exc:
            logging.error("Failed to write dark-sub FITS: %s", exc)
            return 1

    title = (
        f"H2RG linearity — log blocks "
        f"({len(open_blocks)} open DITs"
        f"{', BS' if bs_blocks else ''}; "
        f"{args.n_pixels} non-illum + mean of {n_illum} illum pixels)"
    )
    plot_pixel_linearity(
        open_blocks,
        non_illum_pixels,
        illum_pixels=illum_pixels,
        beamsplitter_blocks=bs_blocks,
        clip_sigma=args.clip_sigma,
        output=output,
        show=args.show,
        title=title,
    )
    logging.info("Linearity analysis completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
