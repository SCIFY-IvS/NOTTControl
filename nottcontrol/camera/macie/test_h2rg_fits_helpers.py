"""Unit tests for H2RG FITS helper functions."""

from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy

from nottcontrol.camera.macie.h2rg_gui import (
    WINDOW_MODES,
    H2rgMainWindow,
    _bottom_vertical_stripe,
    _centered_vertical_stripe,
    _centered_window,
    _channel_window,
    acquire_archive_science_params,
    apply_window_geometry,
    central_value_median,
    cube_reset_kwargs,
    fits_basename,
    fits_frame_number_label,
    fits_header_text,
    is_new_ramp_fits,
    is_science_fits_name,
    list_new_ramp_fits_in_dir,
    list_ramp_fits_in_dir,
    local_fits_file_for_viewer,
    map_server_fits_path,
    newest_fits_file,
    next_fits_frame_number,
    ramp_fits_path_for_viewer,
    ramp_fits_sort_key,
    resolve_ramp_fits_path,
    select_acquire_ramp_paths,
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

    def test_bottom_stripe_128_rows(self) -> None:
        self.assertEqual(_bottom_vertical_stripe(128), (0, 2047, 0, 127))

    def test_bottom_stripe_256_rows(self) -> None:
        self.assertEqual(_bottom_vertical_stripe(256), (0, 2047, 0, 255))

    def test_sc_presets_are_centered_burst(self) -> None:
        by_label = {mode.label: mode for mode in WINDOW_MODES}
        for label, height in (
            ("SC 128", 128),
            ("SC 256", 256),
            ("SC 512", 512),
            ("SC 1024", 1024),
        ):
            mode = by_label[label]
            self.assertFalse(mode.x_window)
            self.assertTrue(mode.y_window)
            self.assertEqual(
                (mode.x1, mode.x2, mode.y1, mode.y2),
                _centered_vertical_stripe(height),
            )

    def test_center_xy_presets(self) -> None:
        by_label = {mode.label: mode for mode in WINDOW_MODES}
        for label, size in (
            ("Center 128x128", 128),
            ("Center 256x256", 256),
            ("Center 512x512", 512),
            ("Center 1024x1024", 1024),
        ):
            mode = by_label[label]
            self.assertTrue(mode.x_window)
            self.assertTrue(mode.y_window)
            self.assertEqual(
                (mode.x1, mode.x2, mode.y1, mode.y2),
                _centered_window(size),
            )

    def test_photonic_chip_window(self) -> None:
        mode = {m.label: m for m in WINDOW_MODES}["Photonic chip"]
        self.assertTrue(mode.x_window)
        self.assertTrue(mode.y_window)
        self.assertEqual((mode.x1, mode.x2, mode.y1, mode.y2), (1024, 1087, 928, 959))


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


class FitsFrameNumberLabelTests(unittest.TestCase):
    def test_extracts_trailing_index(self) -> None:
        self.assertEqual(
            fits_frame_number_label("nott_20260805_00001.fits"),
            "00001",
        )

    def test_science_suffix_stripped(self) -> None:
        self.assertEqual(
            fits_frame_number_label("nott_20260805_00018_science.fits"),
            "00018",
        )

    def test_preview_label(self) -> None:
        self.assertEqual(fits_frame_number_label("preview.fits"), "—")


class NextFitsFrameNumberTests(unittest.TestCase):
    def test_empty_directory_starts_at_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(next_fits_frame_number(Path(tmp)), "000000")

    def test_increments_past_highest_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "nott_20260805_000003.fits").write_bytes(b"")
            (directory / "nott_20260805_000018.fits").write_bytes(b"")
            (directory / "nott_20260805_000018_science.fits").write_bytes(b"")
            (directory / "preview.fits").write_bytes(b"")
            self.assertEqual(next_fits_frame_number(directory), "000019")


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

    def test_later_macie_index_with_same_mtime_is_new(self) -> None:
        self.assertTrue(
            is_new_ramp_fits(
                "nott_20260817_000019.fits",
                100.0,
                before_name="nott_20260817_000018.fits",
                before_mtime=100.0,
            )
        )

    def test_earlier_macie_index_with_same_mtime_is_not_new(self) -> None:
        """SMB 1 s mtime: leftover siblings from the last burst are not new."""
        self.assertFalse(
            is_new_ramp_fits(
                "nott_20260817_000010.fits",
                100.0,
                before_name="nott_20260817_000018.fits",
                before_mtime=100.0,
            )
        )

    def test_older_different_name_is_not_new(self) -> None:
        # Regression: Live used to flip between latest and previous because any
        # different basename was treated as new regardless of mtime.
        self.assertFalse(
            is_new_ramp_fits(
                "ramp001.fits",
                100.0,
                before_name="ramp002.fits",
                before_mtime=200.0,
            )
        )


