"""H2RG FITS header metadata helpers (Redis cryostat temperatures, etc.)."""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache
from typing import TYPE_CHECKING

from nottcontrol import sensor_config_path
from nottcontrol.sensors import load_temperature_sensors

if TYPE_CHECKING:
    from nottcontrol.redisclient import RedisClient

# FITS keyword, Redis temperature tag, header comment.
# Vote sensors match the main-window headline cryo temperatures.
H2RG_FITS_TEMP_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("DETTEMP", "t_detector_vote", "Detector vote temperature from Redis (K)"),
    ("BPTEMP", "t_base_plate_vote", "Base plate vote temperature from Redis (K)"),
)


@lru_cache(maxsize=1)
def _temperature_redis_keys_by_tag() -> dict[str, str]:
    _opc, redis_keys, _names, tags = load_temperature_sensors(sensor_config_path)
    return {tag: key for tag, key in zip(tags, redis_keys)}


def redis_key_for_temperature_tag(tag: str) -> str | None:
    """Return the Redis TimeSeries key for a nott_temp *tag*, or None."""
    return _temperature_redis_keys_by_tag().get(tag)


def cryo_temperatures_for_fits(
    redis_client: RedisClient | None,
) -> dict[str, tuple[float, str]]:
    """Return FITS cards ``{keyword: (value_K, comment)}`` from Redis.

    Missing Redis connectivity or missing series are skipped (no NaN cards).
    """
    if redis_client is None:
        return {}
    cards: dict[str, tuple[float, str]] = {}
    for keyword, tag, comment in H2RG_FITS_TEMP_FIELDS:
        redis_key = redis_key_for_temperature_tag(tag)
        if not redis_key:
            continue
        value = redis_client.get_latest(redis_key)
        if value is None:
            continue
        cards[keyword] = (float(value), comment)
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
