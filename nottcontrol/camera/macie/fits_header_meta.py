"""H2RG FITS header metadata helpers (Redis instrument status)."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from nottcontrol import sensor_config_path
from nottcontrol.sensors import load_pressure_sensors, load_temperature_sensors

if TYPE_CHECKING:
    from nottcontrol.redisclient import RedisClient

# (keyword, value, comment). COMMENT cards use value=None.
HeaderCard = tuple[str, float | str | None, str]

DETMODE_COMMENT = "Detector readout mode"
EXPTIME_COMMENT = "Photon collection time (s)"


def detector_mode_fits_card(mode: str) -> HeaderCard:
    """FITS card for the GUI/ASIC ramp readout mode."""
    return ("DETMODE", str(mode), DETMODE_COMMENT)


def exposure_fits_cards(
    *,
    mode: str | None = None,
    tint_ms: float | None = None,
    ngroups: int | None = None,
    nreads: int | None = None,
    ndrops: int | None = None,
) -> list[HeaderCard]:
    """Acquisition timing/mode cards for ramp and science FITS headers."""
    cards: list[HeaderCard] = []
    if mode is not None:
        cards.append(detector_mode_fits_card(mode))
    if tint_ms is not None:
        cards.append(("EXPTIME", float(tint_ms) / 1000.0, EXPTIME_COMMENT))
    if ngroups is not None:
        cards.append(("NGROUPS", int(ngroups), "Number of groups in ramp"))
    if nreads is not None:
        cards.append(("NREADS", int(nreads), "Reads per group"))
    if ndrops is not None:
        cards.append(("NDROPS", int(ndrops), "Drop frames between groups"))
    return cards


def utc_fits_timestamp(when: datetime | None = None) -> str:
    """UTC timestamp for FITS DATE-OBS: ``YYYY-MM-DDThh:mm:ss.ffffffZ``."""
    stamp = datetime.now(timezone.utc) if when is None else when
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    else:
        stamp = stamp.astimezone(timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def fits_file_id(name: str) -> str:
    """Ramp index from a FITS basename (e.g. ``000018``), else the stem."""
    stem = Path(name).stem
    if stem.lower().endswith("_science"):
        stem = stem[: -len("_science")]
    if stem.lower() == "preview":
        return stem
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[1]
    return stem


def file_identity_fits_cards(
    path: Path | str,
    *,
    when: datetime | None = None,
) -> list[HeaderCard]:
    """FILENAME, FILEID, and precise UTC DATE-OBS for a ramp or science FITS."""
    path = Path(path)
    name = path.name
    if when is None:
        try:
            when = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            when = datetime.now(timezone.utc)
    return [
        ("FILENAME", name, "Original FITS file name"),
        ("FILEID", fits_file_id(name), "Ramp file identifier"),
        ("DATE-OBS", utc_fits_timestamp(when), "UTC observation time"),
    ]

# FITS keyword, Redis temperature tag, header comment (unit in brackets).
H2RG_FITS_TEMP_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("DETTEMP", "t_detector_vote", "Detector vote temperature [K]"),
    ("BPTEMP", "t_base_plate_vote", "Base plate vote temperature [K]"),
)

# Delay-line positions logged by MotorWidget as ``{name}_pos`` (microns).
H2RG_FITS_DL_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("DL1POS", "DL_1_pos", "Delay line 1 position [um]"),
    ("DL2POS", "DL_2_pos", "Delay line 2 position [um]"),
    ("DL3POS", "DL_3_pos", "Delay line 3 position [um]"),
    ("DL4POS", "DL_4_pos", "Delay line 4 position [um]"),
)

# Shutter positions logged as ``Shutter N_pos`` (millimetres; open≈5, closed≈35).
H2RG_FITS_SHUTTER_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("SH1POS", "Shutter 1_pos", "Shutter 1 position [mm]"),
    ("SH2POS", "Shutter 2_pos", "Shutter 2 position [mm]"),
    ("SH3POS", "Shutter 3_pos", "Shutter 3 position [mm]"),
    ("SH4POS", "Shutter 4_pos", "Shutter 4 position [mm]"),
)

# Pressure sensors from sensors.ini (tag → FITS keyword / comment).
# Pump foreline is logged in hPa; convert to mbar (1 hPa == 1 mbar).
H2RG_FITS_PRESSURE_FIELDS: tuple[tuple[str, str, str], ...] = (
    (
        "PRESVAGC",
        "VAGC.stat.lrPressure",
        "VAGC cryostat pressure [mbar]",
    ),
    (
        "PRESPUMP",
        "evac.pump_pvp.stat.PresSens_lrPressure_hPa",
        "Pump foreline pressure [mbar]",
    ),
)

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


def fits_round(value: float, *, scientific_if_small: bool = False) -> float:
    """Round to two decimal places; use 2-digit scientific form for tiny pressures."""
    number = float(value)
    if scientific_if_small and abs(number) > 0.0 and abs(number) < 1e-2:
        return float(f"{number:.2e}")
    return round(number, 2)


def _value_cards_from_redis(
    redis_client: RedisClient,
    fields: tuple[tuple[str, str, str], ...],
    *,
    resolve_key,
    scientific_if_small: bool = False,
    scale: float = 1.0,
) -> list[HeaderCard]:
    cards: list[HeaderCard] = []
    for keyword, key_or_tag, comment in fields:
        redis_key = resolve_key(key_or_tag)
        if not redis_key:
            continue
        value = redis_client.get_latest(redis_key)
        if value is None:
            continue
        cards.append(
            (
                keyword,
                fits_round(float(value) * scale, scientific_if_small=scientific_if_small),
                comment,
            )
        )
    return cards


def cryo_temperatures_for_fits(
    redis_client: RedisClient | None,
) -> list[HeaderCard]:
    """Return temperature FITS cards from Redis (Kelvin, 2 decimals)."""
    if redis_client is None:
        return []
    return _value_cards_from_redis(
        redis_client,
        H2RG_FITS_TEMP_FIELDS,
        resolve_key=redis_key_for_temperature_tag,
    )


def delay_line_positions_for_fits(
    redis_client: RedisClient | None,
) -> list[HeaderCard]:
    """Return DL_1…DL_4 position cards from Redis (um, 2 decimals)."""
    if redis_client is None:
        return []
    return _value_cards_from_redis(
        redis_client,
        H2RG_FITS_DL_FIELDS,
        resolve_key=lambda key: key,
    )


def shutter_positions_for_fits(
    redis_client: RedisClient | None,
) -> list[HeaderCard]:
    """Return Shutter 1…4 position cards from Redis (mm, 2 decimals)."""
    if redis_client is None:
        return []
    return _value_cards_from_redis(
        redis_client,
        H2RG_FITS_SHUTTER_FIELDS,
        resolve_key=lambda key: key,
    )


def pressures_for_fits(
    redis_client: RedisClient | None,
) -> list[HeaderCard]:
    """Return cryostat / pump pressure cards from Redis (mbar)."""
    if redis_client is None:
        return []
    cards: list[HeaderCard] = []
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
        cards.append(
            (
                keyword,
                fits_round(pressure_mbar, scientific_if_small=True),
                comment,
            )
        )
    return cards


def fits_header_cards_from_redis(
    redis_client: RedisClient | None,
) -> list[HeaderCard]:
    """Ordered FITS cards: temperatures, pressures, delay lines, shutters.

    Groups are separated with COMMENT markers and include units in comments.
    """
    cards: list[HeaderCard] = []

    temps = cryo_temperatures_for_fits(redis_client)
    if temps:
        cards.append(("COMMENT", None, "----- Temperatures [K] -----"))
        cards.extend(temps)

    pressures = pressures_for_fits(redis_client)
    if pressures:
        cards.append(("COMMENT", None, "----- Pressures [mbar] -----"))
        cards.extend(pressures)

    positions = delay_line_positions_for_fits(redis_client)
    if positions:
        cards.append(("COMMENT", None, "----- Delay line positions [um] -----"))
        cards.extend(positions)

    shutters = shutter_positions_for_fits(redis_client)
    if shutters:
        cards.append(("COMMENT", None, "----- Shutter positions [mm] -----"))
        cards.extend(shutters)

    return cards


def header_cards_as_value_dict(
    cards: list[HeaderCard],
) -> dict[str, tuple[float | str, str]]:
    """Map of value keywords only (no COMMENT), for in-memory headers."""
    return {
        keyword: (value, comment)
        for keyword, value, comment in cards
        if keyword != "COMMENT" and value is not None
    }


def apply_fits_header_cards(header, cards: list[HeaderCard] | dict) -> None:
    """Write *cards* onto an astropy ``fits.Header`` (or Header-like mapping)."""
    if isinstance(cards, dict):
        for keyword, (value, comment) in cards.items():
            header[keyword] = (value, comment)
        return

    for keyword, value, comment in cards:
        if keyword == "COMMENT":
            text = comment or ""
            if hasattr(header, "add_comment"):
                header.add_comment(text)
            else:
                header["COMMENT"] = text
            continue
        if value is None:
            continue
        header[keyword] = (value, comment)


def update_fits_file_header_cards(
    path: Path, cards: list[HeaderCard] | dict
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
