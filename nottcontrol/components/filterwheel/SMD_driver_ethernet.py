import socket
import time
from datetime import datetime

#Communication protocol is described here: https://bookstack.vps-da8d40f3.arunmicro.com/books/smd4-user-manual/page/communications-protocol
# We always assume the motor is driven in unit 'steps'!
class SMD_driver_ethernet:
    def __init__(self, ip, port=11312):
        self.ip = ip
        self.port = port

        #Check the connection
        self.get_status()
    
    def _send_message(self, msg):
        #For now, create and destroy the socket for each message
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((self.ip, self.port))
            print(f"Sending message: {msg}")
            s.sendall(msg.encode())
            #TODO: is there a better way to ensure we wait long enough to get an answer?
            time.sleep(1)
            answer = s.recv(1024).decode()
        
        print(f"Answer: {answer}")
        return answer
    
    def _send_and_parse_message(self, msg):
        # See documentation at https://bookstack.vps-da8d40f3.arunmicro.com/books/smd4-user-manual/page/communications-protocol
        # Responses are in the form <address prefix>,<SFLAGS>,<EFLAGS>,<data 1>,<data 2>,<data n>…<CR><LF>
        # address prefix is optional, and we assume it is not used
        # Error response is <address prefix>,<SFLAGS>,<EFLAGS>,<error code><CR><LF>

        answer = self._send_message(msg)
        answer = answer.removesuffix("\r\n")

        if answer == "":
            #It seems that when the connection is held by another source, we can still connect the socket, but there is no reply
            raise Exception("No answer received - please check if the connection to the filterwheel is held by another source")

        tokens = answer.split(",")
        flags = tokens[0]
        self.status = flags
        eflags = tokens[1]
        self.estatus = eflags
        results = tokens[2:]
        # For now, ignore the flags and return the result

        if len(results) > 0 and results[0].startswith("ERR"):
            raise Exception(f"Exception from filterwheel: {results[0]}")
        return results
    
    def get_position(self):
        pos_string = self._send_and_parse_message(f"MOTOR:PACT\r\n")[0]
        return float(pos_string)

    def set_position(self, pos):
        return self._send_and_parse_message(f"MOTOR:PACT,{pos}\r\n")
    
    #Untested
    def move_relative(self, steps:int):
        message = f"MCON:RUNR,{steps}\r\n"
        self._send_and_parse_message(message)
    
    def move_absolute_steps(self, steps:int):
        message = f"MCON:RUNA,{steps}\r\n"
        self._send_and_parse_message(message)

    def move_to_spectrograph_pos(self):
        """Move to spectrograph position - filterwheel must be properly homed"""
        self.move_absolute_steps(0)
    
    def move_to_open_pos(self):
        """Move to open position - filterwheel must be properly homed"""
        self.move_absolute_steps(40)
    
    def move_to_closed_pos(self):
        """Move to closed position - filterwheel must be properly homed"""
        self.move_absolute_steps(80)
    
    def move_to_home(self, direction:bool = True):
        dir = '+' if direction else '-'
        self._send_and_parse_message(f"MCON:RUNH,{dir}\r\n")
    
    def stop(self):
        self._send_and_parse_message(f"MCON:STOP\r\n")
    
    #Untested
    def set_speed(self, speed:float):
        #TODO
        #Set speed of the motor, in degrees/s
        self._send_and_parse_message(f"MOTOR:VMAX,{speed}\r\n")
    
    def set_acceleration(self, acc:float):
        #TODO
        #Set acceleration in steps/s
        return
    
    #Untested
    def set_mode(self, mode:int):
        #Set the operation mode
        # 0:Step/direction
        # 1: Normal
        # 3: Bake
        self._send_and_parse_message(f"SYS:MODE,{mode}\r\n")
    
    def get_readable_status(self):
        return self._send_message("SYS:FLAGSV\r\n")
    
    def get_status(self):
        return self._send_and_parse_message("SYS:FLAGS\r\n")
    
    def get_uptime(self):
        #Unit is ms
        uptime_str = self._send_and_parse_message("SYS:UPTIME\r\n")[0]
        return int(uptime_str)
    
    def get_temperature(self):
        #Unit is degrees Celcius
        temp_str = self._send_and_parse_message("MOTOR:T\r\n")[0]
        return float(temp_str)
    
    def get_acceleration_current(self):
        #Unit is A
        current_str = self._send_and_parse_message("MOTOR:IA\r\n")[0]
        return float(current_str)

    def get_hold_current(self):
        #Unit is A
        current_str = self._send_and_parse_message("MOTOR:IH\r\n")[0]
        return float(current_str)

    def get_run_current(self):
        #Unit is A
        current_str = self._send_and_parse_message("MOTOR:IR\r\n")[0]
        return float(current_str)
    
    def get_target_speed(self):
        #Unit is step/s
        speed_str = self._send_and_parse_message("MOTOR:VMAX\r\n")[0]
        return float(speed_str)
    
    def get_start_speed(self):
        #Unit is step/s
        speed_str = self._send_and_parse_message("MOTOR:VSTART\r\n")[0]
        return float(speed_str)
    
    def get_stop_speed(self):
        #Unit is step/s
        speed_str = self._send_and_parse_message("MOTOR:VSTOP\r\n")[0]
        return float(speed_str)
    
    def get_acceleration(self):
        #Unit is step/s2
        acc_str = self._send_and_parse_message("MOTOR:AMAX\r\n")[0]
        return float(acc_str)

    def get_deceleration(self):
        #Unit is step/s2
        dec_str = self._send_and_parse_message("MOTOR:DMAX\r\n")[0]
        return float(dec_str)
    
    #For troubleshooting only; unit should be "steps" (0)
    def get_units(self):
        unit_str = self._send_and_parse_message("SYS:UNITS\r\n")[0]
        return int(unit_str)
    
    #Should trigger error
    def get_unit(self):
        return self._send_and_parse_message("SYS:UNIT\r\n")
    
    def get_global_limit_switch(self):
        state_str = self._send_and_parse_message("LIMIT:EN\r\n")[0]
        return state_str == "1"
    
    def get_positive_limit_switch(self):
        state_str = self._send_and_parse_message("LIMIT:EN+\r\n")[0]
        return state_str == "1"

    def toggle_global_limit_switch(self, val):
        val_int = 1 if val else 0
        return self._send_and_parse_message(f"LIMIT:EN,{val_int}\r\n")[0]
    
    def toggle_positive_limit_switch(self, val):
        val_int = 1 if val else 0
        return self._send_and_parse_message(f"LIMIT:EN+,{val_int}\r\n")[0]
    
    #Testing not finished, as there was a problem with the limit switch
    def run_homing_procedure(self):
        if not self.get_global_limit_switch():
            self.toggle_global_limit_switch(True)
        if not self.get_positive_limit_switch():
            self.toggle_positive_limit_switch(True)
        
        self.move_to_home()

        start = datetime.now()
        #Wait until in position
        while(True):
            time.sleep(1)
            if self.is_limit_positive_active():
                break
            
            if (datetime.now() - start).total_seconds() > 10:
                self.stop()
                raise Exception("Not homed after 10s - stop waiting")
        
        #Ok, we are now at home position
        self.toggle_global_limit_switch(False)
        self.set_position(0)

    
    def is_limit_positive_active(self):
        self.get_status()
        #Extract bit 2 from status

        int_status = int(self.status, 16)
        b_status = "{0:016b}".format(int_status)
        #bits are in reverse order, so check bit 2 starting from the end of the string
        return b_status[15-2] == "1"
