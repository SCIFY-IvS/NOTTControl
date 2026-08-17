"""Take Background must not leave MACIE latched at nseq=1."""

from __future__ import annotations

import unittest

from nottcontrol.camera.macie.macie_interface import (
    override_nseq,
    restore_exposure_settings,
)


class FakeMacie:
    def __init__(self, nseq: int = 8) -> None:
        self.settings = [True, 2, nseq, 4, 1, 0, 1]
        self.writes: list[tuple] = []

    def read_exposure_settings(self):
        return tuple(self.settings)

    def exposure_settings(self, save, ncoadds, nseq, ngroups, nreads, ndrops, nresets):
        written = (save, ncoadds, nseq, ngroups, nreads, ndrops, nresets)
        self.writes.append(written)
        self.settings = list(written)


class OverrideNseqTests(unittest.TestCase):
    def test_override_forces_single_ramp_and_restore_puts_nseq_back(self) -> None:
        macie = FakeMacie(nseq=8)
        saved = override_nseq(macie, 1)
        self.assertEqual(macie.settings[2], 1)
        self.assertEqual(saved[2], 8)
        restore_exposure_settings(macie, saved)
        self.assertEqual(macie.settings[2], 8)
        self.assertEqual(macie.settings[1], 2)

    def test_restore_none_is_a_no_op(self) -> None:
        macie = FakeMacie(nseq=5)
        restore_exposure_settings(macie, None)
        self.assertEqual(macie.settings[2], 5)
        self.assertEqual(macie.writes, [])

    def test_acquire_without_restore_leaves_nseq_latched(self) -> None:
        """Documents the silent 1-of-N Acquire failure if restore is skipped."""
        macie = FakeMacie(nseq=10)
        override_nseq(macie, 1)
        self.assertEqual(int(macie.settings[2]), 1)


if __name__ == "__main__":
    unittest.main()
