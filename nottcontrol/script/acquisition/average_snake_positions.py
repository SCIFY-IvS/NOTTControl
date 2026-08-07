#!/usr/bin/env python3
"""Average H2RG frames at each snake FOV scan position.

Default (2026-08-06): frames **301–889**. Open vs closed is taken from
FITS shutter positions ``SH1POS``…``SH4POS`` (open≈5 mm, closed≈35 mm):
all closed → background; any open → snake dwell. Consecutive frames with
the same state are grouped into blocks.

Each snake mean subtracts the **closest** background mean. The positions
cube is stacked from those background-subtracted means (unless
``--no-bg-sub``). Pass ``--log`` to override header-based classification.
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
    FrameFile,
    build_frame_catalog,
    frames_for_range,
    load_image,
    resolve_data_dir,
)

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LOG = SCRIPT_DIR / "snake_20260806.log"
# Inclusive frame range for the bundled 2026-08-06 snake scan.
DEFAULT_SNAKE_FIRST = 301
DEFAULT_SNAKE_LAST = 889

# FITS cards from fits_header_meta.H2RG_FITS_SHUTTER_FIELDS.
SHUTTER_POS_KEYS = ("SH1POS", "SH2POS", "SH3POS", "SH4POS")
# open≈5 mm, closed≈35 mm — classify with midpoint threshold.
SHUTTER_CLOSED_MM = 20.0


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
    def midpoint(self) -> float:
        return 0.5 * (self.start + self.end)

    @property
    def is_background(self) -> bool:
        label = self.label.lower()
        if label.startswith("snake"):
            return False
        return label.startswith("background") or self.shutter in (
            "close",
            "closed",
        )

    @property
    def is_snake(self) -> bool:
        return self.label.lower().startswith("snake")


def read_fits_header(path: Path) -> dict:
    from astropy.io import fits

    with fits.open(path, memmap=True) as hdul:
        return dict(hdul[0].header)


def shutter_state_from_header(header: dict) -> str:
    """Return ``close`` if all reported shutters are closed, else ``open``.

    Missing ``SHnPOS`` cards are ignored. Raises ``KeyError`` if none are
    present.
    """
    positions: list[float] = []
    for key in SHUTTER_POS_KEYS:
        if key in header and header[key] is not None:
            positions.append(float(header[key]))
    if not positions:
        raise KeyError(
            "No shutter position cards "
            f"({', '.join(SHUTTER_POS_KEYS)}) in FITS header"
        )
    if all(pos >= SHUTTER_CLOSED_MM for pos in positions):
        return "close"
    return "open"


def blocks_from_shutter_headers(
    catalog: dict[int, FrameFile],
    first: int,
    last: int,
) -> list[ScanBlock]:
    """Group consecutive frames by open/closed state from FITS headers."""
    files = frames_for_range(catalog, first, last)
    states: list[tuple[int, str]] = []
    for item in files:
        try:
            state = shutter_state_from_header(read_fits_header(item.path))
        except KeyError as exc:
            raise KeyError(f"Frame {item.frame:06d} ({item.path.name}): {exc}") from exc
        states.append((item.frame, state))
        logging.info(
            "Frame %06d shutter=%s  %s",
            item.frame,
            state,
            item.path.name,
        )

    blocks: list[ScanBlock] = []
    run_start, run_state = states[0]
    prev = run_start
    for frame, state in states[1:]:
        if state == run_state and frame == prev + 1:
            prev = frame
            continue
        label = "background" if run_state == "close" else "snake"
        blocks.append(ScanBlock(run_start, prev, label, run_state))
        run_start, run_state, prev = frame, state, frame
    label = "background" if run_state == "close" else "snake"
    blocks.append(ScanBlock(run_start, prev, label, run_state))
    return blocks


def parse_log_file(path: Path) -> list[ScanBlock]:
    """Parse a simple log: ``START END LABEL SHUTTER`` (``#`` comments ok)."""
    blocks: list[ScanBlock] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
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


def closest_background(
    snake: ScanBlock,
    backgrounds: list[tuple[ScanBlock, np.ndarray]],
) -> tuple[ScanBlock, np.ndarray]:
    """Return the background mean whose frame range is nearest to *snake*."""
    if not backgrounds:
        raise ValueError("No background means available")
    return min(
        backgrounds,
        key=lambda item: abs(item[0].midpoint - snake.midpoint),
    )


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
            "Average H2RG snake FOV dwells and subtract the closest "
            "closed-shutter background (from FITS SHnPOS, or --log)."
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
        "--first",
        type=int,
        default=DEFAULT_SNAKE_FIRST,
        help=f"First frame (inclusive) when using headers (default: {DEFAULT_SNAKE_FIRST})",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=DEFAULT_SNAKE_LAST,
        help=f"Last frame (inclusive) when using headers (default: {DEFAULT_SNAKE_LAST})",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help=(
            "Optional scan log (START-END LABEL SHUTTER). "
            "If omitted, open/closed is read from FITS SH1POS…SH4POS."
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
        help="Do not subtract background means from snake dwell means",
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

    try:
        catalog = build_frame_catalog(
            data_dir, prefer_science=not args.prefer_raw
        )
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 1

    try:
        if args.log is not None:
            blocks = parse_log_file(args.log)
            logging.info("Scan plan from log: %s", args.log)
        else:
            if args.last < args.first:
                logging.error("--last (%d) < --first (%d)", args.last, args.first)
                return 1
            logging.info(
                "Scan plan from FITS shutter headers (frames %d–%d)",
                args.first,
                args.last,
            )
            blocks = blocks_from_shutter_headers(
                catalog, args.first, args.last
            )
    except (FileNotFoundError, KeyError, ValueError, OSError) as exc:
        logging.error("%s", exc)
        return 1

    for block in blocks:
        logging.info(
            "Plan: %06d–%06d  %-14s  shutter=%s",
            block.start,
            block.end,
            block.label,
            block.shutter,
        )

    day_label = args.day or data_dir.name
    out_dir = args.output_dir or (
        Path(__file__).resolve().parent / f"snake_{day_label}_avg"
    )

    bg_means: list[tuple[ScanBlock, np.ndarray]] = []
    bg_blocks = [b for b in blocks if b.is_background]
    if bg_blocks and not args.no_bg_sub:
        for bg_block in bg_blocks:
            try:
                bg_img, _ = average_block(
                    catalog, bg_block, reduction=args.reduction
                )
            except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
                logging.error(
                    "Background block %d–%d failed: %s",
                    bg_block.start,
                    bg_block.end,
                    exc,
                )
                return 1
            bg_means.append((bg_block, bg_img))
            bg_path = out_dir / (
                f"snake_{day_label}_background_"
                f"{bg_block.start:06d}-{bg_block.end:06d}_mean.fits"
            )
            save_fits(
                bg_path,
                bg_img,
                header_cards={
                    "IMTYPE": (
                        "BGMEAN",
                        "mean of closed-shutter background frames",
                    ),
                    "FRMSTART": (bg_block.start, "First background frame"),
                    "FRMEND": (bg_block.end, "Last background frame"),
                    "NFRAMES": (bg_block.n_frames, "Frames averaged"),
                    "LABEL": (bg_block.label, "Log label"),
                    "SHUTTER": (bg_block.shutter, "Shutter state"),
                },
            )
        logging.info(
            "Loaded %d background mean(s); each snake uses the closest",
            len(bg_means),
        )
    elif args.no_bg_sub:
        logging.info("Skipping background subtraction (--no-bg-sub)")
    else:
        logging.error(
            "No closed-shutter blocks found; positions cube must be "
            "background-subtracted. Check SHnPOS in the FITS headers, "
            "or pass --no-bg-sub for a raw cube."
        )
        return 1

    snake_blocks = [b for b in blocks if b.is_snake]
    if not snake_blocks:
        logging.error("No open-shutter (snake) blocks found")
        return 1

    means: list[np.ndarray] = []
    labels: list[str] = []
    used_bg = False
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
        bg_block: ScanBlock | None = None
        if bg_means:
            bg_block, background = closest_background(block, bg_means)
            product = mean_img - background
            imtype = "SNAKE-BG"
            used_bg = True
            logging.info(
                "pos %02d frames %06d–%06d: subtract bg %06d–%06d",
                index,
                block.start,
                block.end,
                bg_block.start,
                bg_block.end,
            )

        slug = re.sub(r"[^A-Za-z0-9]+", "_", block.label).strip("_") or "snake"
        path = out_dir / (
            f"snake_{day_label}_pos{index:02d}_{slug}_"
            f"{block.start:06d}-{block.end:06d}_mean.fits"
        )
        header_cards = {
            "IMTYPE": (imtype, "mean(snake dwell) [- closest background]"),
            "POSINDEX": (index, "Snake position index (1-based)"),
            "FRMSTART": (block.start, "First dwell frame"),
            "FRMEND": (block.end, "Last dwell frame"),
            "NFRAMES": (block.n_frames, "Frames averaged"),
            "LABEL": (block.label, "Log label"),
            "SHUTTER": (block.shutter, "Shutter state"),
            "BGSUB": (bg_block is not None, "Background subtracted"),
            "COMMENT": (
                f"Frames averaged: {', '.join(f'{n:06d}' for n in frame_ids)}"
            ),
        }
        if bg_block is not None:
            header_cards["BGSTART"] = (
                bg_block.start,
                "Closest background first frame",
            )
            header_cards["BGEND"] = (
                bg_block.end,
                "Closest background last frame",
            )
        save_fits(path, product, header_cards=header_cards)
        means.append(np.asarray(product, dtype=np.float32))
        labels.append(f"pos{index:02d}:{block.start}-{block.end}")

    cube = np.stack(means, axis=0)
    cube_path = out_dir / f"snake_{day_label}_positions_cube.fits"
    if used_bg:
        cube_imtype = "SNAKECUBE-BG"
        cube_comment = (
            "Plane k = bg-sub mean at snake position k (closest background)"
        )
    else:
        cube_imtype = "SNAKECUBE"
        cube_comment = "Plane k = raw mean at snake position k (--no-bg-sub)"
    save_fits(
        cube_path,
        cube,
        header_cards={
            "IMTYPE": (cube_imtype, cube_comment),
            "NPOS": (len(means), "Number of snake positions"),
            "BGSUB": (used_bg, "Each plane is background-subtracted"),
            "COMMENT": "Planes: " + "; ".join(labels),
        },
    )
    logging.info(
        "Snake FOV average done: %d positions → %s (%s)",
        len(means),
        out_dir,
        "bg-subtracted cube" if used_bg else "raw cube",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI surface
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
        logging.error("%s", exc)
        raise SystemExit(1) from exc
