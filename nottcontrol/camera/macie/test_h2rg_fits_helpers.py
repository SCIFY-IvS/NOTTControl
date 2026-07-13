"""Unit tests for H2RG FITS helper functions."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

import numpy

from nottcontrol.camera.macie.h2rg_gui import (
    _centered_vertical_stripe,
    _channel_window,
    central_value_median,
    fits_basename,
    is_new_ramp_fits,
    is_science_fits_name,
    map_server_fits_path,
    newest_fits_file,
)


class ChannelWindowTests(unittest.TestCase):
    def test_channel_16_window_on_2048_detector(self) -> None:
        self.assertEqual(_channel_window(16), (960, 1023, 0, 2047))

    def test_channel_1_window_starts_at_origin(self) -> None:
        self.assertEqual(_channel_window(1)[:2], (0, 63))


class StripeWindowTests(unittest.TestCase):
    def test_centered_stripe_512_rows(self) -> None:
        self.assertEqual(_centered_vertical_stripe(512), (0, 2047, 768, 1279))

    def test_centered_stripe_1024_rows(self) -> None:
        self.assertEqual(_centered_vertical_stripe(1024), (0, 2047, 512, 1535))


class CentralValueTests(unittest.TestCase):
    def test_median_of_inner_region(self) -> None:
        frame = numpy.arange(100, dtype=numpy.float32).reshape(10, 10)
        value = central_value_median(frame)
        self.assertIsNotNone(value)
        inner_span = int(numpy.sqrt(0.5) * 10)
        y0 = (10 - inner_span) // 2
        x0 = (10 - inner_span) // 2
        expected = float(
            numpy.median(frame[y0 : y0 + inner_span, x0 : x0 + inner_span])
        )
        self.assertEqual(value, expected)

    def test_empty_frame_returns_none(self) -> None:
        self.assertIsNone(central_value_median(numpy.empty((0, 0))))


class ScienceFitsNameTests(unittest.TestCase):
    def test_science_suffix_is_recognized(self) -> None:
        self.assertTrue(is_science_fits_name("frame_001_science.fits"))
        self.assertTrue(is_science_fits_name("FRAME_SCIENCE.FITS"))

    def test_ramp_names_are_not_science(self) -> None:
        self.assertFalse(is_science_fits_name("frame_001.fits"))
        self.assertFalse(is_science_fits_name("ramp.fits"))


class NewRampFitsTests(unittest.TestCase):
    def test_newer_mtime_is_new(self) -> None:
        self.assertTrue(
            is_new_ramp_fits(
                "ramp002.fits",
                200.0,
                before_name="ramp001.fits",
                before_mtime=100.0,
            )
        )

    def test_same_name_and_mtime_is_not_new(self) -> None:
        self.assertFalse(
            is_new_ramp_fits(
                "ramp001.fits",
                100.0,
                before_name="ramp001.fits",
                before_mtime=100.0,
            )
        )

    def test_science_file_is_never_new(self) -> None:
        self.assertFalse(
            is_new_ramp_fits(
                "ramp001_science.fits",
                200.0,
                before_name="ramp001.fits",
                before_mtime=100.0,
            )
        )

    def test_different_name_with_same_mtime_is_new(self) -> None:
        self.assertTrue(
            is_new_ramp_fits(
                "ramp002.fits",
                100.0,
                before_name="ramp001.fits",
                before_mtime=100.0,
            )
        )


class MapServerFitsPathTests(unittest.TestCase):
    def test_linux_prefix_maps_to_unc_on_windows(self) -> None:
        mapped = map_server_fits_path(
            "/data/fits/frame.fits",
            zmq_address="tcp://camera-host:65534",
        )
        self.assertEqual(mapped, Path("/data/fits/frame.fits"))

    def test_basename_helper(self) -> None:
        self.assertEqual(fits_basename("/tmp/a/b.fits"), "b.fits")
        self.assertIsNone(fits_basename(None))


class NewestFitsFileTests(unittest.TestCase):
    def test_excludes_science_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            ramp_old = directory / "old.fits"
            ramp_new = directory / "new.fits"
            science = directory / "new_science.fits"
            ramp_old.write_bytes(b"SIMPLE  =                    T")
            time.sleep(0.01)
            ramp_new.write_bytes(b"SIMPLE  =                    T")
            science.write_bytes(b"SIMPLE  =                    T")

            newest = newest_fits_file(directory)
            self.assertIsNotNone(newest)
            assert newest is not None
            self.assertEqual(newest.name, "new.fits")

    def test_dir_not_ok_returns_none(self) -> None:
        self.assertIsNone(newest_fits_file(Path("/nonexistent"), dir_ok=False))


if __name__ == "__main__":
    unittest.main()
