"""Tests for the H2RG GUI SaveRstFrames ZMQ path."""

from __future__ import annotations

import unittest

from nottcontrol.camera.macie.macie_interface import (
    MacieInterface,
    override_nseq,
    restore_exposure_settings,
)


class SaveRstFramesTests(unittest.TestCase):
    def test_set_save_rst_frames_sends_zmq(self) -> None:
        iface = MacieInterface.__new__(MacieInterface)
        sent: list[str] = []
        iface._request = lambda message: sent.append(message) or True
        self.assertTrue(iface.set_save_rst_frames(True))
        self.assertTrue(iface.set_save_rst_frames(False))
        self.assertEqual(sent, ["saverst;true", "saverst;false"])

    def test_configure_ramp_exposure_sets_save_rst(self) -> None:
        iface = MacieInterface.__new__(MacieInterface)
        sent: list[str] = []
        iface.read_exposure_timing = lambda: {
            "frametime_s": 0.2,
            "inttime_s": 0.4,
            "ramptime_s": 0.4,
            "execution_s": 1.0,
            "efficiency": 0.4,
        }
        iface.set_exp_mode = lambda mode: sent.append(f"expmode;{mode}") or True
        iface.set_preview_reduction = lambda mode: True
        iface.set_save_rst_frames = (
            lambda save: sent.append(f"saverst;{str(bool(save)).lower()}") or True
        )
        iface.read_exposure_settings = lambda: (True, 1, 1, 2, 1, 0, 1)
        iface.exposure_settings = lambda *args: sent.append("expsettings") or True

        iface.configure_ramp_exposure(400.0, ramp_mode="CDS", save_rst=False)
        self.assertIn("saverst;false", sent)

        sent.clear()
        iface.configure_ramp_exposure(400.0, ramp_mode="CDS", save_rst=True)
        self.assertIn("saverst;true", sent)


class ExposureSettingsRelatchTests(unittest.TestCase):
    """NGroups ReconfigureASIC poisons GigE until cached WinMode is re-sent."""

    def _iface(self) -> tuple[MacieInterface, list[str]]:
        iface = MacieInterface.__new__(MacieInterface)
        sent: list[str] = []
        iface._last_frame_settings = None
        iface._request = lambda message: sent.append(message) or True
        return iface, sent

    def test_exposure_settings_relatches_cached_full_frame(self) -> None:
        iface, sent = self._iface()
        iface.frame_settings(False, False, 0, 2047, 0, 2047)
        sent.clear()
        iface.exposure_settings(True, 1, 8, 2, 1, 0, 1)
        self.assertEqual(
            sent,
            [
                "expsettings;true;1;8;2;1;0;1",
                "framesettings;false;false;0;2047;0;2047",
            ],
        )

    def test_exposure_settings_relatches_cached_stripe(self) -> None:
        iface, sent = self._iface()
        iface.frame_settings(False, True, 0, 2047, 928, 959)
        sent.clear()
        iface.exposure_settings(False, 1, 1, 2, 1, 0, 1)
        self.assertIn("framesettings;false;true;0;2047;928;959", sent)
        self.assertGreater(
            sent.index("framesettings;false;true;0;2047;928;959"),
            sent.index("expsettings;false;1;1;2;1;0;1"),
        )

    def test_exposure_settings_skips_relatch_before_any_frame_settings(self) -> None:
        iface, sent = self._iface()
        iface.exposure_settings(True, 1, 1, 2, 1, 0, 1)
        self.assertEqual(sent, ["expsettings;true;1;1;2;1;0;1"])

    def test_live_nseq_arm_relatches_after_override(self) -> None:
        iface, sent = self._iface()
        iface.read_exposure_settings = lambda: (True, 2, 8, 2, 1, 0, 1)
        iface.frame_settings(False, False, 0, 2047, 0, 2047)
        sent.clear()
        iface._arm_live_single_ramp()
        exp_at = next(i for i, msg in enumerate(sent) if msg.startswith("expsettings;"))
        latch = "framesettings;false;false;0;2047;0;2047"
        self.assertIn(latch, sent)
        self.assertGreater(sent.index(latch), exp_at)
        self.assertTrue(sent[exp_at].startswith("expsettings;false;1;1;"))

    def test_live_restore_relatches_after_nseq_put_back(self) -> None:
        iface, sent = self._iface()
        iface.read_exposure_settings = lambda: (True, 2, 8, 2, 1, 0, 1)
        iface.frame_settings(False, False, 0, 2047, 0, 2047)
        iface._arm_live_single_ramp()
        sent.clear()
        iface._restore_exposure_after_live()
        self.assertEqual(
            sent,
            [
                "expsettings;true;2;8;2;1;0;1",
                "framesettings;false;false;0;2047;0;2047",
            ],
        )

    def test_override_nseq_relatches_so_background_acquire_is_not_65535(self) -> None:
        iface, sent = self._iface()
        iface.read_exposure_settings = lambda: (True, 1, 10, 2, 1, 0, 1)
        iface.frame_settings(False, False, 0, 2047, 0, 2047)
        sent.clear()
        saved = override_nseq(iface, 1)
        self.assertEqual(saved[2], 10)
        self.assertEqual(
            sent,
            [
                "expsettings;true;1;1;2;1;0;1",
                "framesettings;false;false;0;2047;0;2047",
            ],
        )
        sent.clear()
        restore_exposure_settings(iface, saved)
        self.assertEqual(
            sent,
            [
                "expsettings;true;1;10;2;1;0;1",
                "framesettings;false;false;0;2047;0;2047",
            ],
        )


if __name__ == "__main__":
    unittest.main()
