import numpy as np
from nottcontrol.components.motor import Motor

class Shutter_Old():
    def __init__(self, opcua_conn, opcua_prefix: str, name: str):
        self._opcua_conn = opcua_conn
        self._prefix = opcua_prefix
        self.name = name
    
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
    
    def open(self):
        return self._opcua_conn.execute_rpc(self._prefix, "4:RPC_Open", [])
    
    def close(self):
        return self._opcua_conn.execute_rpc(self._prefix, "4:RPC_Close", [])

    def getStatusInformation(self):
        status, state, substate = self._opcua_conn.read_nodes([f"{self._prefix}.stat.sStatus", f"{self._prefix}.stat.sState", f"{self._prefix}.stat.sSubstate"])
        return (status, state, substate)
    
    def getHardwareStatus(self):
        hwStatus, timestamp = self._opcua_conn.read_nodes([f"{self._prefix}.stat.sHwStatus",  "ns=4;s=INFRATEC_TRIGERS.sNTPExtTime"])
        return (hwStatus, timestamp)
    
class Shutter(Motor):
    def __init__(self, opcua_conn, opcua_prefix: str, name: str, speed:float, open_pos:float, close_pos:float, rtol=0.02):
        super().__init__(opcua_conn, opcua_prefix, name, speed)
        self._open_pos = open_pos
        self._close_pos = close_pos
        self.rtol = 0.02 # relative tolerance for is_open / is_closed
    
    def open(self):
        self.command_move_absolute(self._open_pos).execute()
    
    def close(self):
        self.command_move_absolute(self._close_pos).execute()
        
    @property
    def is_open(self):
        pos = self.getPositionAndSpeed()[0]
        return np.isclose(pos,self._open_pos,self.rtol) 
    
    @property
    def is_closed(self):
        pos = self.getPositionAndSpeed()[0]
        return np.isclose(pos,self._close_pos,self.rtol)
        
        
        