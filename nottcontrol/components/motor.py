from nottcontrol.commands.move_abs_command import MoveAbsCommand
from nottcontrol.commands.move_rel_command import MoveRelCommand

class Motor():
    def __init__(self, opcua_conn, opcua_prefix: str, name: str, speed: int):
        self._opcua_conn = opcua_conn
        self._prefix = opcua_prefix
        self.name = name
        self._speed = speed
    
    def command_move_absolute(self, pos) -> MoveAbsCommand:
        #Unit conversion as the PLC expects mm/s
        return MoveAbsCommand(self._opcua_conn, self._prefix, pos, self._speed * 10**(-3))
    
    def command_move_relative(self, rel_pos) -> MoveRelCommand:
        #Unit conversion as the PLC expects mm/s
        return MoveRelCommand(self._opcua_conn, self._prefix, rel_pos, self._speed * 10**(-3))
    
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
    
    def getPositionAndSpeed(self):
        current_pos, current_speed, timestamp = self._opcua_conn.read_nodes([f"{self._prefix}.stat.lrPosActual", f"{self._prefix}.stat.lrVelActual", 
                                                                              "ns=4;s=INFRATEC_TRIGERS.sNTPExtTime"])
        return (current_pos, current_speed, timestamp)
    
    def getStatusInformation(self):
        status, state, substate = self._opcua_conn.read_nodes([f"{self._prefix}.stat.sStatus", f"{self._prefix}.stat.sState", f"{self._prefix}.stat.sSubstate"])
        return (status, state, substate)
    
    def getTargetPosition(self):
        pos = self._opcua_conn.read_node(f"{self._prefix}.ctrl.lrPosition")
        return pos
    
    def getInitialized(self):
        init = self._opcua_conn.read_node(f"{self._prefix}.stat.bInitialised")
        return init
