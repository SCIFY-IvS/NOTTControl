"""FITS ramp loading and CDS/Fowler science-image helpers for H2RG/MACIE."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Literal

import numpy

RampReduction = Literal["Normal", "CDS", "Fowler"]


def load_fits_data(source: Path | bytes) -> tuple[numpy.ndarray, dict]:
    from astropy.io import fits

    if isinstance(source, bytes):
        handle = fits.open(BytesIO(source), memmap=False)
    else:
        handle = fits.open(source, memmap=False)

    with handle as hdul:
        header = dict(hdul[0].header)
        data = numpy.asarray(hdul[0].data)
    return data, header


def ramp_sample_axis(header: dict, shape: tuple[int, ...]) -> int:
    naxis = int(header.get("NAXIS", len(shape)))
    if naxis < 3:
        return 0
    naxis3 = int(header.get("NAXIS3", shape[0] if len(shape) == 3 else 1))
    if len(shape) == 3 and shape[0] == naxis3:
        return 0
    if len(shape) == 3 and shape[-1] == naxis3:
        return 2
    return 0


def cds_science_image(
    data: numpy.ndarray, header: dict | None = None
) -> numpy.ndarray:
    arr = numpy.asarray(data, dtype=numpy.float32)
    if arr.ndim <= 2:
        return arr

    axis = ramp_sample_axis(header or {}, arr.shape)
    if arr.shape[axis] == 1:
        return numpy.take(arr, 0, axis=axis)
    first = numpy.take(arr, 0, axis=axis)
    last = numpy.take(arr, -1, axis=axis)
    return last - first


def fowler_science_image(
    data: numpy.ndarray,
    header: dict | None = None,
    *,
    fowler_pairs: int = 2,
) -> numpy.ndarray:
    """Average of correlated pair differences (Fowler-N)."""
    arr = numpy.asarray(data, dtype=numpy.float32)
    if arr.ndim <= 2:
        return arr

    axis = ramp_sample_axis(header or {}, arr.shape)
    nsamples = arr.shape[axis]
    pairs = max(1, min(int(fowler_pairs), nsamples // 2))
    diffs = []
    for index in range(pairs):
        first = numpy.take(arr, 2 * index, axis=axis)
        second = numpy.take(arr, 2 * index + 1, axis=axis)
        diffs.append(second - first)
    return numpy.mean(numpy.stack(diffs, axis=0), axis=0).astype(numpy.float32)


def raw_science_image(
    data: numpy.ndarray, header: dict | None = None
) -> numpy.ndarray:
    """Return the single saved sample (first plane if a ramp cube)."""
    arr = numpy.asarray(data, dtype=numpy.float32)
    if arr.ndim <= 2:
        return arr

    axis = ramp_sample_axis(header or {}, arr.shape)
    return numpy.take(arr, 0, axis=axis)


def science_image_from_cube(
    data: numpy.ndarray,
    header: dict | None = None,
    *,
    reduction: RampReduction = "CDS",
    fowler_pairs: int = 2,
) -> numpy.ndarray:
    if reduction == "Fowler":
        return fowler_science_image(data, header, fowler_pairs=fowler_pairs)
    if reduction == "Normal":
        return raw_science_image(data, header)
    return cds_science_image(data, header)


def load_science_image(
    source: Path | bytes,
    *,
    reduction: RampReduction = "CDS",
    fowler_pairs: int = 2,
) -> numpy.ndarray:
    data, header = load_fits_data(source)
    return science_image_from_cube(
        data, header, reduction=reduction, fowler_pairs=fowler_pairs
    )


def science_fits_path(ramp_path: Path) -> Path:
    stem = ramp_path.stem
    if stem.endswith("_science"):
        return ramp_path
    return ramp_path.with_name(f"{stem}_science.fits")


def save_science_fits(
    output_path: Path,
    image: numpy.ndarray,
    *,
    source_header: dict | None = None,
    tint_ms: float | None = None,
    reduction: RampReduction = "CDS",
    fowler_pairs: int = 2,
) -> Path:
    from astropy.io import fits

    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = fits.Header()
    header["IMTYPE"] = ("SCIENCE", "Reduced science image")
    if reduction == "Fowler":
        header["REDUCT"] = (f"Fowler{fowler_pairs}", "Mean pair-difference ramp")
    elif reduction == "Normal":
        header["REDUCT"] = ("RAW", "Single raw ramp sample")
    else:
        header["REDUCT"] = ("CDS", "Last minus first ramp sample")
    if tint_ms is not None:
        header["EXPTIME"] = (tint_ms / 1000.0, "Photon collection time (s)")
    if source_header:
        for key in ("DATE-OBS", "AMPGAIN", "AMPINPUT", "DETTYPE", "SMPLMODE"):
            if key in source_header:
                header[key] = source_header[key]

    hdu = fits.PrimaryHDU(data=image.astype(numpy.float32), header=header)
    hdu.writeto(output_path, overwrite=True)
    return output_path
