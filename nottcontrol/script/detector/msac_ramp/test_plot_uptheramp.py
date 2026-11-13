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


class MixedScienceShapeTests(unittest.TestCase):
    def test_science_plot_skips_mismatched_winmode_files(self) -> None:
        """Flux plot must not abort when one folder mixes WinMode sizes.

        MACIE dated session folders can hold leftover full-frame (or old
        64×32 photonic) science next to a later 21×21 window. Geometry is
        taken from the last file; earlier mismatched sizes must be skipped
        so first-NDR CDS does not raise.
        """
        import plot_uptheramp as ramp

        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "UTR_mixed_science"
            session.mkdir()
            leftover = np.full((8, 8), 50.0, dtype=np.float32)
            leftover[1:7, 1:7] += 10.0
            _write_fits(session / "ramp_N000001.fits", leftover)
            science = np.full((4, 4), 100.0, dtype=np.float32)
            _write_fits(session / "ramp_N000002.fits", science)
            science2 = science.copy()
            science2[1:3, 1:3] += 40.0
            _write_fits(session / "ramp_N000003.fits", science2)

            rc = ramp.main(
                [
                    "--ramp-dir",
                    str(session),
                    "--no-qa",
                    "--no-cds-cube",
                    "--no-illum-cube",
                    "--no-bg-roi",
                    "--illum-center",
                    "2",
                    "2",
                    "--illum-size",
                    "2",
                ]
            )
            self.assertEqual(rc, 0)
            slug = ramp.session_filename_slug(session)
            flux = session / f"{slug}_msac_uptheramp_illum_vs_file.png"
            self.assertTrue(flux.is_file(), f"missing science flux plot {flux.name}")

    def test_make_cds_plane_rejects_mismatched_pedestal(self) -> None:
        import plot_uptheramp as ramp

        sample = np.ones((4, 4), dtype=np.float32)
        pedestal = np.ones((8, 8), dtype=np.float32)
        with self.assertRaises(ValueError) as ctx:
            ramp.make_cds_plane(
                sample,
                reset_only=False,
                first_abs=pedestal,
                do_ref_correct=False,
            )
        self.assertIn("pedestal shape", str(ctx.exception))

    def test_keep_sample_refs_matching_shape_drops_other_sizes(self) -> None:
        import plot_uptheramp as ramp

        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp)
            _write_fits(session / "a_N000001.fits", np.ones((8, 8), dtype=np.float32))
            _write_fits(session / "b_N000002.fits", np.ones((4, 4), dtype=np.float32))
            _write_fits(session / "c_N000003.fits", np.ones((4, 4), dtype=np.float32))
            refs, _header = ramp.build_sample_refs(
                [
                    session / "a_N000001.fits",
                    session / "b_N000002.fits",
                    session / "c_N000003.fits",
                ],
                preferred_tag="N",
                max_frames=None,
            )
            kept = ramp.keep_sample_refs_matching_shape(refs, (4, 4))
            self.assertEqual([ref.name for ref in kept], ["b_N000002.fits", "c_N000003.fits"])


if __name__ == "__main__":
    unittest.main()
