"""Tests for ramp timing plans and Fowler/CDS reduction."""

from __future__ import annotations

import unittest

import numpy

from nottcontrol.camera.macie.fits_science import (
    cds_science_image,
    fowler_science_image,
    ramp_science_image,
    raw_science_image,
    science_image_from_cube,
)
from nottcontrol.camera.macie.ramp_plan import (
    calc_ramp_plan,
    exp_mode_for_ramp,
    fits_wait_timeout_s,
)


class CalcRampPlanTests(unittest.TestCase):
    def test_cds_short_integration_single_read(self) -> None:
        plan = calc_ramp_plan(50.0, 200.0, mode="CDS")
        self.assertEqual(plan["ngroups"], 1)
        self.assertEqual(plan["nreads"], 1)
        self.assertEqual(plan["ndrops"], 0)

    def test_cds_long_integration_two_groups(self) -> None:
        plan = calc_ramp_plan(500.0, 200.0, mode="CDS")
        self.assertEqual(plan["ngroups"], 2)
        self.assertEqual(plan["nreads"], 1)
        self.assertEqual(plan["ndrops"], 1)

    def test_single_frame_one_read_no_drops(self) -> None:
        plan = calc_ramp_plan(500.0, 200.0, mode="SingleFrame")
        self.assertEqual(plan["ngroups"], 1)
        self.assertEqual(plan["nreads"], 1)
        self.assertEqual(plan["ndrops"], 0)

    def test_ramp_long_integration_uses_group_drops(self) -> None:
        # 600 ms → nearest 3×200; two groups with one drop between.
        plan = calc_ramp_plan(600.0, 200.0, mode="Ramp")
        self.assertEqual(plan["ngroups"], 2)
        self.assertEqual(plan["nreads"], 1)
        self.assertEqual(plan["ndrops"], 1)
        self.assertEqual(plan["tint_ms"], 600.0)

    def test_ramp_rounds_to_nearest_frame_multiple(self) -> None:
        # 500 ms with 200 ms frames → round to 2×200 (not ceil to 3).
        plan = calc_ramp_plan(500.0, 200.0, mode="Ramp")
        self.assertEqual(plan["ngroups"], 2)
        self.assertEqual(plan["nreads"], 1)
        self.assertEqual(plan["ndrops"], 0)
        self.assertEqual(plan["tint_ms"], 400.0)

    def test_ramp_short_integration_single_read(self) -> None:
        # 50 ms → rounds to 1×200 ms single read (full frame).
        plan = calc_ramp_plan(50.0, 200.0, mode="Ramp")
        self.assertEqual(plan["ngroups"], 1)
        self.assertEqual(plan["nreads"], 1)
        self.assertEqual(plan["ndrops"], 0)
        self.assertEqual(plan["tint_ms"], 200.0)

    def test_ramp_windowed_min_two_samples_via_groups(self) -> None:
        # WinMode: never a lone read — Jarron 2×1 with no drops (min CDS pair).
        plan = calc_ramp_plan(50.0, 200.0, mode="Ramp", windowed_cds=True)
        self.assertEqual(plan["ngroups"], 2)
        self.assertEqual(plan["nreads"], 1)
        self.assertEqual(plan["ndrops"], 0)
        self.assertEqual(plan["tint_ms"], 400.0)

    def test_ramp_windowed_long_dit_uses_drops(self) -> None:
        # 5 s with 374 ms frames → round to 13 frames: 2 groups, 11 drops.
        plan = calc_ramp_plan(5000.0, 374.0, mode="Ramp", windowed_cds=True)
        self.assertEqual(plan["ngroups"], 2)
        self.assertEqual(plan["nreads"], 1)
        self.assertEqual(plan["ndrops"], 11)
        self.assertAlmostEqual(plan["tint_ms"], 13 * 374.0)

    def test_cds_windowed_long_dit_uses_drops(self) -> None:
        # Jarron-style: nreads stays 1; DIT stretched with ndrops.
        plan = calc_ramp_plan(5000.0, 374.0, mode="CDS", windowed_cds=True)
        self.assertEqual(plan["ngroups"], 2)
        self.assertEqual(plan["nreads"], 1)
        self.assertEqual(plan["ndrops"], 12)  # ceil(5000/374)=14 → 14-2
        self.assertAlmostEqual(plan["tint_ms"], 14 * 374.0)

    def test_cds_windowed_short_dit_still_two_samples(self) -> None:
        # Must not fall through to the full-frame 1-read short-DIT shortcut.
        plan = calc_ramp_plan(50.0, 200.0, mode="CDS", windowed_cds=True)
        self.assertEqual(plan["ngroups"], 2)
        self.assertEqual(plan["nreads"], 1)
        self.assertEqual(plan["ndrops"], 0)
        self.assertEqual(plan["tint_ms"], 400.0)

    def test_single_frame_windowed_promoted_to_two_group_cds(self) -> None:
        plan = calc_ramp_plan(500.0, 200.0, mode="SingleFrame", windowed_cds=True)
        self.assertEqual(plan["ngroups"], 2)
        self.assertEqual(plan["nreads"], 1)
        self.assertEqual(plan["ndrops"], 0)

    def test_fowler_uses_single_group_and_even_reads(self) -> None:
        plan = calc_ramp_plan(180.0, 100.0, mode="Fowler", fowler_pairs=2)
        self.assertEqual(plan["ngroups"], 1)
        self.assertEqual(plan["nreads"], 4)
        self.assertEqual(plan["fowler_pairs"], 2)

    def test_exp_mode_values(self) -> None:
        self.assertEqual(exp_mode_for_ramp("SingleFrame"), 0)
        self.assertEqual(exp_mode_for_ramp("Ramp"), 0)
        self.assertEqual(exp_mode_for_ramp("CDS"), 0)
        self.assertEqual(exp_mode_for_ramp("Fowler"), 1)

    def test_fits_wait_timeout_scales_with_sequence(self) -> None:
        timeout = fits_wait_timeout_s(12.0, ncoadds=2, nseq=5, margin_s=10.0)
        self.assertEqual(timeout, 130.0)


