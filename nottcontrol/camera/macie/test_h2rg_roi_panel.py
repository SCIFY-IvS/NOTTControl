"""Unit tests for H2RG ROI Redis keys and brightness helpers."""

from __future__ import annotations

import unittest

import numpy
from collections import deque

from nottcontrol.camera.macie.h2rg_gui import (
    WINDOW_MODES,
    display_window_origin,
    soft_sc_delivered_height,
    soft_sc_top_pad,
    window_origin_for_frame,
)
from nottcontrol.camera.macie.h2rg_roi_panel import (
    compute_local_roi_brightness,
    compute_roi_brightness,
    map_roi_full_to_image,
    map_roi_image_to_full,
    pop_roi_to_image,
    redis_key_for_roi,
    remap_rois_to_image,
    roi_profile_1d,
)


class RedisKeyTests(unittest.TestCase):
    def test_prefix_is_distinct_from_infratec(self) -> None:
        self.assertEqual(redis_key_for_roi(1), "h2rg_roi1")
        self.assertEqual(redis_key_for_roi(10), "h2rg_roi10")
        self.assertFalse(redis_key_for_roi(1).startswith("roi1"))


class BrightnessTests(unittest.TestCase):
    def test_compute_roi_brightness(self) -> None:
        frame = numpy.arange(100, dtype=numpy.float64).reshape(10, 10)
        results, regions = compute_roi_brightness(frame, {1: (2, 2, 3, 3)})
        self.assertIn(1, results)
        expected = frame[2:5, 2:5]
        self.assertAlmostEqual(results[1].avg, float(expected.mean()))
        self.assertAlmostEqual(results[1].max, float(expected.max()))
        self.assertAlmostEqual(results[1].min, float(expected.min()))
        numpy.testing.assert_array_equal(regions[1], expected)

    def test_profile_collapses_narrow_axis(self) -> None:
        region = numpy.arange(12, dtype=numpy.float64).reshape(4, 3)
        profile = roi_profile_1d(region)
        self.assertEqual(profile.shape, (4,))
        numpy.testing.assert_allclose(profile, region.mean(axis=1))

    def test_profile_min_max_statistics(self) -> None:
        region = numpy.array(
            [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0], [10.0, 11.0, 12.0]],
            dtype=numpy.float64,
        )
        numpy.testing.assert_allclose(
            roi_profile_1d(region, statistic="min"), region.min(axis=1)
        )
        numpy.testing.assert_allclose(
            roi_profile_1d(region, statistic="max"), region.max(axis=1)
        )

    def test_subframe_brightness_uses_window_origin(self) -> None:
        # Full-frame ROI at detector (10, 800); SC stripe starts at y=768.
        frame = numpy.zeros((512, 2048), dtype=numpy.float64)
        frame[800 - 768, 10] = 42.0
        results, _regions = compute_roi_brightness(
            frame,
            {1: (10, 800, 1, 1)},
            origin_x=0,
            origin_y=768,
            pad_top=0,
        )
        self.assertIn(1, results)
        self.assertAlmostEqual(results[1].avg, 42.0)

    def test_roi_outside_subframe_cleared(self) -> None:
        frame = numpy.ones((512, 2048), dtype=numpy.float64)
        results, regions = compute_roi_brightness(
            frame,
            {1: (10, 100, 4, 4)},  # detector y=100 is above SC512 stripe
            origin_x=0,
            origin_y=768,
            pad_top=0,
            window_x1=0,
            window_x2=2047,
            window_y1=768,
            window_y2=1279,
        )
        self.assertNotIn(1, results)
        self.assertNotIn(1, regions)

    def test_origin_zero_still_gated_by_science_window(self) -> None:
        # Old bug: origin left at 0 on an SC frame still sampled y=105.
        frame = numpy.full((512, 2048), 99.0, dtype=numpy.float64)
        results, _regions = compute_roi_brightness(
            frame,
            {1: (333, 105, 4, 105)},
            origin_x=0,
            origin_y=0,
            pad_top=0,
            window_x1=0,
            window_x2=2047,
            window_y1=768,
            window_y2=1279,
        )
        self.assertNotIn(1, results)

    def test_full_frame_buffer_ignores_sc_combo(self) -> None:
        mode = next(m for m in WINDOW_MODES if m.label == "SC 512")
        frame = numpy.zeros((2048, 2048), dtype=numpy.float64)
        frame[105, 333] = 7.0
        ox, oy, pad = window_origin_for_frame(frame.shape, mode, candidates=WINDOW_MODES)
        self.assertEqual((ox, oy, pad), (0, 0, 0))
        results, _regions = compute_roi_brightness(
            frame,
            {1: (333, 105, 1, 1)},
            origin_x=ox,
            origin_y=oy,
            pad_top=pad,
        )
        self.assertAlmostEqual(results[1].avg, 7.0)

    def test_sc512_frame_infers_origin(self) -> None:
        mode = next(m for m in WINDOW_MODES if m.label == "SC 512")
        ox, oy, pad = window_origin_for_frame(
            (512, 2048), mode, candidates=WINDOW_MODES
        )
        self.assertEqual((ox, oy, pad), (0, 768, 0))

    def test_sc512_delivered_height_is_ny(self) -> None:
        mode = next(m for m in WINDOW_MODES if m.label == "SC 512")
        self.assertEqual(soft_sc_delivered_height(mode), 512)
        ox, oy, pad = window_origin_for_frame(
            (512, 2048), mode, candidates=WINDOW_MODES
        )
        self.assertEqual((ox, oy, pad), (0, 768, 0))


