from __future__ import annotations

from nottcontrol import config
from nottcontrol.camera.infratec.hirbgrab import (
    IRBG_PARAM_Calib_MaxFrameRate,
    IRBG_PARAM_Framerate_Hz,
    IRBG_PARAM_Framerate_Max,
    IRBG_PARAM_IntegTime,
    IRBG_PARAM_MIT_Count,
)

DEFAULT_FRAMERATE_OPTIONS_HZ = (
    1.0,
    2.0,
    5.0,
    10.0,
    12.5,
    15.0,
    20.0,
    25.0,
    30.0,
    40.0,
    50.0,
    60.0,
    80.0,
    100.0,
    125.0,
    200.0,
)


def _parse_int_list(raw: str) -> list[int]:
    values: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        values.append(int(part))
    return values


def _parse_float_list(raw: str) -> list[float]:
    values: list[float] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        values.append(float(part))
    return values


def fallback_integration_times_us() -> list[int]:
    raw = config["CAMERA"].get(
        "integration_times_us",
        "200,500,1000,2000,5000,10000",
    )
    return sorted(_parse_int_list(raw))


def fallback_framerate_options_hz() -> list[float]:
    raw = config["CAMERA"].get(
        "framerates_hz",
        "10,20,25,30,40,50,60,80,100",
    )
    return sorted(_parse_float_list(raw))


def format_exposure_ms(integration_us: int) -> str:
    ms = integration_us / 1000.0
    text = f"{ms:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def format_framerate_hz(framerate_hz: float) -> str:
    text = f"{framerate_hz:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def get_integration_time_options_us(interface) -> list[int]:
    options: list[int] = []
    try:
        count = int(interface.getparam_int32(IRBG_PARAM_MIT_Count))
    except Exception:
        count = 0

    for index in range(max(count, 0)):
        try:
            integration_us = int(
                interface.getparam_idx_int32(IRBG_PARAM_IntegTime, index)
            )
        except Exception:
            continue
        if integration_us > 0 and integration_us not in options:
            options.append(integration_us)

    if not options:
        try:
            current_us = int(
                interface.getparam_idx_int32(IRBG_PARAM_IntegTime, 0)
            )
            if current_us > 0:
                options.append(current_us)
        except Exception:
            pass

    if not options:
        options = fallback_integration_times_us()
    return sorted(options)


def get_framerate_options_hz(interface) -> list[float]:
    max_hz = 500.0
    for parameter in (IRBG_PARAM_Framerate_Max, IRBG_PARAM_Calib_MaxFrameRate):
        try:
            max_hz = min(max_hz, float(interface.getparam_single(parameter)))
        except Exception:
            continue

    candidates = list(DEFAULT_FRAMERATE_OPTIONS_HZ) + fallback_framerate_options_hz()
    options: list[float] = []
    for rate in candidates:
        if rate <= max_hz + 0.01 and rate not in options:
            options.append(rate)

    try:
        current_hz = float(interface.getparam_single(IRBG_PARAM_Framerate_Hz))
        if current_hz > 0 and all(abs(current_hz - rate) > 0.05 for rate in options):
            options.append(current_hz)
    except Exception:
        pass

    if not options:
        options = fallback_framerate_options_hz()
    return sorted(options)
