"""Unit tests for H2RG ROI Redis keys and brightness helpers."""

from __future__ import annotations

import unittest

import numpy

from nottcontrol.camera.macie.h2rg_roi_panel import (
    compute_roi_brightness,
    redis_key_for_roi,
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


if __name__ == "__main__":
    unittest.main()
