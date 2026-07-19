"""Unit tests for H2RG FITS header Redis instrument-status cards."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import numpy

from nottcontrol.camera.macie.fits_header_meta import (
    H2RG_FITS_TEMP_FIELDS,
    apply_fits_header_cards,
    cryo_temperatures_for_fits,
    delay_line_positions_for_fits,
    fits_header_cards_from_redis,
    pressures_for_fits,
    redis_key_for_pressure_tag,
    redis_key_for_temperature_tag,
    update_fits_file_header_cards,
)
from nottcontrol.camera.macie.fits_science import save_science_fits


class FitsHeaderTempTests(unittest.TestCase):
    def test_redis_keys_resolve_for_vote_sensors(self) -> None:
        det = redis_key_for_temperature_tag("t_detector_vote")
        base = redis_key_for_temperature_tag("t_base_plate_vote")
        self.assertIsNotNone(det)
        self.assertIsNotNone(base)
        assert det is not None and base is not None
        self.assertIn("t_detector_vote", det)
        self.assertIn("t_base_plate_vote", base)

    def test_cryo_temperatures_from_redis_client(self) -> None:
        det_key = redis_key_for_temperature_tag("t_detector_vote")
        base_key = redis_key_for_temperature_tag("t_base_plate_vote")
        self.assertIsNotNone(det_key)
        self.assertIsNotNone(base_key)

        client = MagicMock()
        client.get_latest.side_effect = lambda key: {
            det_key: 80.1,
            base_key: 85.2,
        }.get(key)

        cards = cryo_temperatures_for_fits(client)
        self.assertEqual(cards["DETTEMP"][0], 80.1)
        self.assertEqual(cards["BPTEMP"][0], 85.2)
        self.assertIn("Detector", cards["DETTEMP"][1])
        self.assertIn("Base plate", cards["BPTEMP"][1])

    def test_missing_redis_returns_empty(self) -> None:
        self.assertEqual(cryo_temperatures_for_fits(None), {})
        self.assertEqual(delay_line_positions_for_fits(None), {})
        self.assertEqual(pressures_for_fits(None), {})
        self.assertEqual(fits_header_cards_from_redis(None), {})

    def test_delay_line_positions_from_redis(self) -> None:
        client = MagicMock()
        client.get_latest.side_effect = lambda key: {
            "DL_1_pos": 100.0,
            "DL_2_pos": 200.0,
            "DL_3_pos": 300.0,
            "DL_4_pos": 400.0,
        }.get(key)
        cards = delay_line_positions_for_fits(client)
        self.assertEqual(cards["DL1POS"][0], 100.0)
        self.assertEqual(cards["DL2POS"][0], 200.0)
        self.assertEqual(cards["DL3POS"][0], 300.0)
        self.assertEqual(cards["DL4POS"][0], 400.0)

    def test_pressures_from_redis(self) -> None:
        vagc_key = redis_key_for_pressure_tag("VAGC.stat.lrPressure")
        pump_key = redis_key_for_pressure_tag(
            "evac.pump_pvp.stat.PresSens_lrPressure_hPa"
        )
        self.assertIsNotNone(vagc_key)
        self.assertIsNotNone(pump_key)

        client = MagicMock()
        client.get_latest.side_effect = lambda key: {
            vagc_key: 1.2e-6,
            pump_key: 0.05,
        }.get(key)
        cards = pressures_for_fits(client)
        self.assertAlmostEqual(cards["PRESVAGC"][0], 1.2e-6)
        self.assertAlmostEqual(cards["PRESPUMP"][0], 0.05)
        self.assertIn("mbar", cards["PRESVAGC"][1])
        self.assertIn("mbar", cards["PRESPUMP"][1])
        self.assertNotIn("hPa", cards["PRESPUMP"][1])

    def test_combined_fits_header_cards(self) -> None:
        det_key = redis_key_for_temperature_tag("t_detector_vote")
        vagc_key = redis_key_for_pressure_tag("VAGC.stat.lrPressure")
        client = MagicMock()
        client.get_latest.side_effect = lambda key: {
            det_key: 80.0,
            "DL_1_pos": 12.5,
            vagc_key: 3e-7,
        }.get(key)
        cards = fits_header_cards_from_redis(client)
        self.assertIn("DETTEMP", cards)
        self.assertIn("DL1POS", cards)
        self.assertIn("PRESVAGC", cards)

    def test_save_science_fits_writes_temp_cards(self) -> None:
        image = numpy.zeros((8, 8), dtype=numpy.float32)
        cards = {
            "DETTEMP": (80.0, "Detector vote temperature from Redis (K)"),
            "BPTEMP": (85.0, "Base plate vote temperature from Redis (K)"),
            "DL1POS": (1234.5, "Delay line 1 position from Redis (um)"),
            "PRESVAGC": (1e-6, "VAGC cryostat pressure from Redis (mbar)"),
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frame_science.fits"
            save_science_fits(path, image, extra_cards=cards)
            from astropy.io import fits

            with fits.open(path) as hdul:
                self.assertAlmostEqual(float(hdul[0].header["DETTEMP"]), 80.0)
                self.assertAlmostEqual(float(hdul[0].header["BPTEMP"]), 85.0)
                self.assertAlmostEqual(float(hdul[0].header["DL1POS"]), 1234.5)
                self.assertAlmostEqual(float(hdul[0].header["PRESVAGC"]), 1e-6)

    def test_update_fits_file_header_cards(self) -> None:
        image = numpy.ones((4, 4), dtype=numpy.float32)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ramp.fits"
            save_science_fits(path, image)
            ok = update_fits_file_header_cards(
                path,
                {"DETTEMP": (81.5, "Detector vote temperature from Redis (K)")},
            )
            self.assertTrue(ok)
            from astropy.io import fits

            with fits.open(path) as hdul:
                self.assertAlmostEqual(float(hdul[0].header["DETTEMP"]), 81.5)

    def test_apply_fits_header_cards_on_mapping(self) -> None:
        header: dict = {}
        apply_fits_header_cards(
            header,
            {H2RG_FITS_TEMP_FIELDS[0][0]: (79.0, H2RG_FITS_TEMP_FIELDS[0][2])},
        )
        self.assertEqual(header["DETTEMP"], (79.0, H2RG_FITS_TEMP_FIELDS[0][2]))


if __name__ == "__main__":
    unittest.main()
