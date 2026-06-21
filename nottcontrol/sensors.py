"""Load cryostat sensor OPC UA nodes and map them to Redis TimeSeries keys."""
from __future__ import annotations

from pathlib import Path


def opc_node_to_redis_key(opc_node: str) -> str:
    """Build a short Redis TS key from a cryo OPC UA node identifier line.

    Example
    -------
    NS4|String|MAIN.nott_cryo_ctrl.nott_temp.t_detector.stat.lrTempK
    -> cryo.t_detector.lrTempK
    """
    path = opc_node.split("|")[-1] if "|" in opc_node else opc_node
    parts = path.split(".")
    if "stat" not in parts:
        return path.replace(".", "_")

    stat_idx = parts.index("stat")
    field = parts[stat_idx + 1] if stat_idx + 1 < len(parts) else "value"
    # Drop MAIN.nott_cryo_ctrl
    signal_parts = parts[2:stat_idx]
    if signal_parts and signal_parts[0] == "nott_temp":
        signal_parts = signal_parts[1:]
    if signal_parts:
        return f"cryo.{'.'.join(signal_parts)}.{field}"
    return f"cryo.{field}"


def load_sensor_config(path: str | Path) -> tuple[list[str], list[str]]:
    """Return (opc_node_ids, redis_keys) from sensors.ini."""
    opc_nodes: list[str] = []
    redis_keys: list[str] = []
    with open(path, encoding="utf-8") as sensors_file:
        for raw_line in sensors_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            opc_nodes.append(line)
            redis_keys.append(opc_node_to_redis_key(line))
    return opc_nodes, redis_keys
