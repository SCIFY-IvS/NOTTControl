"""Load cryostat sensor OPC UA nodes and map them to Redis TimeSeries keys."""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path


def opc_node_path(opc_node: str) -> str:
    """Return the PLC browse path from a sensors.ini line or asyncua node id."""
    if opc_node.startswith("ns="):
        _, _, path = opc_node.partition(";s=")
        return path or opc_node
    if "|" in opc_node:
        return opc_node.split("|")[-1]
    return opc_node


def opc_node_to_asyncua_id(opc_node: str) -> str:
    """Convert a sensors.ini line to an asyncua-compatible node id string."""
    if opc_node.startswith("ns="):
        return opc_node

    path = opc_node_path(opc_node)
    namespace = "4"
    if "|" in opc_node:
        ns_token = opc_node.split("|", 1)[0]
        if ns_token.upper().startswith("NS") and ns_token[2:].isdigit():
            namespace = ns_token[2:]
    return f"ns={namespace};s={path}"


def opc_node_to_redis_key(opc_node: str) -> str:
    """Use the asyncua OPC UA node id as the Redis TimeSeries key."""
    return opc_node_to_asyncua_id(opc_node)


def temperature_tag(opc_node_id: str) -> str | None:
    """Return the nott_temp tag (e.g. t_detector_vote) or None if not a temperature node."""
    path = opc_node_path(opc_node_id)
    if ".nott_temp." not in path or not path.endswith("lrTempK"):
        return None
    return path.split(".nott_temp.")[1].split(".stat.")[0]


def temperature_group(tag: str) -> str:
    """Group name for sorting and section headers in the GUI."""
    group_prefixes = [
        ("Detector", "t_detector"),
        ("Base plate", "t_base_plate"),
        ("Shield", "t_shield"),
        ("Photonic chip", "t_photonic_chip"),
        ("Flat field", "t_flat_field"),
        ("Master", "t_master"),
        ("Sidecar", "t_sidecar"),
        ("Thermal box", "t_thermal_box"),
        ("Cabinet", "t_cabinet"),
    ]
    for group_name, prefix in group_prefixes:
        if tag == prefix or tag.startswith(f"{prefix}_"):
            return group_name
    return "Other"


def temperature_display_name(tag: str) -> str:
    """Human-readable label for a temperature tag."""
    name = tag[2:] if tag.startswith("t_") else tag
    return name.replace("_", " ")


def is_vote_temperature_tag(tag: str) -> bool:
    """True for consolidated vote sensors (one reading per device group)."""
    return tag.endswith("_vote")


