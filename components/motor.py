from commands.move_abs_command import MoveAbsCommand
from commands.move_rel_command import MoveRelCommand

class Motor():
    def __init__(self, opcua_conn, opcua_prefix: str):
        self._opcua_conn = opcua_conn
        self._prefix = opcua_prefix
    
    def command_move_absolute(self, pos, speed) -> MoveAbsCommand:
        return MoveAbsCommand(self._opcua_conn, self._prefix, pos, speed)
    
    def command_move_relative(self, rel_pos, speed) -> MoveRelCommand:
        return MoveRelCommand(self._opcua_conn, self._prefix, rel_pos, speed)
    
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