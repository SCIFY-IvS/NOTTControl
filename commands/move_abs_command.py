from opcua import OPCUAConnection
from commands.async_command import AsyncCommand

class MoveAbsCommand(AsyncCommand):
    def __init__(self, opcua_conn, target_pos, speed):
        self._opcua_conn = opcua_conn
        self._target_pos = target_pos
        self._speed = speed

    def execute(self):
         self._opcua_conn.execute_rpc("ns=4;s=MAIN.DL_Servo_1", "4:RPC_MoveAbs", [self._target_pos,self._speed])
    
    def text(self):
        return "Move absolute"
    
    def check_progress(self):
        status, state = self._opcua_conn.read_nodes(["ns=4;s=MAIN.DL_Servo_1.stat.sStatus", "ns=4;s=MAIN.DL_Servo_1.stat.sState"])

        return (status == 'STANDING' and state == 'OPERATIONAL')
