"""Load cryostat sensor OPC UA nodes and map them to Redis TimeSeries keys."""
from __future__ import annotations

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
    """Build a short Redis TS key from a cryo OPC UA node identifier line.

    Example
    -------
    NS4|String|MAIN.nott_cryo_ctrl.nott_temp.t_detector.stat.lrTempK
    -> cryo.t_detector.lrTempK
    """
    path = opc_node_path(opc_node)
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
