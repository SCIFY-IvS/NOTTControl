#!/usr/bin/env python3
"""Unit tests for live-data retention helpers."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from nottcontrol.script.backup.retention import (
    cutoff_datetime,
    purge_stale_files,
    purge_utc_day_folders,
)


class RetentionTests(unittest.TestCase):
    def test_cutoff_keeps_last_seven_calendar_days(self) -> None:
        now = datetime(2026, 9, 19, 15, 0, tzinfo=timezone.utc)
        cutoff = cutoff_datetime(7, now=now)
        self.assertEqual(cutoff.strftime("%Y%m%d"), "20260912")

    def test_purge_utc_day_folders_requires_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            archive = root / "archive"
            data.mkdir()
            archive.mkdir()
            (data / "20260901").mkdir()
            (data / "20260901" / "a.fits").write_text("x", encoding="utf-8")
            (data / "20260918").mkdir()
            (data / "20260918" / "b.fits").write_text("y", encoding="utf-8")
            # Old day not yet in archive → must be kept.
            now = datetime(2026, 9, 19, tzinfo=timezone.utc)
            removed = purge_utc_day_folders(
                data,
                retention_days=7,
                archive_root=archive,
                require_archived=True,
                dry_run=False,
                now=now,
            )
            self.assertEqual(removed, 0)
            self.assertTrue((data / "20260901").is_dir())

            (archive / "20260901").mkdir()
            removed = purge_utc_day_folders(
                data,
                retention_days=7,
                archive_root=archive,
                require_archived=True,
                dry_run=False,
                now=now,
            )
            self.assertEqual(removed, 1)
            self.assertFalse((data / "20260901").exists())
            self.assertTrue((data / "20260918").is_dir())

    def test_purge_stale_files_by_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "bench"
            archive = root / "archive_bench"
            old_rel = Path("H2RG_ASIC") / "old.fits"
            new_rel = Path("H2RG_ASIC") / "new.fits"
            for base in (data, archive):
                (base / "H2RG_ASIC").mkdir(parents=True)
                (base / old_rel).write_text("old", encoding="utf-8")
                (base / new_rel).write_text("new", encoding="utf-8")

            import os

            old_ts = datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()
            new_ts = datetime(2026, 9, 18, tzinfo=timezone.utc).timestamp()
            os.utime(data / old_rel, (old_ts, old_ts))
            os.utime(data / new_rel, (new_ts, new_ts))
            os.utime(archive / old_rel, (old_ts, old_ts))
            os.utime(archive / new_rel, (new_ts, new_ts))

            now = datetime(2026, 9, 19, tzinfo=timezone.utc)
            removed = purge_stale_files(
                data,
                retention_days=7,
                archive_root=archive,
                require_archived=True,
                dry_run=False,
                now=now,
            )
            self.assertEqual(removed, 1)
            self.assertFalse((data / old_rel).exists())
            self.assertTrue((data / new_rel).exists())
            self.assertTrue((archive / old_rel).exists())


if __name__ == "__main__":
    unittest.main()
