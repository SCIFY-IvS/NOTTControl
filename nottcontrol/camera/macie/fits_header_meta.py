"""H2RG FITS header metadata helpers (Redis instrument status)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from nottcontrol import sensor_config_path
from nottcontrol.sensors import load_pressure_sensors, load_temperature_sensors

if TYPE_CHECKING:
    from nottcontrol.redisclient import RedisClient

# FITS keyword, Redis temperature tag, header comment.
# Vote sensors match the main-window headline cryo temperatures.
H2RG_FITS_TEMP_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("DETTEMP", "t_detector_vote", "Detector vote temperature from Redis (K)"),
    ("BPTEMP", "t_base_plate_vote", "Base plate vote temperature from Redis (K)"),
)

# Delay-line positions logged by MotorWidget as ``{name}_pos`` (microns).
H2RG_FITS_DL_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("DL1POS", "DL_1_pos", "Delay line 1 position from Redis (um)"),
    ("DL2POS", "DL_2_pos", "Delay line 2 position from Redis (um)"),
    ("DL3POS", "DL_3_pos", "Delay line 3 position from Redis (um)"),
    ("DL4POS", "DL_4_pos", "Delay line 4 position from Redis (um)"),
)

# Pressure sensors from sensors.ini (tag → FITS keyword / comment).
# Pump foreline is logged in hPa; convert to mbar (1 hPa == 1 mbar).
H2RG_FITS_PRESSURE_FIELDS: tuple[tuple[str, str, str], ...] = (
    (
        "PRESVAGC",
        "VAGC.stat.lrPressure",
        "VAGC cryostat pressure from Redis (mbar)",
    ),
    (
        "PRESPUMP",
        "evac.pump_pvp.stat.PresSens_lrPressure_hPa",
        "Pump foreline pressure from Redis (mbar)",
    ),
)

# Redis tags whose TimeSeries values are stored in hPa and must be reported as mbar.
_PRESSURE_TAGS_HPA_TO_MBAR = frozenset(
    {"evac.pump_pvp.stat.PresSens_lrPressure_hPa"}
)
HPA_TO_MBAR = 1.0  # 1 hPa = 1 mbar


@lru_cache(maxsize=1)
def _temperature_redis_keys_by_tag() -> dict[str, str]:
    _opc, redis_keys, _names, tags = load_temperature_sensors(sensor_config_path)
    return {tag: key for tag, key in zip(tags, redis_keys)}


@lru_cache(maxsize=1)
def _pressure_redis_keys_by_tag() -> dict[str, str]:
    _opc, redis_keys, _names, tags, _units = load_pressure_sensors(sensor_config_path)
    return {tag: key for tag, key in zip(tags, redis_keys)}


def redis_key_for_temperature_tag(tag: str) -> str | None:
    """Return the Redis TimeSeries key for a nott_temp *tag*, or None."""
    return _temperature_redis_keys_by_tag().get(tag)


def redis_key_for_pressure_tag(tag: str) -> str | None:
    """Return the Redis TimeSeries key for a pressure *tag*, or None."""
    return _pressure_redis_keys_by_tag().get(tag)


def _cards_from_redis_keys(
    redis_client: RedisClient,
    fields: tuple[tuple[str, str, str], ...],
    *,
    resolve_key,
) -> dict[str, tuple[float, str]]:
    cards: dict[str, tuple[float, str]] = {}
    for keyword, key_or_tag, comment in fields:
        redis_key = resolve_key(key_or_tag)
        if not redis_key:
            continue
        value = redis_client.get_latest(redis_key)
        if value is None:
            continue
        cards[keyword] = (float(value), comment)
    return cards


def cryo_temperatures_for_fits(
    redis_client: RedisClient | None,
) -> dict[str, tuple[float, str]]:
    """Return FITS cards ``{keyword: (value_K, comment)}`` from Redis."""
    if redis_client is None:
        return {}
    return _cards_from_redis_keys(
        redis_client,
        H2RG_FITS_TEMP_FIELDS,
        resolve_key=redis_key_for_temperature_tag,
    )


def delay_line_positions_for_fits(
    redis_client: RedisClient | None,
) -> dict[str, tuple[float, str]]:
    """Return FITS cards for DL_1…DL_4 positions (um) from Redis."""
    if redis_client is None:
        return {}
    return _cards_from_redis_keys(
        redis_client,
        H2RG_FITS_DL_FIELDS,
        resolve_key=lambda key: key,
    )


def pressures_for_fits(
    redis_client: RedisClient | None,
) -> dict[str, tuple[float, str]]:
    """Return FITS cards for cryostat / pump pressures from Redis (mbar)."""
    if redis_client is None:
        return {}
    cards: dict[str, tuple[float, str]] = {}
    for keyword, tag, comment in H2RG_FITS_PRESSURE_FIELDS:
        redis_key = redis_key_for_pressure_tag(tag)
        if not redis_key:
            continue
        value = redis_client.get_latest(redis_key)
        if value is None:
            continue
        pressure_mbar = float(value)
        if tag in _PRESSURE_TAGS_HPA_TO_MBAR:
            pressure_mbar *= HPA_TO_MBAR
        cards[keyword] = (pressure_mbar, comment)
    return cards


def fits_header_cards_from_redis(
    redis_client: RedisClient | None,
) -> dict[str, tuple[float, str]]:
    """Collect temperature, delay-line, and pressure cards for H2RG FITS headers."""
    cards: dict[str, tuple[float, str]] = {}
    cards.update(cryo_temperatures_for_fits(redis_client))
    cards.update(delay_line_positions_for_fits(redis_client))
    cards.update(pressures_for_fits(redis_client))
    return cards


def apply_fits_header_cards(header, cards: dict[str, tuple[float, str]]) -> None:
    """Write *cards* onto an astropy ``fits.Header`` (or Header-like mapping)."""
    for keyword, (value, comment) in cards.items():
        header[keyword] = (value, comment)


def update_fits_file_header_cards(
    path: Path, cards: dict[str, tuple[float, str]]
) -> bool:
    """Update primary-header keywords in an existing FITS file. Return True on success."""
    if not cards:
        return False
    try:
        from astropy.io import fits

        with fits.open(path, mode="update") as hdul:
            apply_fits_header_cards(hdul[0].header, cards)
            hdul.flush()
    except Exception as exc:
        print(f"H2RG failed to update FITS header on {path}: {exc}")
        return False
    return True
