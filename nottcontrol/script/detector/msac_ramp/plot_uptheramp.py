#!/usr/bin/env python3
"""Plot illuminated-region ADU along MSAC Up-the-Ramp FITS cubes.

Default data root (on the acquisition machine)::

    ~/frames/H2RG_ASIC/UpTheRamp/

MSAC writes each session into a subdirectory of that root. By default the
script selects the **latest** subdirectory (by modification time), then
loads FITS from there.

Uses the same illuminated box as the linearity analysis
(20×20 centred at X=1045, Y=943) and reports a 3σ-clipped mean of
random pixels inside that box for each saved ramp sample.

This is meant to answer: does charge grow along the MSAC ramp?
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

DEFAULT_RAMP_ROOT = Path.home() / "frames" / "H2RG_ASIC" / "UpTheRamp"
DEFAULT_N_ILLUM_PIXELS = 100
DEFAULT_ILLUM_SIZE = 20
DEFAULT_ILLUM_CENTER_X = 1045
DEFAULT_ILLUM_CENTER_Y = 943
DEFAULT_SEED = 0
DEFAULT_N_SIGMA = 3.0


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

    # Newest folder first (mtime), with name as tie-breaker.
    subdirs.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    for candidate in subdirs:
        if _fits_in_dir(candidate):
            logging.info("Using latest session folder: %s", candidate)
            return candidate.resolve()

    raise FileNotFoundError(
        f"No FITS files found in {root} or its subdirectories"
    )


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
        # Prefer NAXIS3 as sample axis when it matches the leading or trailing dim.
        naxis3 = int(header.get("NAXIS3", data.shape[0]))
        if data.shape[0] == naxis3:
            cube = data
        elif data.shape[-1] == naxis3:
            cube = np.moveaxis(data, -1, 0)
        else:
            # Fallback: assume sample-first (common for MACIE/MSAC writes).
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


def illuminated_series(
    cube: np.ndarray,
    pixels: np.ndarray,
    *,
    n_sigma: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return sample index and 3σ-clipped mean ADU for *pixels* along the ramp."""
    means: list[float] = []
    for sample in cube:
        values = np.array(
            [float(sample[int(r), int(c)]) for r, c in pixels],
            dtype=np.float64,
        )
        mean_val, n_kept, n_rej = sigma_clip_mean(values, n_sigma=n_sigma)
        means.append(mean_val)
        logging.debug(
            "sample mean=%.4g (kept %d / %d, rej %d)",
            mean_val,
            n_kept,
            n_kept + n_rej,
            n_rej,
        )
    return np.arange(cube.shape[0], dtype=np.int32), np.asarray(means, dtype=np.float64)


def pixel_tracks(cube: np.ndarray, pixels: np.ndarray) -> np.ndarray:
    """Return ``(n_pixels, nsamples)`` ADU tracks."""
    tracks = np.empty((len(pixels), cube.shape[0]), dtype=np.float64)
    for i, (row, col) in enumerate(pixels):
        tracks[i] = cube[:, int(row), int(col)]
    return tracks


