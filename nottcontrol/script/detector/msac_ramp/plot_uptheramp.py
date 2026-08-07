#!/usr/bin/env python3
"""Plot illuminated-region ADU vs MSAC UpTheRamp file index.

Default data root (on the acquisition machine)::

    ~/frames/H2RG_ASIC/UpTheRamp/

MSAC writes each session into a subdirectory of that root. By default the
script selects the **latest** subdirectory (by modification time), then
loads **all** FITS there.

Frames are stacked in file-index order (last plane of each FITS, or all
planes of a single multi-sample cube). A **CDS-relative cube** is written
next to the plot: plane ``k`` is ``frame[k] - frame[0]``. The illuminated
mean plot uses that differential cube (first point is ~0).

Illuminated box: full-frame default centre ``(X=1045, Y=943)``; if the
image is smaller than 2048×2048 (windowed), the centre defaults to the
middle of the frame unless ``--illum-center`` is set.
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
# Full-frame H2RG; smaller shapes are treated as windowed readouts.
DEFAULT_FULL_FRAME = 2048
DEFAULT_SEED = 0
DEFAULT_N_SIGMA = 3.0

# MSAC names often embed both counters, e.g. ``…_N000012_M000001.fits``.
# Prefer the tag (M or N) that varies across the session; do not assume it is
# the trailing field (that is often a constant ``_M000001``).
FILE_INDEX_RE = re.compile(r"_(?P<tag>[MN])(?P<index>\d+)", re.IGNORECASE)
TRAILING_DIGITS_RE = re.compile(r"_(\d+)\s*$")


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
    """Return all ``M``/``N`` counters found in *name* (last wins per tag)."""
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
    """
    found = file_indices_from_name(name)
    if preferred_tag:
        tag = preferred_tag.upper()
        if tag in found:
            return tag, found[tag]
    if found:
        # Last match in the filename order: re-scan for ordering.
        stem = Path(name).stem
        matches = list(FILE_INDEX_RE.finditer(stem))
        match = matches[-1]
        return match.group("tag").upper(), int(match.group("index"))

    trailing = TRAILING_DIGITS_RE.search(Path(name).stem)
    if trailing:
        return "#", int(trailing.group(1))
    return None


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


def save_cube_fits(
    path: Path,
    cube: np.ndarray,
    *,
    reference_header: dict | None = None,
    history: str,
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
    header["NAXIS"] = 3
    header["NAXIS1"] = data.shape[2]
    header["NAXIS2"] = data.shape[1]
    header["NAXIS3"] = data.shape[0]
    header.add_history(history)

    fits.PrimaryHDU(data=data, header=header).writeto(path, overwrite=True)
    logging.info("Wrote CDS-relative cube (%d planes): %s", data.shape[0], path)


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
    ax_mean.set_ylabel("Illuminated mean (frame−first) [ADU]")
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
        ax_pix.set_ylabel("Pixel ADU (frame−first)")
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
            "Illuminated centre X Y (image coords). Default: full-frame "
            f"({DEFAULT_ILLUM_CENTER_X}, {DEFAULT_ILLUM_CENTER_Y}); "
            f"for frames smaller than {DEFAULT_FULL_FRAME}×{DEFAULT_FULL_FRAME}, "
            "use the image centre."
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
            "Output FITS cube path for planes = frame - first "
            "(default: msac_uptheramp_frame_minus_first.fits in the session dir)"
        ),
    )
    parser.add_argument(
        "--no-cds-cube",
        action="store_true",
        help="Skip writing the frame-minus-first FITS cube",
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

    if args.index_tag == "auto":
        preferred_tag = choose_index_tag(paths)
    else:
        preferred_tag = args.index_tag
        logging.info("Using forced file-index tag: %s", preferred_tag)

    if args.illum_size is None:
        illum_h = illum_w = DEFAULT_ILLUM_SIZE
    elif len(args.illum_size) == 1:
        illum_h = illum_w = int(args.illum_size[0])
    elif len(args.illum_size) == 2:
        illum_h, illum_w = int(args.illum_size[0]), int(args.illum_size[1])
    else:
        raise ValueError("--illum-size accepts SIZE or HEIGHT WIDTH")

    explicit_center = args.illum_center is not None
    req_center_x = int(args.illum_center[0]) if explicit_center else None
    req_center_y = int(args.illum_center[1]) if explicit_center else None

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
    cds_cube = relative_to_first(stack)
    indices = np.array([row[0] for row in records], dtype=np.int64)
    names = [row[2] for row in records]
    index_tag = records[0][1]
    ny, nx = int(stack.shape[-2]), int(stack.shape[-1])
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

    means = np.array(
        [
            illuminated_mean_for_image(plane, pixels, n_sigma=args.n_sigma)
            for plane in cds_cube
        ],
        dtype=np.float64,
    )
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

    if not args.no_cds_cube:
        if args.cds_cube is not None:
            cds_path = args.cds_cube.expanduser()
            if not cds_path.is_absolute():
                cds_path = (ramp_dir / cds_path).resolve()
            else:
                cds_path = cds_path.resolve()
        else:
            cds_path = ramp_dir / "msac_uptheramp_frame_minus_first.fits"
        save_cube_fits(
            cds_path,
            cds_cube,
            reference_header=ref_header,
            history=(
                "MSAC UpTheRamp CDS-relative cube: each plane = "
                "sample - first sample (ordered by file/plane index)."
            ),
        )

    title = (
        f"MSAC UpTheRamp — illum mean (frame−first) vs index "
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