class RampReductionTests(unittest.TestCase):
    def test_cds_last_minus_first(self) -> None:
        cube = numpy.array(
            [[[10.0, 20.0], [30.0, 40.0]], [[11.0, 22.0], [33.0, 44.0]]],
            dtype=numpy.float32,
        )
        result = cds_science_image(cube, {"NAXIS": 3, "NAXIS3": 2})
        numpy.testing.assert_allclose(result, [[1.0, 2.0], [3.0, 4.0]])

    def test_fowler_pair_average(self) -> None:
        cube = numpy.array(
            [
                [[0.0, 0.0], [0.0, 0.0]],
                [[2.0, 4.0], [6.0, 8.0]],
                [[10.0, 0.0], [0.0, 0.0]],
                [[12.0, 4.0], [6.0, 8.0]],
            ],
            dtype=numpy.float32,
        )
        result = fowler_science_image(cube, {"NAXIS": 3, "NAXIS3": 4}, fowler_pairs=2)
        numpy.testing.assert_allclose(result, [[2.0, 4.0], [6.0, 8.0]])

    def test_science_image_from_cube_fowler(self) -> None:
        cube = numpy.array([[[5.0]], [[7.0]]], dtype=numpy.float32)
        result = science_image_from_cube(
            cube, {"NAXIS": 3, "NAXIS3": 2}, reduction="Fowler", fowler_pairs=1
        )
        self.assertAlmostEqual(float(result[0, 0]), 2.0)

    def test_raw_science_image_returns_first_plane(self) -> None:
        cube = numpy.array(
            [[[10.0, 20.0]], [[99.0, 88.0]]],
            dtype=numpy.float32,
        )
        result = raw_science_image(cube, {"NAXIS": 3, "NAXIS3": 2})
        numpy.testing.assert_allclose(result, [[10.0, 20.0]])

    def test_ramp_science_image_returns_last_plane(self) -> None:
        cube = numpy.array(
            [[[10.0, 20.0]], [[99.0, 88.0]]],
            dtype=numpy.float32,
        )
        result = ramp_science_image(cube, {"NAXIS": 3, "NAXIS3": 2})
        numpy.testing.assert_allclose(result, [[99.0, 88.0]])

    def test_science_image_from_cube_ramp(self) -> None:
        cube = numpy.array([[[3.0]], [[9.0]]], dtype=numpy.float32)
        result = science_image_from_cube(
            cube, {"NAXIS": 3, "NAXIS3": 2}, reduction="Ramp"
        )
        self.assertAlmostEqual(float(result[0, 0]), 9.0)


if __name__ == "__main__":
    unittest.main()