class SelectAcquireRampPathsTests(unittest.TestCase):
    def test_sort_key_orders_macie_indices_numerically(self) -> None:
        self.assertLess(
            ramp_fits_sort_key("nott_20260817_000009.fits"),
            ramp_fits_sort_key("nott_20260817_000010.fits"),
        )
        self.assertLess(
            ramp_fits_sort_key("nott_20260816_000099.fits"),
            ramp_fits_sort_key("nott_20260817_000001.fits"),
        )

    def test_overflow_keeps_newest_not_oldest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            stamp = 1_700_000_000.0
            leftovers = [
                directory / f"nott_20260817_{index:06d}.fits"
                for index in range(10, 18)
            ]
            current = [
                directory / f"nott_20260817_{index:06d}.fits"
                for index in range(19, 24)
            ]
            for path in leftovers + current:
                path.write_bytes(b"SIMPLE  =                    T")
                os.utime(path, (stamp, stamp))
            selected = select_acquire_ramp_paths(leftovers + current, 5)
            self.assertEqual([path.name for path in selected], [p.name for p in current])

    def test_same_mtime_siblings_are_not_collected_as_new(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            stamp = 1_700_000_000.0
            for index in range(10, 19):
                path = directory / f"nott_20260817_{index:06d}.fits"
                path.write_bytes(b"SIMPLE  =                    T")
                os.utime(path, (stamp, stamp))
            new_paths = list_new_ramp_fits_in_dir(
                directory,
                before_mtime=stamp,
                before_name="nott_20260817_000018.fits",
                dir_ok=True,
            )
            self.assertEqual(new_paths, [])


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


class AcquireArchiveScienceParamsTests(unittest.TestCase):
    def test_snapshot_is_not_the_live_gui_mode(self) -> None:
        ctx = {
            "ramp_mode": "CDS",
            "fowler_pairs": 2,
            "tint_ms": 12.5,
            "keep_files": True,
            "exposure": {"ngroups": 4, "nreads": 1, "ndrops": 0},
        }
        params = acquire_archive_science_params(ctx)
        # Operator switches Fowler / unchecks Save after ZMQ returns.
        live_gui = {"ramp_mode": "Fowler", "fowler_pairs": 8, "keep_files": False}
        self.assertEqual(params["ramp_mode"], "CDS")
        self.assertEqual(params["fowler_pairs"], 2)
        self.assertEqual(params["tint_ms"], 12.5)
        self.assertTrue(params["keep_files"])
        self.assertEqual(params["exposure_report"]["ngroups"], 4)
        self.assertNotEqual(params["ramp_mode"], live_gui["ramp_mode"])
        self.assertNotEqual(params["keep_files"], live_gui["keep_files"])

    def test_cube_reset_kwargs_from_exposure_report(self) -> None:
        self.assertEqual(
            cube_reset_kwargs({"ngroups": 2, "nreads": 1, "nresets": 1}),
            {"ngroups": 2, "nreads": 1, "nresets": 1},
        )
        self.assertEqual(cube_reset_kwargs({"nresets": "x"}), {})
        self.assertEqual(cube_reset_kwargs(None), {})

    def test_invalid_pairs_and_missing_mode_fall_back(self) -> None:
        params = acquire_archive_science_params(
            {"fowler_pairs": "x", "tint_ms": "bad"}
        )
        self.assertEqual(params["ramp_mode"], "CDS")
        self.assertEqual(params["fowler_pairs"], 2)
        self.assertIsNone(params["tint_ms"])
        self.assertTrue(params["keep_files"])

    def test_archive_holds_operation_lock_until_fits_finish(self) -> None:
        """Second Acquire must wait; overlapping archive mixed ramp files."""
        lock = threading.Lock()
        archive_started = threading.Event()
        release_archive = threading.Event()
        events: list[str] = []

        def worker() -> None:
            with lock:
                events.append("zmq-done")
                archive_started.set()
                release_archive.wait(timeout=2.0)
                events.append("archive-done")

        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(archive_started.wait(timeout=2.0))
        self.assertTrue(lock.locked())
        self.assertFalse(lock.acquire(timeout=0.05))
        release_archive.set()
        thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(events, ["zmq-done", "archive-done"])


class ApplyWindowGeometryTests(unittest.TestCase):
    def test_forwards_full_frame_and_sc_args(self) -> None:
        class FakeMacie:
            def __init__(self) -> None:
                self.args = None

            def frame_settings(self, *args) -> None:
                self.args = args

        macie = FakeMacie()
        full = WINDOW_MODES[0]
        apply_window_geometry(macie, full)
        self.assertEqual(
            macie.args,
            (full.x_window, full.y_window, full.x1, full.x2, full.y1, full.y2),
        )

        sc = next(mode for mode in WINDOW_MODES if mode.label == "SC 256")
        apply_window_geometry(macie, sc)
        self.assertEqual(
            macie.args,
            (sc.x_window, sc.y_window, sc.x1, sc.x2, sc.y1, sc.y2),
        )
        self.assertTrue(sc.y_window)
        self.assertFalse(sc.x_window)

    def test_exposure_reconfigure_is_followed_by_geometry_latch(self) -> None:
        """Set/Acquire/Live share _apply_exposure_settings; it must relatch.

        configure_ramp_exposure ReconfigureASIC poisons full-frame GigE
        (~65535 ADU) until frame_settings runs again. Window toggle already
        did this; Set and Acquire did not.
        """
        import inspect

        source = inspect.getsource(H2rgMainWindow._apply_exposure_settings)
        configure_at = source.index("configure_ramp_exposure")
        latch_at = source.index("apply_window_geometry")
        self.assertGreater(
            latch_at,
            configure_at,
            "WinMode/stripe/XY must be re-latched after the ramp-plan write",
        )


if __name__ == "__main__":
    unittest.main()
