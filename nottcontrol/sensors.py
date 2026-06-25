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
    """Use the asyncua OPC UA node id as the Redis TimeSeries key."""
    return opc_node_to_asyncua_id(opc_node)


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
