"""Tests for truncated-FITS guards used on full-frame SMB loads."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy

from nottcontrol.camera.macie.fits_science import (
    TruncatedFitsError,
    load_fits_data,
    wait_for_file_size_stable,
)


class WaitForFileSizeStableTests(unittest.TestCase):
    def test_stable_file_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ramp.fits"
            path.write_bytes(b"0" * 4000)
            self.assertTrue(
                wait_for_file_size_stable(path, settle_s=0.15, timeout_s=2.0)
            )

    def test_missing_file_times_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.fits"
            self.assertFalse(
                wait_for_file_size_stable(path, settle_s=0.1, timeout_s=0.35)
            )


class LoadFitsDataTruncationTests(unittest.TestCase):
    def test_complete_fits_loads(self) -> None:
        from astropy.io import fits

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ok.fits"
            fits.PrimaryHDU(data=numpy.arange(64, dtype=numpy.uint16).reshape(8, 8)).writeto(
                path
            )
            data, header = load_fits_data(path)
            self.assertEqual(data.shape, (8, 8))
            self.assertEqual(int(header["NAXIS1"]), 8)

    def test_truncated_fits_raises(self) -> None:
        from astropy.io import fits

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trunc.fits"
            # Full-frame-like plane (~8 MB expected once complete).
            fits.PrimaryHDU(
                data=numpy.zeros((256, 256), dtype=numpy.uint16)
            ).writeto(path)
            full_size = path.stat().st_size
            with path.open("r+b") as handle:
                handle.truncate(max(2880, full_size // 3))
            with self.assertRaises(TruncatedFitsError):
                load_fits_data(path)


if __name__ == "__main__":
    unittest.main()