class RemapTests(unittest.TestCase):
    def test_sc512_no_pad(self) -> None:
        mode = next(m for m in WINDOW_MODES if m.label == "SC 512")
        self.assertEqual(soft_sc_top_pad(mode), 0)
        ox, oy, pad = display_window_origin(mode)
        self.assertEqual((ox, oy, pad), (0, 768, 0))

    def test_full_frame_no_pad(self) -> None:
        mode = WINDOW_MODES[0]
        self.assertEqual(soft_sc_top_pad(mode), 0)
        self.assertEqual(display_window_origin(mode), (0, 0, 0))

    def test_map_roundtrip(self) -> None:
        local = map_roi_full_to_image(
            (333, 800, 4, 10),
            origin_x=0,
            origin_y=768,
            image_w=2048,
            image_h=512,
            pad_top=0,
        )
        self.assertEqual(local, (333, 32, 4, 10))
        full = map_roi_image_to_full(
            local, origin_x=0, origin_y=768, pad_top=0
        )
        self.assertEqual(full, (333, 800, 4, 10))

    def test_remap_drops_non_overlapping(self) -> None:
        mapped = remap_rois_to_image(
            {1: (10, 100, 4, 4), 2: (10, 900, 4, 4)},
            origin_x=0,
            origin_y=768,
            image_w=2048,
            image_h=512,
            pad_top=0,
        )
        self.assertNotIn(1, mapped)
        self.assertIn(2, mapped)

    def test_pop_roi_to_image_centers_in_subframe(self) -> None:
        local = pop_roi_to_image((333, 105, 40, 30), image_w=512, image_h=256)
        self.assertEqual(local, (236, 113, 40, 30))

    def test_pop_roundtrip_updates_full_frame(self) -> None:
        popped = pop_roi_to_image((10, 100, 4, 4), image_w=512, image_h=256)
        full = map_roi_image_to_full(
            popped, origin_x=1024, origin_y=512, pad_top=0
        )
        self.assertEqual(full, (1278, 638, 4, 4))

    def test_gap_sample_is_non_finite(self) -> None:
        from nottcontrol.camera.macie.h2rg_roi_panel import H2rgRoiRow

        row = H2rgRoiRow.__new__(H2rgRoiRow)
        row.min_values = deque(maxlen=10)
        row.max_values = deque(maxlen=10)
        row.avg_values = deque(maxlen=10)
        H2rgRoiRow.add_gap_sample(row)
        self.assertEqual(len(row.avg_values), 1)
        self.assertFalse(numpy.isfinite(row.avg_values[0]))


if __name__ == "__main__":
    unittest.main()
