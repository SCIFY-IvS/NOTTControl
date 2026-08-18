from nottcontrol.commands.move_abs_command import MoveAbsCommand, MoveAbsCommandSim
from nottcontrol.commands.move_rel_command import MoveRelCommand, MoveRelCommandSim
from nottcontrol.components.device_polling import NTP_EXT_TIME_NODE


class Motor:
    def __init__(self, opcua_conn, opcua_prefix: str, name: str, speed: float):
        self._opcua_conn = opcua_conn
        self._prefix = opcua_prefix
        self.name = name
        self._speed = speed

    def command_move_absolute(self, pos, speed=None) -> MoveAbsCommand:
        if speed is not None:
            spd = speed
        else:
            spd = self._speed
        # Unit conversion as the PLC expects mm/s
        return MoveAbsCommand(self._opcua_conn, self._prefix, pos, spd * 10 ** (-3))

    def command_move_relative(self, rel_pos, speed=None) -> MoveRelCommand:
        if speed is not None:
            spd = speed
        else:
            spd = self._speed
        # Unit conversion as the PLC expects mm/s
        return MoveRelCommand(self._opcua_conn, self._prefix, rel_pos, spd * 10 ** (-3))

    def reset(self):
        return self._opcua_conn.execute_rpc(self._prefix, "4:RPC_Reset", [])

    def init(self):
        return self._opcua_conn.execute_rpc(self._prefix, "4:RPC_Init", [])

    def enable(self):
        return self._opcua_conn.execute_rpc(self._prefix, "4:RPC_Enable", [])

    def disable(self):
        return self._opcua_conn.execute_rpc(self._prefix, "4:RPC_Disable", [])

    def stop(self):
        return self._opcua_conn.execute_rpc(self._prefix, "4:RPC_Stop", [])

    def getPositionAndSpeed(self, ntp_timestamp=None):
        if ntp_timestamp is None:
            current_pos, current_speed, timestamp = self._opcua_conn.read_nodes(
                [
                    f"{self._prefix}.stat.lrPosActual",
                    f"{self._prefix}.stat.lrVelActual",
                    NTP_EXT_TIME_NODE,
                ]
            )
        else:
            current_pos, current_speed = self._opcua_conn.read_nodes(
                [
                    f"{self._prefix}.stat.lrPosActual",
                    f"{self._prefix}.stat.lrVelActual",
                ]
            )
            timestamp = ntp_timestamp
        return (current_pos, current_speed, timestamp)

    def getStatusInformation(self):
        status, state, substate = self._opcua_conn.read_nodes(
            [
                f"{self._prefix}.stat.sStatus",
                f"{self._prefix}.stat.sState",
                f"{self._prefix}.stat.sSubstate",
            ]
        )
        return (status, state, substate)

    def getTargetPosition(self):
        pos = self._opcua_conn.read_node(f"{self._prefix}.ctrl.lrPosition")
        return pos

    def getInitialized(self):
        init = self._opcua_conn.read_node(f"{self._prefix}.stat.bInitialised")
        return init


class MotorSim(Motor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_pos = 0.0
        self.current_speed = 0.0
        self.timestamp = 0.0
        self.status = "STANDING"
        self.state = "OPERATIONAL"

    def command_move_absolute(self, pos, speed=None) -> MoveAbsCommand:
        pos = self.current_pos
        if speed is not None:
            spd = speed
        else:
            spd = self._speed
        # Unit conversion as the PLC expects mm/s
        return MoveAbsCommandSim(self._opcua_conn, self._prefix, pos, spd * 10 ** (-3))

    def command_move_relative(self, rel_pos, speed=None) -> MoveRelCommandSim:
        if speed is not None:
            spd = speed
        else:
            spd = self._speed
        # Unit conversion as the PLC expects mm/s
        return MoveRelCommandSim(
            self._opcua_conn, self._prefix, rel_pos, spd * 10 ** (-3)
        )

    def reset(self):
        pass

    def init(self):
        pass

    def enable(self):
        pass

    def disable(self):
        pass

    def stop(self):
        pass

    def getPositionAndSpeed(self):
        return self.current_pos, self.current_speed, self.timestamp

    def getStatusInformation(self):
        return self.status, self.state, None

    def getTargetPosition(self):
        return self.current_pos

    def getInitialized(self):
        return True
