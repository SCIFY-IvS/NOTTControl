from opcua import OPCUAConnection
from commands.async_command import AsyncCommand

class MoveRelCommand(AsyncCommand):
    def __init__(self, opcua_conn, rel_pos, speed):
        self._opcua_conn = opcua_conn
        self._rel_pos = rel_pos
        self._speed = speed

    def execute(self):
         self._opcua_conn.execute_rpc("ns=4;s=MAIN.DL_Servo_1", "4:RPC_MoveRel", [self._rel_pos,self._speed])
    
    def text(self):
        return "Move relative"
    
    def check_progress(self):
        status, state = self._opcua_conn.read_nodes(["ns=4;s=MAIN.DL_Servo_1.stat.sStatus", "ns=4;s=MAIN.DL_Servo_1.stat.sState"])

        return (status == 'STANDING' and state == 'OPERATIONAL')