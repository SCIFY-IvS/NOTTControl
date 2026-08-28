#!/usr/bin/env python3
"""Scan MSAC UpTheRamp session folders and rank ramp quality.

Each immediate subdirectory of ``--root`` that contains FITS files is treated
as one acquisition session. For every session the script builds the same
illuminated flux vs file-index series used by ``plot_uptheramp.py`` (CDS
relative to reset or first sample, photonic-chip brightest pixels) and
scores whether flux **increases** with ramp index.

Example::

    ./nottcontrol/script/detector/msac_ramp/scan_uptheramp_sessions.py
    ./nottcontrol/script/detector/msac_ramp/scan_uptheramp_sessions.py \\
        --root /data/bench_data/H2RG_ASIC/UpTheRamp --top 5
    ./nottcontrol/script/detector/msac_ramp/scan_uptheramp_sessions.py --good-only
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

DEFAULT_ROOT = Path("/data/bench_data/H2RG_ASIC/UpTheRamp")
DEFAULT_MIN_FILES = 3
DEFAULT_MIN_RANGE_ADU = 5.0
DEFAULT_MIN_R2 = 0.5
DEFAULT_MIN_FRAC_INCREASING = 0.6
DEFAULT_MIN_SPEARMAN = 0.6
DEFAULT_N_BRIGHTEST = 10
DEFAULT_N_SIGMA = 3.0

try:
    from . import plot_uptheramp as ramp
except ImportError:
    import plot_uptheramp as ramp  # type: ignore[no-redef]


@dataclass(frozen=True)
class SessionScore:
    path: Path
    n_files: int
    n_points: int
    index_tag: str
    slope: float
    intercept: float
    r2: float
    spearman: float
    frac_increasing: float
    flux_min: float
    flux_max: float
    flux_range: float
    good: bool
    note: str

    @property
    def name(self) -> str:
        return self.path.name


def _fits_in_dir(directory: Path) -> bool:
    return any(
        p.is_file() and p.suffix.lower() == ".fits" for p in directory.iterdir()
    )


def collect_session_dirs(root: Path) -> list[Path]:
    """Return session folders under *root* (each must contain FITS)."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"UpTheRamp root not found: {root}")

    if _fits_in_dir(root):
        return [root]

    sessions = [
        child.resolve()
        for child in sorted(root.iterdir())
        if child.is_dir() and _fits_in_dir(child)
    ]
    if sessions:
        return sessions

    raise FileNotFoundError(
        f"No session folders with FITS under {root}"
    )


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size < 2:
        return float("nan")
    rx = np.argsort(np.argsort(x))
    ry = np.argsort(np.argsort(y))
    corr = np.corrcoef(rx, ry)
    return float(corr[0, 1])


def _linear_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size < 2:
        return float("nan"), float("nan"), float("nan")
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return float(slope), float(intercept), float(r2)


def _frac_increasing(values: np.ndarray) -> float:
    y = np.asarray(values, dtype=np.float64)
    if y.size < 2:
        return float("nan")
    diffs = np.diff(y)
    return float(np.mean(diffs > 0))


def build_flux_series(
    session_dir: Path,
    *,
    n_brightest: int,
    n_sigma: float,
    no_reset: bool,
) -> tuple[np.ndarray, np.ndarray, str, int]:
    """Return ``(indices, flux_adu, index_tag, n_science_files)`` for *session_dir*."""
    folder_fits = ramp.list_ramp_fits(session_dir)
    science_paths, reset_from_folder = ramp.split_science_and_reset(folder_fits)

    reset_paths: list[Path] = []
    if not no_reset:
        reset_paths = list({p.resolve() for p in reset_from_folder})

    reset_loaded = None if no_reset else ramp.load_reset_reference(reset_paths)
    reset_frame = reset_loaded[0] if reset_loaded is not None else None

    preferred_tag = ramp.choose_index_tag(science_paths)
    records: list[tuple[int, str, str, np.ndarray]] = []

    if len(science_paths) == 1:
        only_cube, _header = ramp.load_ramp_cube(science_paths[0])
        if only_cube.shape[0] > 1:
            parsed = ramp.file_index_from_name(
                science_paths[0].name, preferred_tag=preferred_tag
            )
            base_tag = parsed[0] if parsed else "P"
            for iplane, plane in enumerate(only_cube):
                records.append(
                    (
                        iplane + 1,
                        base_tag,
                        f"{science_paths[0].name}[plane{iplane}]",
                        np.asarray(plane, dtype=np.float64),
                    )
                )

    if not records:
        for path in science_paths:
            parsed = ramp.file_index_from_name(
                path.name, preferred_tag=preferred_tag
            )
            if parsed is None:
                continue
            tag, index = parsed
            cube, _header = ramp.load_ramp_cube(path)
            records.append(
                (
                    index,
                    tag,
                    path.name,
                    np.asarray(ramp.last_plane(cube), dtype=np.float64),
                )
            )

    if not records:
        raise RuntimeError("no science FITS with M/N file index")

    records.sort(key=lambda row: (row[0], row[2].lower()))
    stack = np.stack([row[3] for row in records], axis=0)
    if reset_frame is not None:
        if reset_frame.shape != stack.shape[1:]:
            raise RuntimeError("reset frame shape mismatch")
        cds_cube = ramp.relative_to_reference(stack, reset_frame)
    else:
        cds_cube = ramp.relative_to_first(stack)

    ny, nx = int(stack.shape[-2]), int(stack.shape[-1])
    (row0, row1, col0, col1), _det_box = ramp.photonic_chip_illum_box((ny, nx))
    pixels, _n_rej = ramp.select_brightest_after_outliers(
        cds_cube[-1],
        row0,
        row1,
        col0,
        col1,
        n_brightest=n_brightest,
        n_sigma=n_sigma,
    )
    if pixels.shape[0] == 0:
        raise RuntimeError("no usable bright pixels in photonic box")

    means = np.array(
        [
            float(np.mean(ramp.pixel_values(plane, pixels)))
            for plane in cds_cube
        ],
        dtype=np.float64,
    )
    indices = np.array([row[0] for row in records], dtype=np.int64)
    index_tag = records[0][1]
    return indices, means, index_tag, len(science_paths)


