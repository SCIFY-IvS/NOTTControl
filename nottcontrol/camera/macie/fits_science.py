"""FITS ramp loading and CDS/Fowler science-image helpers for H2RG/MACIE."""

from __future__ import annotations

import time
import warnings
from io import BytesIO
from pathlib import Path
from typing import Literal

import numpy

RampReduction = Literal["SingleFrame", "Ramp", "CDS", "Fowler"]


class TruncatedFitsError(OSError):
    """Raised when a FITS file is still being written or is incomplete."""


def wait_for_file_size_stable(
    path: Path,
    *,
    settle_s: float = 0.45,
    timeout_s: float = 45.0,
    poll_s: float = 0.1,
    min_bytes: int = 2880,
) -> bool:
    """Wait until *path* exists and its size is unchanged for *settle_s*.

    SMB copies of MACIE full-frame ramps often appear before the write finishes.
    Opening early triggers Astropy "File may have been truncated" warnings.
    """
    path = Path(path)
    deadline = time.monotonic() + max(0.1, float(timeout_s))
    last_size = -1
    stable_since: float | None = None
    while time.monotonic() < deadline:
        try:
            size = int(path.stat().st_size)
        except OSError:
            last_size = -1
            stable_since = None
            time.sleep(poll_s)
            continue
        if size < int(min_bytes):
            last_size = size
            stable_since = None
            time.sleep(poll_s)
            continue
        if size == last_size:
            if stable_since is None:
                stable_since = time.monotonic()
            elif (time.monotonic() - stable_since) >= float(settle_s):
                return True
        else:
            last_size = size
            stable_since = None
        time.sleep(poll_s)
    return False


def _fits_data_nbytes_expected(header: dict) -> int | None:
    try:
        naxis = int(header.get("NAXIS", 0) or 0)
        if naxis < 2:
            return None
        bitpix = abs(int(header.get("BITPIX", 16) or 16))
        if bitpix not in (8, 16, 32, 64):
            return None
        n = 1
        for i in range(1, naxis + 1):
            n *= max(1, int(header.get(f"NAXIS{i}", 1) or 1))
        return n * (bitpix // 8)
    except (TypeError, ValueError):
        return None


def load_fits_data(source: Path | bytes) -> tuple[numpy.ndarray, dict]:
    """Load primary HDU image data and header from a path or bytes.

    Raises TruncatedFitsError if the file is incomplete (common while MACIE is
    still writing a full-frame ramp over SMB).
    """
    from astropy.io import fits

    handle = None
    caught: list = []
    header: dict | None = None
    data: numpy.ndarray | None = None
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            if isinstance(source, bytes):
                handle = fits.open(BytesIO(source), memmap=False)
            else:
                handle = fits.open(source, memmap=False)
            hdu = handle[0]
            if hdu.data is None:
                raise TruncatedFitsError("FITS primary HDU has no image data")
            header = dict(hdu.header)
            data = numpy.asarray(hdu.data)
    except TruncatedFitsError:
        raise
    except OSError:
        raise
    except (ValueError, EOFError) as exc:
        raise TruncatedFitsError(str(exc)) from exc
    except Exception as exc:
        msg = str(exc).lower()
        if "truncat" in msg or "smaller than the expected" in msg:
            raise TruncatedFitsError(str(exc)) from exc
        raise
    finally:
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass

    for warning in caught:
        text = str(warning.message).lower()
        if "truncat" in text or "smaller than the expected" in text:
            raise TruncatedFitsError(str(warning.message))

    if header is None or data is None:
        raise TruncatedFitsError("FITS primary HDU has no image data")

    expected = _fits_data_nbytes_expected(header)
    if expected is not None and int(data.nbytes) < int(expected):
        raise TruncatedFitsError(
            f"FITS image incomplete: got {data.nbytes} bytes, expected {expected}"
        )
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


def ramp_science_image(
    data: numpy.ndarray, header: dict | None = None
) -> numpy.ndarray:
    """Return the last saved raw sample (end of the requested DIT)."""
    arr = numpy.asarray(data, dtype=numpy.float32)
    if arr.ndim <= 2:
        return arr

    axis = ramp_sample_axis(header or {}, arr.shape)
    if arr.shape[axis] == 1:
        return numpy.take(arr, 0, axis=axis)
    return numpy.take(arr, -1, axis=axis)


def raw_science_image(
    data: numpy.ndarray, header: dict | None = None
) -> numpy.ndarray:
    """Return the first saved sample (single-frame readout)."""
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
    if reduction == "Ramp":
        return ramp_science_image(data, header)
    if reduction == "SingleFrame":
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
    extra_cards: list | dict | None = None,
) -> Path:
    from astropy.io import fits

    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = fits.Header()
    header["IMTYPE"] = ("SCIENCE", "Reduced science image")
    from nottcontrol.camera.macie.fits_header_meta import detector_mode_fits_card

    mode_key, mode_val, mode_comment = detector_mode_fits_card(reduction)
    header[mode_key] = (mode_val, mode_comment)
    if reduction == "Fowler":
        header["REDUCT"] = (f"Fowler{fowler_pairs}", "Mean pair-difference ramp")
    elif reduction == "SingleFrame":
        header["REDUCT"] = ("SINGLE", "Single clocked frame (no drops)")
    elif reduction == "Ramp":
        header["REDUCT"] = ("RAW", "Single raw ramp sample")
    else:
        header["REDUCT"] = ("CDS", "Last minus first ramp sample")
    if tint_ms is not None:
        header["EXPTIME"] = (tint_ms / 1000.0, "Photon collection time (s)")
    if source_header:
        for key in ("DATE-OBS", "AMPGAIN", "AMPINPUT", "DETTYPE", "SMPLMODE"):
            if key in source_header:
                header[key] = source_header[key]
    if extra_cards:
        from nottcontrol.camera.macie.fits_header_meta import apply_fits_header_cards

        apply_fits_header_cards(header, extra_cards)

    hdu = fits.PrimaryHDU(data=image.astype(numpy.float32), header=header)
    hdu.writeto(output_path, overwrite=True)
    return output_path
