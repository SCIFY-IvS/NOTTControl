"""Tests for MSAC UpTheRamp plotting helpers."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))


def _write_fits(path: Path, data: np.ndarray) -> None:
    from astropy.io import fits

    path.parent.mkdir(parents=True, exist_ok=True)
    fits.PrimaryHDU(data=np.asarray(data, dtype=np.float32)).writeto(
        path, overwrite=True
    )


class MismatchedResetShapeTests(unittest.TestCase):
    def test_science_plot_survives_windowed_reset_next_to_larger_science(self) -> None:
        """Science flux plot must not abort when _R FITS are a different size.

        After treating destructive MSAC resets as QA-only, a leftover
        ``raise`` still halted the whole session if a windowed ``_R`` sat
        next to larger science ramps (or the reverse). Cron then never
        wrote the flux PNG.
        """
        import plot_uptheramp as ramp

        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "UTR_mixed_reset"
            session.mkdir()
            science = np.full((8, 8), 100.0, dtype=np.float32)
            _write_fits(session / "ramp_N000001.fits", science)
            science2 = science.copy()
            science2[2:6, 2:6] += 40.0
            _write_fits(session / "ramp_N000002.fits", science2)
            reset = np.full((4, 4), 80.0, dtype=np.float32)
            _write_fits(session / "ramp_R0001.fits", reset)
            _write_fits(session / "ramp_R0002.fits", reset + 3.0)

            rc = ramp.main(
                [
                    "--ramp-dir",
                    str(session),
                    "--no-qa",
                    "--no-cds-cube",
                    "--no-illum-cube",
                    "--no-bg-roi",
                    "--illum-center",
                    "4",
                    "4",
                    "--illum-size",
                    "4",
                ]
            )
            self.assertEqual(rc, 0)
            slug = ramp.session_filename_slug(session)
            flux = session / f"{slug}_msac_uptheramp_illum_vs_file.png"
            reset_plot = session / f"{slug}_msac_reset_illum_vs_R.png"
            self.assertTrue(flux.is_file(), f"missing science flux plot {flux.name}")
            self.assertTrue(
                reset_plot.is_file(), f"missing reset-vs-R plot {reset_plot.name}"
            )


if __name__ == "__main__":
    unittest.main()
