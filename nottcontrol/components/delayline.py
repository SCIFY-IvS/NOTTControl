import numpy as np
from time import sleep, time
from nottcontrol.components.motor import Motor
from nottcontrol import config

class DelayLine(Motor):
    """
       Wrapper of the Motor class for delay lines.
        - Provides readout of the status of the delay line
        - Provides absolute and relative move calls
        - Provides validity checks upon moves, remaining within the travel range.
    """

    def __init__(self, opcua_conn, opcua_prefix: str, name: str,
                 speed: float = None, pos_min: float = 0.0, pos_max: float = 6.0):
        """
        Params
        ------
        opcua_conn : OPCUA connection address, see config
        opcua_prefix : Delay line OPCUA name ("ns=4;s=MAIN.nott_ics.Delay_Lines.NDL2")
        name : Delay line name ("NDL2")
        speed : Travel speed (um/s)
                - converted to mm/s upon move calls
                - defaults to value in config.ini
        pos_min : lower bound of travel range (um)
                - defaults to 0.0
        pos_max : upper bound of travel range (um)
                - defaults to 6000.0 
        """
        if speed is None:
            speed = config.getint('DL', 'default_speed')
        super().__init__(opcua_conn, opcua_prefix, name, speed)
        self.pos_min = pos_min
        self.pos_max = pos_max

    # Status checks

    @property
    def position(self):
        # Current position in um.
        return self.getPositionAndSpeed()[0]*1000

    @property
    def is_standing(self):
        # Motor sStatus == 'STANDING'?
        return self.getStatusInformation()[0] == 'STANDING'

    @property
    def is_operational(self):
        # Motor sState == 'OPERATIONAL'?
        return self.getStatusInformation()[1] == 'OPERATIONAL'

    def is_in_travel_range(self, target_pos: float = self.position):
        # Target position within [pos_min, pos_max]?
        # If no target specified, use current position
        return self.pos_min <= target_pos <= self.pos_max

    # Motion control

    def _valid_move(self, target_pos: float):
        # Is the imposed target position valid, i.e. within the travel range?
        if not self.is_in_travel_range(target_pos):
            raise ValueError(f"Target position {target_pos} um on {self.name} is
                             out of the travel range [{self.pos_min, self.pos_max}] um.")

    def move_abs(self, target_pos: float, check_valid: bool= True):
        """
           Move to absolute position target_pos (um). 
        """
        if check_valid:
            self._valid_move(target_pos)
        self.command_move_absolute(target_pos).execute()

    def move_rel(self, delta_pos: float, check_valid: bool= True):
        """
            Move by a relative distance delta_pos (um).
        """
        target_pos = self.position + delta_pos
        if check_valid:
            self._valid_move(target_pos)
        self.command_move_relative(delta_pos).execute()

    
