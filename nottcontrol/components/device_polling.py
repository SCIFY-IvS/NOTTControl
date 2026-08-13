"""Batched OPC UA reads for motor and shutter control windows."""

NTP_EXT_TIME_NODE = "ns=4;s=INFRATEC_TRIGERS.sNTPExtTime"


def motor_status_opc_nodes(prefixes: list[str]) -> list[str]:
    nodes: list[str] = []
    for prefix in prefixes:
        nodes.extend(
            [
                f"{prefix}.stat.sStatus",
                f"{prefix}.stat.sState",
                f"{prefix}.stat.sSubstate",
                f"{prefix}.ctrl.lrPosition",
            ]
        )
    return nodes


def motor_position_opc_nodes(prefixes: list[str], *, include_ntp: bool = True) -> list[str]:
    nodes: list[str] = []
    for prefix in prefixes:
        nodes.extend(
            [
                f"{prefix}.stat.lrPosActual",
                f"{prefix}.stat.lrVelActual",
            ]
        )
    if include_ntp:
        nodes.append(NTP_EXT_TIME_NODE)
    return nodes


def split_motor_status_values(values: list, motor_count: int) -> list[tuple]:
    rows: list[tuple] = []
    for index in range(motor_count):
        base = index * 4
        rows.append(tuple(values[base : base + 4]))
    return rows


def split_motor_position_values(
    values: list, motor_count: int, *, include_ntp: bool = True
) -> list[tuple]:
    ntp = values[-1] if include_ntp else None
    position_values = values[: motor_count * 2]
    rows: list[tuple] = []
    for index in range(motor_count):
        base = index * 2
        rows.append((position_values[base], position_values[base + 1], ntp))
    return rows


def shutter_status_opc_nodes(prefixes: list[str]) -> list[str]:
    nodes: list[str] = []
    for prefix in prefixes:
        nodes.extend(
            [
                f"{prefix}.stat.sStatus",
                f"{prefix}.stat.sState",
                f"{prefix}.stat.sSubstate",
                f"{prefix}.stat.lrPosActual",
            ]
        )
    return nodes


def split_shutter_status_values(values: list, shutter_count: int) -> list[tuple]:
    rows: list[tuple] = []
    for index in range(shutter_count):
        base = index * 4
        rows.append(tuple(values[base : base + 4]))
    return rows
