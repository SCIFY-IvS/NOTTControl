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
    fits_round,
    header_cards_as_value_dict,
    pressures_for_fits,
    redis_key_for_pressure_tag,
    redis_key_for_temperature_tag,
    update_fits_file_header_cards,
)
from nottcontrol.camera.macie.fits_science import save_science_fits


def _card_map(cards) -> dict[str, tuple[float, str]]:
    return header_cards_as_value_dict(cards)


class FitsHeaderTempTests(unittest.TestCase):
    def test_redis_keys_resolve_for_vote_sensors(self) -> None:
        det = redis_key_for_temperature_tag("t_detector_vote")
        base = redis_key_for_temperature_tag("t_base_plate_vote")
        self.assertIsNotNone(det)
        self.assertIsNotNone(base)
        assert det is not None and base is not None
        self.assertIn("t_detector_vote", det)
        self.assertIn("t_base_plate_vote", base)

    def test_fits_round_two_decimals(self) -> None:
        self.assertEqual(fits_round(80.1234), 80.12)
        self.assertEqual(fits_round(1.2e-6, scientific_if_small=True), 1.2e-6)
        self.assertEqual(fits_round(0.0543, scientific_if_small=True), 0.05)

    def test_cryo_temperatures_from_redis_client(self) -> None:
        det_key = redis_key_for_temperature_tag("t_detector_vote")
        base_key = redis_key_for_temperature_tag("t_base_plate_vote")
        self.assertIsNotNone(det_key)
        self.assertIsNotNone(base_key)

        client = MagicMock()
        client.get_latest.side_effect = lambda key: {
            det_key: 80.123,
            base_key: 85.289,
        }.get(key)

        cards = _card_map(cryo_temperatures_for_fits(client))
        self.assertEqual(cards["DETTEMP"][0], 80.12)
        self.assertEqual(cards["BPTEMP"][0], 85.29)
        self.assertIn("[K]", cards["DETTEMP"][1])
        self.assertIn("[K]", cards["BPTEMP"][1])

    def test_missing_redis_returns_empty(self) -> None:
        self.assertEqual(cryo_temperatures_for_fits(None), [])
        self.assertEqual(delay_line_positions_for_fits(None), [])
        self.assertEqual(pressures_for_fits(None), [])
        self.assertEqual(fits_header_cards_from_redis(None), [])

    def test_delay_line_positions_from_redis(self) -> None:
        client = MagicMock()
        client.get_latest.side_effect = lambda key: {
            "DL_1_pos": 100.456,
            "DL_2_pos": 200.0,
            "DL_3_pos": 300.0,
            "DL_4_pos": 400.0,
        }.get(key)
        cards = _card_map(delay_line_positions_for_fits(client))
        self.assertEqual(cards["DL1POS"][0], 100.46)
        self.assertEqual(cards["DL2POS"][0], 200.0)
        self.assertIn("[um]", cards["DL1POS"][1])

    def test_pressures_from_redis(self) -> None:
        vagc_key = redis_key_for_pressure_tag("VAGC.stat.lrPressure")
        pump_key = redis_key_for_pressure_tag(
            "evac.pump_pvp.stat.PresSens_lrPressure_hPa"
        )
        self.assertIsNotNone(vagc_key)
        self.assertIsNotNone(pump_key)

        client = MagicMock()
        client.get_latest.side_effect = lambda key: {
            vagc_key: 1.234e-6,
            pump_key: 0.0543,
        }.get(key)
        cards = _card_map(pressures_for_fits(client))
        self.assertAlmostEqual(cards["PRESVAGC"][0], 1.2e-6)
        self.assertEqual(cards["PRESPUMP"][0], 0.05)
        self.assertIn("[mbar]", cards["PRESVAGC"][1])
        self.assertIn("[mbar]", cards["PRESPUMP"][1])

    def test_combined_fits_header_cards_are_grouped(self) -> None:
        det_key = redis_key_for_temperature_tag("t_detector_vote")
        vagc_key = redis_key_for_pressure_tag("VAGC.stat.lrPressure")
        client = MagicMock()
        client.get_latest.side_effect = lambda key: {
            det_key: 80.0,
            "DL_1_pos": 12.5,
            vagc_key: 3e-7,
        }.get(key)
        cards = fits_header_cards_from_redis(client)
        comments = [c for c in cards if c[0] == "COMMENT"]
        self.assertTrue(any("Temperatures" in c[2] for c in comments))
        self.assertTrue(any("Pressures" in c[2] for c in comments))
        self.assertTrue(any("Delay line" in c[2] for c in comments))
        # Order: temperatures group before pressures before delay lines
        keywords = [c[0] for c in cards if c[0] != "COMMENT"]
        self.assertLess(keywords.index("DETTEMP"), keywords.index("PRESVAGC"))
        self.assertLess(keywords.index("PRESVAGC"), keywords.index("DL1POS"))

    def test_save_science_fits_writes_grouped_cards(self) -> None:
        image = numpy.zeros((8, 8), dtype=numpy.float32)
        cards = [
            ("COMMENT", None, "----- Temperatures [K] -----"),
            ("DETTEMP", 80.12, "Detector vote temperature [K]"),
            ("COMMENT", None, "----- Pressures [mbar] -----"),
            ("PRESVAGC", 1.2e-6, "VAGC cryostat pressure [mbar]"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frame_science.fits"
            save_science_fits(path, image, reduction="Ramp", extra_cards=cards)
            from astropy.io import fits

            with fits.open(path) as hdul:
                header = hdul[0].header
                self.assertEqual(header["DETMODE"], "Ramp")
                self.assertAlmostEqual(float(header["DETTEMP"]), 80.12)
                self.assertAlmostEqual(float(header["PRESVAGC"]), 1.2e-6)
                comment_text = " ".join(str(c) for c in header["COMMENT"])
                self.assertIn("Temperatures", comment_text)
                self.assertIn("Pressures", comment_text)

    def test_detector_mode_fits_card(self) -> None:
        from nottcontrol.camera.macie.fits_header_meta import detector_mode_fits_card

        key, value, comment = detector_mode_fits_card("CDS")
        self.assertEqual(key, "DETMODE")
        self.assertEqual(value, "CDS")
        self.assertIn("readout mode", comment.lower())

    def test_exposure_fits_cards(self) -> None:
        from nottcontrol.camera.macie.fits_header_meta import exposure_fits_cards

        cards = exposure_fits_cards(
            mode="Ramp",
            tint_ms=1475.28,
            ngroups=2,
            nreads=1,
            ndrops=3,
        )
        by_key = {k: v for k, v, _c in cards}
        self.assertEqual(by_key["DETMODE"], "Ramp")
        self.assertAlmostEqual(by_key["EXPTIME"], 1.47528)
        self.assertEqual(by_key["NGROUPS"], 2)
        self.assertEqual(by_key["NREADS"], 1)
        self.assertEqual(by_key["NDROPS"], 3)

    def test_update_fits_file_header_cards(self) -> None:
        image = numpy.ones((4, 4), dtype=numpy.float32)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ramp.fits"
            save_science_fits(path, image)
            ok = update_fits_file_header_cards(
                path,
                [("DETTEMP", 81.5, "Detector vote temperature [K]")],
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
