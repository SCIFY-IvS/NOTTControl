"""Tests for ZMQ acquire multipart preview parsing."""

from __future__ import annotations

import unittest

import numpy

from nottcontrol.camera.macie.macie_interface import (
    AcquireResult,
    parse_acquire_preview_parts,
)


class ParseAcquirePreviewPartsTests(unittest.TestCase):
    def test_ok_without_preview(self) -> None:
        result = parse_acquire_preview_parts([b"ok;"])
        self.assertIsNone(result.frame)

    def test_ok_with_preview(self) -> None:
        nx, ny = 4, 3
        pixels = numpy.arange(nx * ny, dtype="<f4").reshape((ny, nx))
        header = f"ok;preview;{nx};{ny};float32".encode("utf-8")
        result = parse_acquire_preview_parts([header, pixels.tobytes()])
        self.assertIsInstance(result, AcquireResult)
        assert result.frame is not None
        numpy.testing.assert_array_equal(result.frame, pixels)

    def test_nok_raises(self) -> None:
        with self.assertRaises(Exception):
            parse_acquire_preview_parts([b"nok;failed"])

    def test_truncated_payload_raises(self) -> None:
        with self.assertRaises(Exception):
            parse_acquire_preview_parts([b"ok;preview;2;2;float32", b"xxxx"])


if __name__ == "__main__":
    unittest.main()