def score_session(
    session_dir: Path,
    *,
    n_brightest: int,
    n_sigma: float,
    no_reset: bool,
    min_files: int,
    min_range: float,
    min_r2: float,
    min_frac_increasing: float,
    min_spearman: float,
) -> SessionScore:
    session_dir = session_dir.resolve()
    try:
        indices, means, index_tag, n_files = build_flux_series(
            session_dir,
            n_brightest=n_brightest,
            n_sigma=n_sigma,
            no_reset=no_reset,
        )
    except Exception as exc:
        return SessionScore(
            path=session_dir,
            n_files=0,
            n_points=0,
            index_tag="?",
            slope=float("nan"),
            intercept=float("nan"),
            r2=float("nan"),
            spearman=float("nan"),
            frac_increasing=float("nan"),
            flux_min=float("nan"),
            flux_max=float("nan"),
            flux_range=float("nan"),
            good=False,
            note=str(exc),
        )

    n_points = int(means.size)
    if not np.all(np.isfinite(means)):
        return SessionScore(
            path=session_dir,
            n_files=n_files,
            n_points=n_points,
            index_tag=index_tag,
            slope=float("nan"),
            intercept=float("nan"),
            r2=float("nan"),
            spearman=float("nan"),
            frac_increasing=float("nan"),
            flux_min=float("nan"),
            flux_max=float("nan"),
            flux_range=float("nan"),
            good=False,
            note="non-finite flux values",
        )

    slope, intercept, r2 = _linear_fit(indices.astype(float), means)
    spearman = _spearman(indices, means)
    frac_inc = _frac_increasing(means)
    flux_min = float(np.min(means))
    flux_max = float(np.max(means))
    flux_range = flux_max - flux_min

    reasons: list[str] = []
    if n_files < min_files:
        reasons.append(f"files<{min_files}")
    if n_points < min_files:
        reasons.append(f"points<{min_files}")
    if flux_range < min_range:
        reasons.append(f"range<{min_range:g}ADU")
    if not np.isfinite(slope) or slope <= 0:
        reasons.append("slope<=0")
    if not np.isfinite(r2) or r2 < min_r2:
        reasons.append(f"R²<{min_r2:g}")
    if not np.isfinite(frac_inc) or frac_inc < min_frac_increasing:
        reasons.append(f"inc<{min_frac_increasing:g}")
    if not np.isfinite(spearman) or spearman < min_spearman:
        reasons.append(f"ρ<{min_spearman:g}")

    good = not reasons
    note = "ok" if good else ", ".join(reasons)
    return SessionScore(
        path=session_dir,
        n_files=n_files,
        n_points=n_points,
        index_tag=index_tag,
        slope=slope,
        intercept=intercept,
        r2=r2,
        spearman=spearman,
        frac_increasing=frac_inc,
        flux_min=flux_min,
        flux_max=flux_max,
        flux_range=flux_range,
        good=good,
        note=note,
    )


def rank_key(score: SessionScore) -> tuple:
    """Sort good sessions first, then by quality."""
    return (
        0 if score.good else 1,
        -score.r2 if np.isfinite(score.r2) else 999.0,
        -score.spearman if np.isfinite(score.spearman) else 999.0,
        -score.flux_range if np.isfinite(score.flux_range) else 999.0,
        score.name.lower(),
    )


