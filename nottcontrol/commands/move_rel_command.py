from nottcontrol.commands.async_command import AsyncCommand

class MoveRelCommand(AsyncCommand):
    def __init__(self, opcua_conn, opcua_prefix, rel_pos, speed):
        self._opcua_conn = opcua_conn
        self._opcua_prefix = opcua_prefix
        self._rel_pos = rel_pos
        self._speed = speed

    def execute(self):
         self._opcua_conn.execute_rpc(self._opcua_prefix, "4:RPC_MoveRel", [self._rel_pos,self._speed])
    
    def text(self):
        return "Move relative"
    
    def check_progress(self):
        status, state = self._opcua_conn.read_nodes([f"{self._opcua_prefix}.stat.sStatus", f"{self._opcua_prefix}.stat.sState"])

        return (status == 'STANDING' and state == 'OPERATIONAL')

class MoveRelCommandSim(MoveRelCommand):
    def execute(self):
        print(f"Simulating MoveAbsCommand to {self._target_pos} at speed {self._speed}")    
        self.st
    def check_progress(self):
        print("Simulate checking status")
        return (True, True)
