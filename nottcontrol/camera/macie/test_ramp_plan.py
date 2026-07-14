"""Tests for ramp timing plans and Fowler/CDS reduction."""

from __future__ import annotations

import unittest

import numpy

from nottcontrol.camera.macie.fits_science import (
    cds_science_image,
    fowler_science_image,
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

    def test_cds_windowed_uses_single_group_two_reads(self) -> None:
        plan = calc_ramp_plan(500.0, 200.0, mode="CDS", windowed_cds=True)
        self.assertEqual(plan["ngroups"], 1)
        self.assertEqual(plan["nreads"], 2)
        self.assertEqual(plan["ndrops"], 0)

    def test_fowler_uses_single_group_and_even_reads(self) -> None:
        plan = calc_ramp_plan(180.0, 100.0, mode="Fowler", fowler_pairs=2)
        self.assertEqual(plan["ngroups"], 1)
        self.assertEqual(plan["nreads"], 4)
        self.assertEqual(plan["fowler_pairs"], 2)

    def test_exp_mode_values(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
