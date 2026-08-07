#!/usr/bin/env python3
"""Average H2RG frames at each snake FOV scan position.

Default log (2026-08-06 lab notes, 5 frames per dwell, ends at 889)::

    830-834  Snake        open
    835-839  Background   close
    840-844  Snake        open
    …
    880-884  Snake/double open
    885-889  Snake        open

For each **Snake** (and Snake/double) block the script writes
``mean(frames)``. Optionally subtracts ``mean(background)`` from the
closed-shutter Background block. Also writes a cube with one plane per
snake position.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nottcontrol.script.detector.linearity.analyze_linearity import (
    build_frame_catalog,
    frames_for_range,
    load_image,
    resolve_data_dir,
)

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

# (start, end, label, shutter) — shutter open/close from the lab log.
DEFAULT_BLOCKS: tuple[tuple[int, int, str, str], ...] = (
    (830, 834, "snake", "open"),
    (835, 839, "background", "close"),
    (840, 844, "snake", "open"),
    (845, 849, "snake", "open"),
    (850, 854, "snake", "open"),
    (855, 859, "snake", "open"),
    (860, 864, "snake", "open"),
    (865, 869, "snake", "open"),
    (870, 874, "snake", "open"),
    (875, 879, "snake", "open"),
    (880, 884, "snake_double", "open"),
    (885, 889, "snake", "open"),
)


@dataclass(frozen=True)
class ScanBlock:
    start: int
    end: int
    label: str
    shutter: str

    @property
    def n_frames(self) -> int:
        return self.end - self.start + 1

    @property
    def is_background(self) -> bool:
        return self.label.lower().startswith("background")

    @property
    def is_snake(self) -> bool:
        return self.label.lower().startswith("snake")


def parse_log_file(path: Path) -> list[ScanBlock]:
    """Parse a simple log: ``START END LABEL SHUTTER`` (``#`` comments ok)."""
    blocks: list[ScanBlock] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Allow "830-834 snake open" or "830 834 snake open"
        line = line.replace(",", " ")
        m = re.match(
            r"^(?P<a>\d+)\s*[-:]\s*(?P<b>\d+)\s+"
            r"(?P<label>\S+)\s+(?P<shutter>\S+)\s*$",
            line,
            re.IGNORECASE,
        )
        if m is None:
            m = re.match(
                r"^(?P<a>\d+)\s+(?P<b>\d+)\s+"
                r"(?P<label>\S+)\s+(?P<shutter>\S+)\s*$",
                line,
                re.IGNORECASE,
            )
        if m is None:
            raise ValueError(f"Bad log line in {path}: {raw!r}")
        a, b = int(m.group("a")), int(m.group("b"))
        if b < a:
            raise ValueError(f"Empty frame range in {path}: {raw!r}")
        blocks.append(
            ScanBlock(
                start=a,
                end=b,
                label=m.group("label"),
                shutter=m.group("shutter").lower(),
            )
        )
    if not blocks:
        raise ValueError(f"No blocks parsed from {path}")
    return blocks


def default_blocks() -> list[ScanBlock]:
    return [
        ScanBlock(a, b, label, shutter)
        for a, b, label, shutter in DEFAULT_BLOCKS
    ]


def average_block(
    catalog: dict,
    block: ScanBlock,
    *,
    reduction: str,
) -> tuple[np.ndarray, list[int]]:
    files = frames_for_range(catalog, block.start, block.end)
    images: list[np.ndarray] = []
    for item in files:
        image, dit_s = load_image(item.path, reduction=reduction)
        images.append(image)
        logging.info(
            "%s frames %06d–%06d: frame %06d  DIT=%.6g s  %s",
            block.label,
            block.start,
            block.end,
            item.frame,
            dit_s,
            item.path.name,
        )
    stack = np.mean(np.stack(images, axis=0), axis=0)
    return np.asarray(stack, dtype=np.float64), [item.frame for item in files]


def save_fits(
    path: Path,
    data: np.ndarray,
    *,
    header_cards: dict,
) -> None:
    from astropy.io import fits

    path.parent.mkdir(parents=True, exist_ok=True)
    header = fits.Header()
    for key, value in header_cards.items():
        if isinstance(value, tuple) and len(value) == 2:
            header[key] = value
        else:
            header[key] = value
    fits.PrimaryHDU(
        data=np.asarray(data, dtype=np.float32),
        header=header,
    ).writeto(path, overwrite=True)
    logging.info("Wrote %s  shape=%s", path.name, data.shape)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Average H2RG snake FOV dwells (5 frames/position) and "
            "optionally subtract the closed-shutter background block."
        )
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory with nott_YYYYMMDD_NNNNNN.fits (overrides --data-root/--day)",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Parent of YYYYMMDD folders",
    )
    parser.add_argument(
        "--day",
        metavar="YYYYMMDD",
        default=None,
        help="UTC day folder under --data-root (default: today UTC)",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help=(
            "Optional scan log file (START-END LABEL SHUTTER per line). "
            "Default: built-in 2026-08-06 snake log (ends at 889)."
        ),
    )
    parser.add_argument(
        "--reduction",
        choices=("CDS", "Ramp", "Fowler", "SingleFrame"),
        default="Ramp",
        help="Ramp reduction for raw cubes (default: Ramp)",
    )
    parser.add_argument(
        "--prefer-raw",
        action="store_true",
        help="Prefer raw ramp FITS over *_science.fits",
    )
    parser.add_argument(
        "--no-bg-sub",
        action="store_true",
        help="Do not subtract the Background (close) block mean",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Output directory "
            "(default: <script_dir>/snake_<day>_avg)"
        ),
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
    blocks = parse_log_file(args.log) if args.log else default_blocks()
    for block in blocks:
        logging.info(
            "Plan: %06d–%06d  %-14s  shutter=%s",
            block.start,
            block.end,
            block.label,
            block.shutter,
        )

    try:
        catalog = build_frame_catalog(
            data_dir, prefer_science=not args.prefer_raw
        )
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 1

    day_label = args.day or data_dir.name
    out_dir = args.output_dir or (
        Path(__file__).resolve().parent / f"snake_{day_label}_avg"
    )

    background: np.ndarray | None = None
    bg_blocks = [b for b in blocks if b.is_background]
    if bg_blocks and not args.no_bg_sub:
        if len(bg_blocks) > 1:
            logging.warning(
                "Multiple background blocks (%d); using the first (%d–%d)",
                len(bg_blocks),
                bg_blocks[0].start,
                bg_blocks[0].end,
            )
        try:
            background, _ = average_block(
                catalog, bg_blocks[0], reduction=args.reduction
            )
        except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
            logging.error("Background block failed: %s", exc)
            return 1
        bg_path = out_dir / (
            f"snake_{day_label}_background_"
            f"{bg_blocks[0].start:06d}-{bg_blocks[0].end:06d}_mean.fits"
        )
        save_fits(
            bg_path,
            background,
            header_cards={
                "IMTYPE": ("BGMEAN", "mean of closed-shutter background frames"),
                "FRMSTART": (bg_blocks[0].start, "First background frame"),
                "FRMEND": (bg_blocks[0].end, "Last background frame"),
                "NFRAMES": (bg_blocks[0].n_frames, "Frames averaged"),
                "LABEL": (bg_blocks[0].label, "Log label"),
                "SHUTTER": (bg_blocks[0].shutter, "Shutter state"),
            },
        )
    elif args.no_bg_sub:
        logging.info("Skipping background subtraction (--no-bg-sub)")
    else:
        logging.warning("No background block in log; writing raw means only")

    snake_blocks = [b for b in blocks if b.is_snake]
    if not snake_blocks:
        logging.error("No snake positions in the log")
        return 1

    means: list[np.ndarray] = []
    labels: list[str] = []
    for index, block in enumerate(snake_blocks, start=1):
        try:
            mean_img, frame_ids = average_block(
                catalog, block, reduction=args.reduction
            )
        except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
            logging.error("Snake block %d–%d failed: %s", block.start, block.end, exc)
            return 1

        product = mean_img
        imtype = "SNAKEMEAN"
        if background is not None:
            product = mean_img - background
            imtype = "SNAKE-BG"

        slug = re.sub(r"[^A-Za-z0-9]+", "_", block.label).strip("_") or "snake"
        path = out_dir / (
            f"snake_{day_label}_pos{index:02d}_{slug}_"
            f"{block.start:06d}-{block.end:06d}_mean.fits"
        )
        save_fits(
            path,
            product,
            header_cards={
                "IMTYPE": (imtype, "mean(snake dwell) [- background]"),
                "POSINDEX": (index, "Snake position index (1-based)"),
                "FRMSTART": (block.start, "First dwell frame"),
                "FRMEND": (block.end, "Last dwell frame"),
                "NFRAMES": (block.n_frames, "Frames averaged"),
                "LABEL": (block.label, "Log label"),
                "SHUTTER": (block.shutter, "Shutter state"),
                "BGSUB": (background is not None, "Background subtracted"),
                "COMMENT": (
                    f"Frames averaged: {', '.join(f'{n:06d}' for n in frame_ids)}"
                ),
            },
        )
        means.append(np.asarray(product, dtype=np.float32))
        labels.append(f"pos{index:02d}:{block.start}-{block.end}")

    cube = np.stack(means, axis=0)
    cube_path = out_dir / f"snake_{day_label}_positions_cube.fits"
    save_fits(
        cube_path,
        cube,
        header_cards={
            "IMTYPE": (
                "SNAKECUBE",
                "Plane k = mean at snake position k (bg-sub if enabled)",
            ),
            "NPOS": (len(means), "Number of snake positions"),
            "BGSUB": (background is not None, "Background subtracted"),
            "COMMENT": "Planes: " + "; ".join(labels),
        },
    )
    logging.info(
        "Snake FOV average done: %d positions → %s",
        len(means),
        out_dir,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI surface
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
        logging.error("%s", exc)
        raise SystemExit(1) from exc
