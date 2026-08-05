"""Unit tests for H2RG FITS helper functions."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy

from nottcontrol.camera.macie.h2rg_gui import (
    _centered_vertical_stripe,
    _channel_window,
    central_value_median,
    fits_basename,
    fits_header_text,
    is_new_ramp_fits,
    is_science_fits_name,
    list_ramp_fits_in_dir,
    local_fits_file_for_viewer,
    map_server_fits_path,
    newest_fits_file,
    ramp_fits_path_for_viewer,
    resolve_ramp_fits_path,
)


class ChannelWindowTests(unittest.TestCase):
    def test_channel_16_window_on_2048_detector(self) -> None:
        self.assertEqual(_channel_window(16), (960, 1023, 0, 2047))

    def test_channel_1_window_starts_at_origin(self) -> None:
        self.assertEqual(_channel_window(1)[:2], (0, 63))


class StripeWindowTests(unittest.TestCase):
    def test_centered_stripe_128_rows(self) -> None:
        self.assertEqual(_centered_vertical_stripe(128), (0, 2047, 960, 1087))

    def test_centered_stripe_256_rows(self) -> None:
        self.assertEqual(_centered_vertical_stripe(256), (0, 2047, 896, 1151))

    def test_centered_stripe_512_rows(self) -> None:
        self.assertEqual(_centered_vertical_stripe(512), (0, 2047, 768, 1279))

    def test_centered_stripe_1024_rows(self) -> None:
        self.assertEqual(_centered_vertical_stripe(1024), (0, 2047, 512, 1535))


class CentralValueTests(unittest.TestCase):
    def test_fits_header_text_from_dict(self) -> None:
        text = fits_header_text({"NAXIS": 2, "BITPIX": 16})
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("NAXIS", text)
        self.assertIn("BITPIX", text)

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


class ViewerFitsPathTests(unittest.TestCase):
    def test_science_path_maps_to_ramp(self) -> None:
        science = Path("/tmp/frame_science.fits")
        self.assertEqual(
            ramp_fits_path_for_viewer(science),
            Path("/tmp/frame.fits"),
        )

    def test_local_file_prefers_existing_ramp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            ramp = directory / "frame.fits"
            science = directory / "frame_science.fits"
            ramp.write_bytes(b"SIMPLE  =                    T")
            science.write_bytes(b"SIMPLE  =                    T")
            resolved = local_fits_file_for_viewer(science)
            self.assertEqual(resolved, ramp)


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

    def test_same_name_newer_mtime_is_new(self) -> None:
        self.assertTrue(
            is_new_ramp_fits(
                "ramp001.fits",
                200.0,
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
    def test_linux_absolute_path_without_mapping_returns_none_on_windows(self) -> None:
        with patch("nottcontrol.camera.macie.h2rg_gui.sys.platform", "win32"):
            with patch("nottcontrol.camera.macie.h2rg_gui.FITS_LINUX_PATH_PREFIX", ""):
                with patch("nottcontrol.camera.macie.h2rg_gui.FITS_WINDOWS_UNC_ROOT", ""):
                    mapped = map_server_fits_path(
                        "/home/labo/test_data/frame.fits",
                    )
        self.assertIsNone(mapped)

    def test_linux_prefix_maps_to_unc_on_windows(self) -> None:
        with patch("nottcontrol.camera.macie.h2rg_gui.sys.platform", "win32"):
            with patch(
                "nottcontrol.camera.macie.h2rg_gui.FITS_LINUX_PATH_PREFIX",
                "/home/labo",
            ):
                with patch(
                    "nottcontrol.camera.macie.h2rg_gui.FITS_WINDOWS_UNC_ROOT",
                    r"\\nott-server.ster.kuleuven.be\labo",
                ):
                    mapped = map_server_fits_path(
                        "/home/labo/test_data/frame.fits",
                    )
        self.assertIsNotNone(mapped)
        assert mapped is not None
        self.assertEqual(
            str(mapped).replace("/", "\\"),
            r"\\nott-server.ster.kuleuven.be\labo\test_data\frame.fits",
        )

    def test_linux_path_unchanged_on_posix(self) -> None:
        mapped = map_server_fits_path("/data/fits/frame.fits")
        self.assertEqual(mapped, Path("/data/fits/frame.fits"))

    def test_linux_does_not_apply_unc_mapping(self) -> None:
        with patch("nottcontrol.camera.macie.h2rg_gui.sys.platform", "linux"):
            with patch(
                "nottcontrol.camera.macie.h2rg_gui.FITS_LINUX_PATH_PREFIX",
                "/data",
            ):
                with patch(
                    "nottcontrol.camera.macie.h2rg_gui.FITS_WINDOWS_UNC_ROOT",
                    r"\\nott-server.ster.kuleuven.be\Data",
                ):
                    mapped = map_server_fits_path("/data/nott/20260805/")
        self.assertEqual(mapped, Path("/data/nott/20260805"))

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

    def test_finds_ramp_in_dated_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            dated = directory / "20260714"
            dated.mkdir()
            ramp = dated / "H2RG_Slow_FullWin_20260714_000003.fits"
            ramp.write_bytes(b"SIMPLE  =                    T")

            paths = list_ramp_fits_in_dir(directory)
            self.assertEqual([path.name for path in paths], [ramp.name])


class ResolveRampFitsPathTests(unittest.TestCase):
    def test_resolves_basename_in_dated_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            dated = directory / "20260714"
            dated.mkdir()
            ramp = dated / "frame.fits"
            ramp.write_bytes(b"SIMPLE  =                    T")

            resolved = resolve_ramp_fits_path(
                Path("frame.fits"),
                search_dirs=[directory],
            )
            self.assertEqual(resolved, ramp)

    def test_returns_none_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resolved = resolve_ramp_fits_path(
                Path("missing.fits"),
                search_dirs=[Path(tmp)],
            )
            self.assertIsNone(resolved)


if __name__ == "__main__":
    unittest.main()