def format_table(scores: list[SessionScore]) -> str:
    headers = (
        "good",
        "session",
        "files",
        "pts",
        "tag",
        "slope",
        "R²",
        "ρ",
        "inc",
        "Δflux",
        "note",
    )
    rows: list[list[str]] = []
    for s in scores:
        rows.append(
            [
                "Y" if s.good else "N",
                s.name,
                str(s.n_files),
                str(s.n_points),
                s.index_tag,
                f"{s.slope:.4g}" if np.isfinite(s.slope) else "—",
                f"{s.r2:.3f}" if np.isfinite(s.r2) else "—",
                f"{s.spearman:.3f}" if np.isfinite(s.spearman) else "—",
                f"{s.frac_increasing:.2f}" if np.isfinite(s.frac_increasing) else "—",
                f"{s.flux_range:.2g}" if np.isfinite(s.flux_range) else "—",
                s.note,
            ]
        )
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(cells: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    lines = [fmt_row(headers), fmt_row(["-" * w for w in widths])]
    lines.extend(fmt_row(row) for row in rows)
    return "\n".join(lines)


def write_csv(path: Path, scores: list[SessionScore]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "good",
                "session_path",
                "session_name",
                "n_files",
                "n_points",
                "index_tag",
                "slope",
                "intercept",
                "r2",
                "spearman",
                "frac_increasing",
                "flux_min",
                "flux_max",
                "flux_range",
                "note",
            ]
        )
        for s in scores:
            writer.writerow(
                [
                    s.good,
                    str(s.path),
                    s.name,
                    s.n_files,
                    s.n_points,
                    s.index_tag,
                    s.slope,
                    s.intercept,
                    s.r2,
                    s.spearman,
                    s.frac_increasing,
                    s.flux_min,
                    s.flux_max,
                    s.flux_range,
                    s.note,
                ]
            )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan UpTheRamp session folders and find acquisitions where "
            "illuminated flux increases with ramp file index."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"UpTheRamp root containing session subfolders (default: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        metavar="N",
        help="Print only the N best-ranked sessions",
    )
    parser.add_argument(
        "--good-only",
        action="store_true",
        help="Show only sessions that pass all quality cuts",
    )
    parser.add_argument(
        "--min-files",
        type=int,
        default=DEFAULT_MIN_FILES,
        help=f"Minimum science FITS count (default: {DEFAULT_MIN_FILES})",
    )
    parser.add_argument(
        "--min-range",
        type=float,
        default=DEFAULT_MIN_RANGE_ADU,
        help=f"Minimum flux range ADU after CDS (default: {DEFAULT_MIN_RANGE_ADU})",
    )
    parser.add_argument(
        "--min-r2",
        type=float,
        default=DEFAULT_MIN_R2,
        help=f"Minimum linear R² of flux vs index (default: {DEFAULT_MIN_R2})",
    )
    parser.add_argument(
        "--min-frac-increasing",
        type=float,
        default=DEFAULT_MIN_FRAC_INCREASING,
        help=(
            "Minimum fraction of consecutive samples with increasing flux "
            f"(default: {DEFAULT_MIN_FRAC_INCREASING})"
        ),
    )
    parser.add_argument(
        "--min-spearman",
        type=float,
        default=DEFAULT_MIN_SPEARMAN,
        help=f"Minimum Spearman ρ(index, flux) (default: {DEFAULT_MIN_SPEARMAN})",
    )
    parser.add_argument(
        "--n-brightest",
        type=int,
        default=DEFAULT_N_BRIGHTEST,
        help=f"Bright pixels averaged (same as plot_uptheramp; default: {DEFAULT_N_BRIGHTEST})",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Subtract first science sample instead of _R reset frame",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write full results table to CSV",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format=LOG_FORMAT,
    )

    sessions = collect_session_dirs(args.root)
    all_scores = [
        score_session(
            session,
            n_brightest=max(1, int(args.n_brightest)),
            n_sigma=DEFAULT_N_SIGMA,
            no_reset=bool(args.no_reset),
            min_files=max(1, int(args.min_files)),
            min_range=float(args.min_range),
            min_r2=float(args.min_r2),
            min_frac_increasing=float(args.min_frac_increasing),
            min_spearman=float(args.min_spearman),
        )
        for session in sessions
    ]
    all_scores.sort(key=rank_key)
    n_total = len(all_scores)
    n_good_total = sum(1 for s in all_scores if s.good)

    scores = all_scores
    if args.good_only:
        scores = [s for s in scores if s.good]
    if args.top is not None:
        scores = scores[: max(1, int(args.top))]

    print(f"Scanned {n_total} session folder(s) under {args.root.resolve()}")
    print(
        f"Quality cuts: slope>0, R²>={args.min_r2}, "
        f"inc>={args.min_frac_increasing}, ρ>={args.min_spearman}, "
        f"Δflux>={args.min_range} ADU, files>={args.min_files}"
    )
    if not scores:
        print("No sessions matched the filters.")
        return 1

    print(format_table(scores))
    if args.good_only:
        print(f"\n{len(scores)} good session(s) shown.")
    else:
        print(f"\n{n_good_total} / {n_total} session(s) pass all cuts.")

    best = next((s for s in all_scores if s.good), None)
    if best is not None:
        print(f"\nBest session: {best.path}")
        print(
            f"  plot: ./nottcontrol/script/detector/msac_ramp/plot_uptheramp.sh "
            f'--ramp-dir "{best.path}"'
        )
    elif scores[0].n_points > 0:
        print(f"\nNo session passed all cuts. Closest: {scores[0].path} ({scores[0].note})")

    if args.csv is not None:
        write_csv(args.csv.expanduser().resolve(), scores)
        print(f"\nWrote CSV: {args.csv}")

    return 0 if best is not None else 2


if __name__ == "__main__":
    sys.exit(main())
