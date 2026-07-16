#!/usr/bin/env python3
"""Daily backup of SCIFY infratec camera frames to archive storage.

Frames are stored as PNG files under UTC day folders:

    /frames/YYYYMMDD/HHMMSSmmm.png

This script uses rsync for incremental copies into archive/infratec/.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from nottcontrol import config

DEFAULT_SOURCE = Path("/frames")
DEFAULT_DEST = Path("/archive/infratec")
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"


def resolve_source(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    configured = config.get("DEFAULT", "linux_frame_directory", fallback="")
    if configured:
        configured_path = Path(configured)
        if configured_path.is_dir():
            return configured_path
    return DEFAULT_SOURCE


def utc_day_string(day: str | None) -> str:
    if day is not None:
        datetime.strptime(day, "%Y%m%d")
        return day
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.strftime("%Y%m%d")


def rsync_copy(
    source: Path,
    dest: Path,
    *,
    dry_run: bool,
    delete: bool,
) -> int:
    if not source.exists():
        raise FileNotFoundError(f"Source does not exist: {source}")

    dest.mkdir(parents=True, exist_ok=True)

    cmd = [
        "rsync",
        "-aH",
        "--partial",
        "--human-readable",
        "--info=stats2",
    ]
    if dry_run:
        cmd.append("--dry-run")
    if delete:
        cmd.append("--delete")

    # Trailing slashes: copy contents of source into dest.
    cmd.extend([f"{source}/", f"{dest}/"])

    logging.info("Running: %s", " ".join(cmd))
    return subprocess.call(cmd)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backup infratec /frames PNG data to archive/infratec.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help=f"Frame root directory (default: {DEFAULT_SOURCE} or linux_frame_directory)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"Archive root directory (default: {DEFAULT_DEST})",
    )
    parser.add_argument(
        "--mode",
        choices=("incremental", "day"),
        default="incremental",
        help=(
            "incremental: rsync entire frame tree (default); "
            "day: copy one UTC day folder only"
        ),
    )
    parser.add_argument(
        "--day",
        metavar="YYYYMMDD",
        default=None,
        help="UTC day for --mode day (default: yesterday)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Remove files in dest that no longer exist in source (incremental mode only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without writing",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Optional log file path (default: <dest>/backup.log)",
    )
    return parser.parse_args(argv)


def configure_logging(log_file: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=handlers,
    )


def main(argv: list[str] | None = None) -> int:
    if shutil.which("rsync") is None:
        print("error: rsync not found in PATH", file=sys.stderr)
        return 1

    args = parse_args(argv)
    source_root = resolve_source(args.source)
    dest_root = args.dest
    log_file = args.log_file or (dest_root / "backup.log")
    configure_logging(log_file)

    logging.info("Frame backup start (mode=%s)", args.mode)
    logging.info("Source root: %s", source_root)
    logging.info("Dest root: %s", dest_root)

    try:
        if args.mode == "day":
            day = utc_day_string(args.day)
            source = source_root / day
            dest = dest_root / day
            logging.info("Backing up UTC day %s", day)
            rc = rsync_copy(source, dest, dry_run=args.dry_run, delete=False)
        else:
            rc = rsync_copy(
                source_root,
                dest_root,
                dry_run=args.dry_run,
                delete=args.delete,
            )
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 1

    if rc == 0:
        logging.info("Frame backup completed successfully")
    else:
        logging.error("Frame backup failed with exit code %s", rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
