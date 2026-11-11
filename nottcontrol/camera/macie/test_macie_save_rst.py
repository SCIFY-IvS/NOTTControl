"""Tests for the H2RG GUI SaveRstFrames ZMQ path."""

from __future__ import annotations

import unittest

from nottcontrol.camera.macie.macie_interface import MacieInterface


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


if __name__ == "__main__":
    unittest.main()
