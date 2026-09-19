#!/usr/bin/env python3
"""Daily backup of H2RG live data to archive, then 1-week retention on /data.

Live trees (copied, then pruned):

    /data/nott          → /archive/nott          (H2RG GUI / zmq FITS)
    /data/bench_data    → /archive/bench_data    (MSAC / H2RG_ASIC, …)

``/archive/*`` is permanent: this script never deletes under archive.
After a successful rsync, live data older than ``--retention-days`` (default 7)
is removed from ``/data/nott`` and ``/data/bench_data`` only when the same
paths already exist in the matching archive tree.
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
from nottcontrol.script.backup.retention import (
    DEFAULT_RETENTION_DAYS,
    purge_stale_files,
    purge_utc_day_folders,
)

H2RG_SECTION = "H2RG DETECTOR"

DEFAULT_SOURCE = Path("/data/nott")
DEFAULT_DEST = Path("/archive/nott")
DEFAULT_BENCH_SOURCE = Path("/data/bench_data")
DEFAULT_BENCH_DEST = Path("/archive/bench_data")
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"


def resolve_source(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    configured = config.get(H2RG_SECTION, "linux_fits_directory", fallback="")
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
        description=(
            "Backup /data/nott and /data/bench_data to /archive/*, then apply "
            "1-week retention on the live /data trees only."
        ),
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help=f"GUI FITS root (default: {DEFAULT_SOURCE} or linux_fits_directory)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"GUI FITS archive root (default: {DEFAULT_DEST})",
    )
    parser.add_argument(
        "--bench-source",
        type=Path,
        default=DEFAULT_BENCH_SOURCE,
        help=f"Bench / MSAC data root (default: {DEFAULT_BENCH_SOURCE})",
    )
    parser.add_argument(
        "--bench-dest",
        type=Path,
        default=DEFAULT_BENCH_DEST,
        help=f"Bench archive root (default: {DEFAULT_BENCH_DEST})",
    )
    parser.add_argument(
        "--mode",
        choices=("incremental", "day"),
        default="incremental",
        help=(
            "incremental: rsync entire trees (default); "
            "day: copy one UTC day folder under /data/nott only "
            "(bench still full incremental unless --skip-bench)"
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
        help=(
            "rsync --delete on archive trees only: remove files in dest that "
            "no longer exist in source (never deletes under /data)"
        ),
    )
    parser.add_argument(
        "--skip-bench",
        action="store_true",
        help="Do not backup or purge /data/bench_data",
    )
    parser.add_argument(
        "--skip-nott",
        action="store_true",
        help="Do not backup or purge /data/nott",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=(
            f"Remove live /data entries older than this many days after a "
            f"successful archive copy (default: {DEFAULT_RETENTION_DAYS}). "
            f"Use 0 to disable purge."
        ),
    )
    parser.add_argument(
        "--no-purge",
        action="store_true",
        help="Backup only; do not apply retention on /data",
    )
    parser.add_argument(
        "--purge-only",
        action="store_true",
        help="Skip rsync; only run retention on /data (still requires archive)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied/removed without writing",
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
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except OSError as exc:
            print(
                f"warning: cannot write log file {log_file}: {exc}",
                file=sys.stderr,
            )

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=handlers,
    )


def apply_retention(
    *,
    nott_source: Path,
    nott_dest: Path,
    bench_source: Path,
    bench_dest: Path,
    retention_days: int,
    skip_nott: bool,
    skip_bench: bool,
    dry_run: bool,
) -> None:
    if retention_days <= 0:
        logging.info("Retention disabled (retention_days=%s)", retention_days)
        return

    logging.info(
        "Applying %s-day retention on live /data (archive is never purged)",
        retention_days,
    )
    if not skip_nott:
        purge_utc_day_folders(
            nott_source,
            retention_days=retention_days,
            archive_root=nott_dest,
            require_archived=True,
            dry_run=dry_run,
        )
    if not skip_bench:
        purge_stale_files(
            bench_source,
            retention_days=retention_days,
            archive_root=bench_dest,
            require_archived=True,
            dry_run=dry_run,
        )


def main(argv: list[str] | None = None) -> int:
    if shutil.which("rsync") is None:
        print("error: rsync not found in PATH", file=sys.stderr)
        return 1

    args = parse_args(argv)
    if args.skip_nott and args.skip_bench:
        print("error: nothing to do (--skip-nott and --skip-bench)", file=sys.stderr)
        return 1

    source_root = resolve_source(args.source)
    dest_root = args.dest
    bench_source = args.bench_source
    bench_dest = args.bench_dest
    log_file = args.log_file or (dest_root / "backup.log")
    configure_logging(log_file)

    logging.info("H2RG / bench backup start (mode=%s)", args.mode)
    logging.info("Nott source: %s → %s", source_root, dest_root)
    logging.info("Bench source: %s → %s", bench_source, bench_dest)

    if args.purge_only:
        apply_retention(
            nott_source=source_root,
            nott_dest=dest_root,
            bench_source=bench_source,
            bench_dest=bench_dest,
            retention_days=0 if args.no_purge else args.retention_days,
            skip_nott=args.skip_nott,
            skip_bench=args.skip_bench,
            dry_run=args.dry_run,
        )
        logging.info("Purge-only completed")
        return 0

    rc = 0
    try:
        if not args.skip_nott:
            if args.mode == "day":
                day = utc_day_string(args.day)
                source = source_root / day
                dest = dest_root / day
                logging.info("Backing up UTC day %s from %s", day, source_root)
                rc = rsync_copy(source, dest, dry_run=args.dry_run, delete=False)
            else:
                rc = rsync_copy(
                    source_root,
                    dest_root,
                    dry_run=args.dry_run,
                    delete=args.delete,
                )
            if rc != 0:
                logging.error("Nott backup failed with exit code %s", rc)
                return rc

        if not args.skip_bench:
            if not bench_source.exists():
                logging.warning(
                    "Bench source missing (%s); skipping bench backup/purge",
                    bench_source,
                )
            else:
                bench_rc = rsync_copy(
                    bench_source,
                    bench_dest,
                    dry_run=args.dry_run,
                    delete=args.delete if args.mode == "incremental" else False,
                )
                if bench_rc != 0:
                    logging.error("Bench backup failed with exit code %s", bench_rc)
                    return bench_rc
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 1

    if not args.no_purge and not args.dry_run:
        apply_retention(
            nott_source=source_root,
            nott_dest=dest_root,
            bench_source=bench_source,
            bench_dest=bench_dest,
            retention_days=args.retention_days,
            skip_nott=args.skip_nott,
            skip_bench=args.skip_bench or not bench_source.exists(),
            dry_run=False,
        )
    elif args.dry_run and not args.no_purge:
        apply_retention(
            nott_source=source_root,
            nott_dest=dest_root,
            bench_source=bench_source,
            bench_dest=bench_dest,
            retention_days=args.retention_days,
            skip_nott=args.skip_nott,
            skip_bench=args.skip_bench or not bench_source.exists(),
            dry_run=True,
        )

    logging.info("Backup completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
