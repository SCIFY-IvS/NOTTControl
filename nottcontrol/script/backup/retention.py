"""Retention helpers for live camera data trees.

Deletes only under configured *data* roots (e.g. ``/data/nott``,
``/data/bench_data``). Archive trees (``/archive/...``) are never modified.
"""

from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC_DAY_RE = re.compile(r"^\d{8}$")
DEFAULT_RETENTION_DAYS = 7


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc_day_name(name: str) -> datetime | None:
    if not UTC_DAY_RE.match(name):
        return None
    try:
        return datetime.strptime(name, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def cutoff_datetime(retention_days: int, *, now: datetime | None = None) -> datetime:
    if retention_days < 0:
        raise ValueError("retention_days must be >= 0")
    ref = now or utc_now()
    # Keep the last *retention_days* calendar days including today → purge
    # folders/files strictly older than (today - retention_days).
    return (ref - timedelta(days=retention_days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def path_mtime_utc(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _remove_path(path: Path, *, dry_run: bool) -> None:
    if dry_run:
        logging.info("DRY-RUN would remove %s", path)
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)
    logging.info("Removed %s", path)


def purge_utc_day_folders(
    data_root: Path,
    *,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    archive_root: Path | None = None,
    require_archived: bool = True,
    dry_run: bool = False,
    now: datetime | None = None,
) -> int:
    """Remove ``YYYYMMDD`` day folders older than the retention window.

    If *require_archived* and *archive_root* are set, a day folder is only
    removed when ``archive_root / YYYYMMDD`` exists.
    """
    if not data_root.is_dir():
        logging.warning("Retention skip (missing data root): %s", data_root)
        return 0

    cutoff = cutoff_datetime(retention_days, now=now)
    removed = 0

    for child in sorted(data_root.iterdir()):
        day = parse_utc_day_name(child.name)
        if day is None or not child.is_dir():
            continue
        if day >= cutoff:
            continue
        if require_archived:
            if archive_root is None:
                logging.warning(
                    "Skipping %s: require_archived set but no archive_root",
                    child,
                )
                continue
            archived = archive_root / child.name
            if not archived.exists():
                logging.warning(
                    "Skipping %s: not found in archive (%s)",
                    child,
                    archived,
                )
                continue
        _remove_path(child, dry_run=dry_run)
        removed += 1

    logging.info(
        "UTC-day retention on %s: removed %s folder(s) older than %s days "
        "(cutoff %s)",
        data_root,
        removed,
        retention_days,
        cutoff.strftime("%Y%m%d"),
    )
    return removed


def purge_stale_files(
    data_root: Path,
    *,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    archive_root: Path | None = None,
    require_archived: bool = True,
    dry_run: bool = False,
    now: datetime | None = None,
) -> int:
    """Remove files under *data_root* older than the retention window by mtime.

    Intended for nested trees without ``YYYYMMDD`` layout (e.g.
    ``/data/bench_data/H2RG_ASIC``). When *require_archived* is true, the same
    relative path must exist under *archive_root* before a file is deleted.
    Empty directories are pruned afterward.
    """
    if not data_root.is_dir():
        logging.warning("Retention skip (missing data root): %s", data_root)
        return 0

    cutoff = cutoff_datetime(retention_days, now=now)
    removed = 0

    for path in sorted(
        (p for p in data_root.rglob("*") if p.is_file()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        try:
            mtime = path_mtime_utc(path)
        except OSError as exc:
            logging.warning("Skipping %s: %s", path, exc)
            continue
        if mtime >= cutoff:
            continue

        rel = path.relative_to(data_root)
        if require_archived:
            if archive_root is None:
                logging.warning(
                    "Skipping %s: require_archived set but no archive_root",
                    path,
                )
                continue
            archived = archive_root / rel
            if not archived.is_file():
                logging.warning(
                    "Skipping %s: not found in archive (%s)",
                    path,
                    archived,
                )
                continue

        _remove_path(path, dry_run=dry_run)
        removed += 1

    pruned = prune_empty_dirs(data_root, dry_run=dry_run)
    logging.info(
        "File retention on %s: removed %s file(s), pruned %s empty dir(s); "
        "older than %s days (cutoff %s)",
        data_root,
        removed,
        pruned,
        retention_days,
        cutoff.strftime("%Y-%m-%d"),
    )
    return removed


def prune_empty_dirs(root: Path, *, dry_run: bool = False) -> int:
    """Remove empty directories under *root* (bottom-up). Does not remove *root*."""
    if not root.is_dir():
        return 0
    removed = 0
    # Deepest paths first.
    for path in sorted(
        (p for p in root.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        try:
            next(path.iterdir())
            empty = False
        except StopIteration:
            empty = True
        except OSError:
            continue
        if not empty:
            continue
        if dry_run:
            logging.info("DRY-RUN would remove empty dir %s", path)
        else:
            path.rmdir()
            logging.info("Removed empty dir %s", path)
        removed += 1
    return removed
