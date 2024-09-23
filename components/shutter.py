class Shutter():
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
        hwStatus, timestamp = self._opcua_conn.read_nodes([f"{self._prefix}.stat.sHwStatus", "ns=4;s=INFRATEC_TRIGERS.NottTime.stat.sSystemTime"])
        return (hwStatus, timestamp)