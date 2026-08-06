#!/usr/bin/env python3
"""Plot illuminated-region ADU vs MSAC UpTheRamp file index.

Default data root (on the acquisition machine)::

    ~/frames/H2RG_ASIC/UpTheRamp/

MSAC writes each session into a subdirectory of that root. By default the
script selects the **latest** subdirectory (by modification time), then
loads **all** FITS there.

For each file it takes the last ramp sample (or the only plane), measures a
3σ-clipped mean in the same illuminated box as the linearity analysis
(20×20 at X=1045, Y=943), and plots that mean vs the file index parsed from
the name (``_M######`` or ``_N######``).
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
DEFAULT_ILLUM_SIZE = 20
DEFAULT_ILLUM_CENTER_X = 1045
DEFAULT_ILLUM_CENTER_Y = 943
DEFAULT_SEED = 0
DEFAULT_N_SIGMA = 3.0

# MSAC names typically end with _M000001 or _N000001 before .fits
FILE_INDEX_RE = re.compile(r"_(?P<tag>[MN])(?P<index>\d+)\s*$", re.IGNORECASE)


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


def file_index_from_name(name: str) -> tuple[str, int] | None:
    """Return ``(tag, index)`` from ``…_M000012.fits`` / ``…_N000012.fits``."""
    stem = Path(name).stem
    match = FILE_INDEX_RE.search(stem)
    if not match:
        return None
    return match.group("tag").upper(), int(match.group("index"))


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
) -> None:
    show_pixels = pixel_matrix is not None and pixel_matrix.size > 0
    fig, axes = plt.subplots(
        2 if show_pixels else 1,
        1,
        figsize=(9, 7 if show_pixels else 4.5),
        sharex=True,
        squeeze=False,
    )
    ax_mean = axes[0, 0]
    ax_mean.plot(indices, means, "o-", markersize=5, color="C0")
    for index, mean_val, name in zip(indices, means, names):
        logging.info(
            "%s: index=%s%d  illum_mean=%.4g ADU",
            name,
            index_tag,
            int(index),
            mean_val,
        )
    ax_mean.set_ylabel("Illuminated mean [ADU]")
    ax_mean.set_title(title)
    ax_mean.grid(True, alpha=0.3)

    if show_pixels:
        ax_pix = axes[1, 0]
        for i in range(pixel_matrix.shape[1]):
            ax_pix.plot(
                indices,
                pixel_matrix[:, i],
                "-",
                alpha=0.25,
                linewidth=0.7,
                color="C1",
            )
        ax_pix.set_ylabel("Pixel ADU")
        ax_pix.set_xlabel(f"File index ({index_tag})")
        ax_pix.grid(True, alpha=0.3)
    else:
        ax_mean.set_xlabel(f"File index ({index_tag})")

    fig.tight_layout()
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
            "Plot illuminated-region ADU vs MSAC file index (_M / _N) "
            "for UpTheRamp FITS."
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
        help="Use only the N newest FITS (default: all files in the session)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Plot every FITS in --ramp-dir (default behaviour)",
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
        if args.latest is not None and not args.all:
            n = max(1, int(args.latest))
            paths = all_paths[-n:]
        else:
            paths = all_paths
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

    records: list[tuple[int, str, str, float, np.ndarray | None]] = []
    pixels: np.ndarray | None = None
    index_tag = "M"

    for path in paths:
        parsed = file_index_from_name(path.name)
        if parsed is None:
            logging.warning(
                "Skipping %s: no _M###### or _N###### index in the name",
                path.name,
            )
            continue
        tag, index = parsed
        index_tag = tag

        cube, header = load_ramp_cube(path)
        ny, nx = cube.shape[-2], cube.shape[-1]
        logging.info(
            "%s: shape=%s  NAXIS=%s  index=%s%d",
            path.name,
            cube.shape,
            header.get("NAXIS", "?"),
            tag,
            index,
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

        image = last_plane(cube)
        mean_val = illuminated_mean_for_image(
            image, pixels, n_sigma=args.n_sigma
        )
        pix_vals = (
            pixel_values(image, pixels) if args.show_pixels else None
        )
        records.append((index, tag, path.name, mean_val, pix_vals))

    if not records:
        raise RuntimeError(
            "No usable FITS with an _M / _N file index in the name"
        )

    records.sort(key=lambda row: (row[0], row[2].lower()))
    indices = np.array([row[0] for row in records], dtype=np.int64)
    means = np.array([row[3] for row in records], dtype=np.float64)
    names = [row[2] for row in records]
    index_tag = records[0][1]

    pixel_matrix: np.ndarray | None = None
    if args.show_pixels:
        pixel_matrix = np.stack(
            [row[4] for row in records if row[4] is not None],
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

    title = (
        f"MSAC UpTheRamp — illum mean vs file index "
        f"({illum_h}×{illum_w} @ X={center_x}, Y={center_y})"
    )
    plot_file_series(
        indices=indices,
        means=means,
        names=names,
        index_tag=index_tag,
        pixel_matrix=pixel_matrix,
        output=output,
        title=title,
        show=args.show,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI surface
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
        logging.error("%s", exc)
        raise SystemExit(1) from exc