def plot_ramps(
    series: list[tuple[str, np.ndarray, np.ndarray, np.ndarray | None]],
    *,
    output: Path,
    title: str,
    show: bool,
) -> None:
    fig, axes = plt.subplots(
        2 if any(tracks is not None for _, _, _, tracks in series) else 1,
        1,
        figsize=(9, 7 if any(tracks is not None for _, _, _, tracks in series) else 4.5),
        sharex=True,
        squeeze=False,
    )
    ax_mean = axes[0, 0]
    for name, samples, means, _tracks in series:
        ax_mean.plot(samples, means, "o-", label=name, markersize=4)
        if len(means) >= 2:
            delta = float(means[-1] - means[0])
            logging.info(
                "%s: n=%d  first=%.4g  last=%.4g  Δ(last-first)=%.4g ADU",
                name,
                len(means),
                means[0],
                means[-1],
                delta,
            )
    ax_mean.set_ylabel("Illuminated mean [ADU]")
    ax_mean.set_title(title)
    ax_mean.grid(True, alpha=0.3)
    if len(series) > 1:
        ax_mean.legend(fontsize=8)

    if axes.shape[0] > 1:
        ax_pix = axes[1, 0]
        for name, samples, _means, tracks in series:
            if tracks is None:
                continue
            for i in range(tracks.shape[0]):
                ax_pix.plot(
                    samples,
                    tracks[i],
                    "-",
                    alpha=0.35,
                    linewidth=0.8,
                    label=name if i == 0 else None,
                )
        ax_pix.set_ylabel("Pixel ADU")
        ax_pix.set_xlabel("Ramp sample index")
        ax_pix.grid(True, alpha=0.3)
        if len(series) > 1:
            ax_pix.legend(fontsize=8)
    else:
        ax_mean.set_xlabel("Ramp sample index")

    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    logging.info("Wrote plot: %s", output)
    if show:
        plt.show()
    else:
        plt.close(fig)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot illuminated-region ADU vs sample index for MSAC UpTheRamp FITS."
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
        default=1,
        metavar="N",
        help="If --file is omitted, plot the N newest FITS (default: 1)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Plot every FITS in --ramp-dir (overrides --latest)",
    )
    parser.add_argument(
        "--n-illum-pixels",
        type=int,
        default=DEFAULT_N_ILLUM_PIXELS,
        help=f"Random pixels in illuminated box (default: {DEFAULT_N_ILLUM_PIXELS})",
    )
    parser.add_argument(
        "--illum-size",
        type=int,
        nargs="+",
        default=None,
        metavar="N",
        help=f"Box size SIZE or HEIGHT WIDTH (default: {DEFAULT_ILLUM_SIZE})",
    )
    parser.add_argument(
        "--illum-center",
        type=int,
        nargs=2,
        default=None,
        metavar=("X", "Y"),
        help=(
            f"Illuminated centre X Y "
            f"(default: {DEFAULT_ILLUM_CENTER_X} {DEFAULT_ILLUM_CENTER_Y})"
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
        help="Also plot individual illuminated-pixel tracks",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output PNG path (default: next to first ramp / script dir)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the plot interactively",
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
    if args.file:
        paths: list[Path] = []
        for item in args.file:
            path = item.expanduser()
            if not path.is_absolute():
                path = ramp_dir / path
            if not path.is_file():
                raise FileNotFoundError(path)
            paths.append(path.resolve())
    else:
        all_paths = list_ramp_fits(ramp_dir)
        if args.all:
            paths = all_paths
        else:
            n = max(1, int(args.latest))
            paths = all_paths[-n:]
        logging.info("Using %d ramp file(s) from %s", len(paths), ramp_dir)

    if args.illum_size is None:
        illum_h = illum_w = DEFAULT_ILLUM_SIZE
    elif len(args.illum_size) == 1:
        illum_h = illum_w = int(args.illum_size[0])
    elif len(args.illum_size) == 2:
        illum_h, illum_w = int(args.illum_size[0]), int(args.illum_size[1])
    else:
        raise ValueError("--illum-size accepts SIZE or HEIGHT WIDTH")

    if args.illum_center is None:
        center_x, center_y = DEFAULT_ILLUM_CENTER_X, DEFAULT_ILLUM_CENTER_Y
    else:
        center_x, center_y = int(args.illum_center[0]), int(args.illum_center[1])

    series: list[tuple[str, np.ndarray, np.ndarray, np.ndarray | None]] = []
    pixels: np.ndarray | None = None
    for path in paths:
        cube, header = load_ramp_cube(path)
        ny, nx = cube.shape[-2], cube.shape[-1]
        logging.info(
            "%s: shape=%s  NAXIS=%s",
            path.name,
            cube.shape,
            header.get("NAXIS", "?"),
        )
        if pixels is None:
            row0, row1, col0, col1 = illuminated_box(
                (ny, nx),
                illum_h,
                illum_w,
                center_x=center_x,
                center_y=center_y,
            )
            n_illum = min(args.n_illum_pixels, (row1 - row0) * (col1 - col0))
            pixels = choose_pixels(
                (ny, nx),
                n_illum,
                args.seed,
                row_slice=(row0, row1),
                col_slice=(col0, col1),
            )
            logging.info(
                "Illuminated box %dx%d at X=%d Y=%d -> rows[%d:%d) cols[%d:%d); "
                "%d pixels (seed=%d)",
                illum_h,
                illum_w,
                center_x,
                center_y,
                row0,
                row1,
                col0,
                col1,
                n_illum,
                args.seed,
            )
        samples, means = illuminated_series(cube, pixels, n_sigma=args.n_sigma)
        tracks = pixel_tracks(cube, pixels) if args.show_pixels else None
        series.append((path.name, samples, means, tracks))

    if args.output is not None:
        output = args.output.expanduser().resolve()
    elif len(paths) == 1:
        output = paths[0].with_name(f"{paths[0].stem}_illum_ramp.png")
    else:
        output = ramp_dir / "msac_uptheramp_illum.png"

    title = (
        f"MSAC UpTheRamp — illum mean "
        f"({illum_h}×{illum_w} @ X={center_x}, Y={center_y})"
    )
    plot_ramps(series, output=output, title=title, show=args.show)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI surface
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
        logging.error("%s", exc)
        raise SystemExit(1) from exc