def filter_temperature_sensors(
    opc_nodes: list[str],
    redis_keys: list[str],
    display_names: list[str],
    tags: list[str],
    *,
    tag_filter,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return temperature sensor lists filtered by ``tag_filter(tag) -> bool``."""
    filtered_opc: list[str] = []
    filtered_redis: list[str] = []
    filtered_names: list[str] = []
    filtered_tags: list[str] = []
    for opc_id, redis_key, name, tag in zip(
        opc_nodes, redis_keys, display_names, tags
    ):
        if not tag_filter(tag):
            continue
        filtered_opc.append(opc_id)
        filtered_redis.append(redis_key)
        filtered_names.append(name)
        filtered_tags.append(tag)
    return filtered_opc, filtered_redis, filtered_names, filtered_tags


def load_temperature_sensors(
    path: str | Path,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (opc_ids, redis_keys, display_names, tags) for temperature sensors only."""
    opc_nodes: list[str] = []
    redis_keys: list[str] = []
    display_names: list[str] = []
    tags: list[str] = []
    with open(path, encoding="utf-8") as sensors_file:
        for raw_line in sensors_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            opc_id = opc_node_to_asyncua_id(line)
            tag = temperature_tag(opc_id)
            if tag is None:
                continue
            opc_nodes.append(opc_id)
            redis_keys.append(opc_node_to_redis_key(line))
            display_names.append(temperature_display_name(tag))
            tags.append(tag)
    return opc_nodes, redis_keys, display_names, tags


def pressure_tag(opc_node_id: str) -> str | None:
    """Return a stable tag for a pressure/vacuum sensor, or None if it is a temperature node."""
    if temperature_tag(opc_node_id) is not None:
        return None
    path = opc_node_path(opc_node_id)
    if "MAIN.nott_cryo_ctrl." not in path:
        return path
    return path.split("MAIN.nott_cryo_ctrl.", 1)[1]


def pressure_display_name(tag: str) -> str:
    """Human-readable label for a pressure/vacuum sensor tag."""
    names = {
        "VAGC.stat.lrPressure": "VAGC pressure",
        "evac.pump_pvp.stat.PresSens_lrPressure_hPa": "Pump pressure",
        "evac.pump_tmp.stat.nPumpSpeed": "TMP speed",
        "evac.pump_pvp.stat.nPumpSpeed": "PVP speed",
    }
    if tag in names:
        return names[tag]
    return tag.replace(".stat.", " ").replace("_", " ")


def pressure_unit(tag: str) -> str:
    if tag.endswith("lrPressure_hPa"):
        return "hPa"
    if tag.endswith("nPumpSpeed"):
        return "rpm"
    if tag.endswith("lrPressure"):
        return "mbar"
    return ""


def format_pressure_value(tag: str, value: float | None) -> str:
    if value is None:
        return "—"
    unit = pressure_unit(tag)
    if unit == "hPa":
        if abs(value) < 0.01 and value != 0:
            text = f"{value:.2e}"
        else:
            text = f"{value:.3f}"
    elif unit == "rpm":
        text = f"{int(round(value))}"
    else:
        if abs(value) < 0.01 and value != 0:
            text = f"{value:.2e}"
        else:
            text = f"{value:.3f}"
    return f"{text} {unit}".strip()


def load_pressure_sensors(
    path: str | Path,
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Return (opc_ids, redis_keys, display_names, tags, units) for pressure sensors."""
    opc_nodes: list[str] = []
    redis_keys: list[str] = []
    display_names: list[str] = []
    tags: list[str] = []
    units: list[str] = []
    with open(path, encoding="utf-8") as sensors_file:
        for raw_line in sensors_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            opc_id = opc_node_to_asyncua_id(line)
            tag = pressure_tag(opc_id)
            if tag is None:
                continue
            opc_nodes.append(opc_id)
            redis_keys.append(opc_node_to_redis_key(line))
            tags.append(tag)
            display_names.append(pressure_display_name(tag))
            units.append(pressure_unit(tag))
    return opc_nodes, redis_keys, display_names, tags, units


@dataclass(frozen=True)
class CryoStatusItem:
    key: str
    label: str
    opc_id: str


PUMP_SPEED_TAGS: dict[str, str] = {
    "tmp": "evac.pump_tmp.stat.nPumpSpeed",
    "pvp": "evac.pump_pvp.stat.nPumpSpeed",
}


def format_equipment_status(value) -> tuple[str, str]:
    """Return (display text, style key) for pump/cryocooler on/off values."""
    if value is None:
        return "Unknown", "unknown"
    if isinstance(value, bool):
        return ("On" if value else "Off"), ("running" if value else "stopped")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        is_on = value != 0
        return ("On" if is_on else "Off"), ("running" if is_on else "stopped")

    text = str(value).strip()
    if not text:
        return "Unknown", "unknown"

    upper = text.upper()
    on_tokens = {"TRUE", "ON", "RUN", "RUNNING", "ENABLED", "ACTIVE", "STARTED"}
    off_tokens = {"FALSE", "OFF", "STOP", "STOPPED", "IDLE", "DISABLED", "STANDBY"}
    if upper in on_tokens:
        return "On", "running"
    if upper in off_tokens:
        return "Off", "stopped"
    return text, "unknown"


def format_pump_status(value, speed_rpm: float | None) -> tuple[str, str]:
    """Return on/off text with pump speed on the same line."""
    text, style_key = format_equipment_status(value)
    if speed_rpm is not None:
        text = f"{text} · {int(round(speed_rpm))} rpm"
    return text, style_key


def load_cryo_status_config(path: str | Path) -> list[CryoStatusItem]:
    """Load equipment status nodes from cryo_status.ini."""
    items: list[CryoStatusItem] = []
    with open(path, encoding="utf-8") as status_file:
        for raw_line in status_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) >= 3:
                key, label = parts[0], parts[1]
                opc_node = "|".join(parts[2:])
            elif len(parts) == 2:
                key, opc_node = parts
                label = key.replace("_", " ").title()
            else:
                continue
            items.append(
                CryoStatusItem(
                    key=key,
                    label=label,
                    opc_id=opc_node_to_asyncua_id(opc_node),
                )
            )
    return items


def coerce_sensor_value(value) -> float | None:
    """Return a finite float suitable for Redis TimeSeries, or None if invalid."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def load_sensor_config(path: str | Path) -> tuple[list[str], list[str]]:
    """Return (asyncua_node_ids, redis_keys) from sensors.ini."""
    opc_nodes: list[str] = []
    redis_keys: list[str] = []
    with open(path, encoding="utf-8") as sensors_file:
        for raw_line in sensors_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            opc_nodes.append(opc_node_to_asyncua_id(line))
            redis_keys.append(opc_node_to_redis_key(line))
    return opc_nodes, redis_keys
