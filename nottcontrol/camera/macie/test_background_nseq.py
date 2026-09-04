"""Take Background / Live must not leave MACIE latched at nseq=1."""

from __future__ import annotations

import unittest
from threading import Event

from nottcontrol.camera.macie.macie_interface import (
    MacieInterface,
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


class LiveArmNseqTests(unittest.TestCase):
    def _iface(self, nseq: int = 10) -> MacieInterface:
        iface = MacieInterface.__new__(MacieInterface)
        iface._live_restore_exposure = None
        iface._live_first_acquire = True
        iface._live_session_open = False
        iface._acquiring = Event()
        settings = [True, 1, nseq, 2, 1, 0, 1]

        def read():
            return tuple(settings)

        def write(save, ncoadds, nseq_w, ngroups, nreads, ndrops, nresets):
            settings[:] = [save, ncoadds, nseq_w, ngroups, nreads, ndrops, nresets]

        iface.read_exposure_settings = read
        iface.exposure_settings = write
        iface._set_live_session = lambda keep: None
        return iface

    def test_second_live_arm_keeps_original_nseq_to_restore(self) -> None:
        iface = self._iface(10)
        iface._arm_live_single_ramp()
        self.assertEqual(iface._live_restore_exposure[2], 10)
        self.assertEqual(iface.read_exposure_settings()[2], 1)
        iface._arm_live_single_ramp()
        self.assertEqual(iface._live_restore_exposure[2], 10)
        self.assertEqual(iface.read_exposure_settings()[2], 1)
        iface._restore_exposure_after_live()
        self.assertEqual(iface.read_exposure_settings()[2], 10)

    def test_start_continuous_twice_restores_original_nseq(self) -> None:
        iface = self._iface(8)
        iface.start_continuous_acquisition()
        iface.start_continuous_acquisition()
        iface._restore_exposure_after_live()
        self.assertEqual(iface.read_exposure_settings()[2], 8)


if __name__ == "__main__":
    unittest.main()
