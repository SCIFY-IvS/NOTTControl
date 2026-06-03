import numpy as np
from time import sleep, time
from nottcontrol.components.motor import Motor
from nottcontrol import config
import threading
from numpy.typing import ArrayLike



class DelayLine(Motor):
    """
       Wrapper of the Motor class for delay lines.
        - Provides readout of the status of the delay line
        - Provides absolute and relative move calls
        - Provides validity checks upon moves, remaining within the travel range.
    """

    def __init__(self, opcua_conn, opcua_prefix: str, name: str,
                 speed: float = None, pos_min: float = 0.0,
                 pos_max: float = 12500.0,
                 backlash=4.0):
        """
        Params
        ------
        opcua_conn : OPCUA connection address, see config
        opcua_prefix : Delay line OPCUA name ("ns=4;s=MAIN.nott_ics.Delay_Lines.NDL2")
        name : Delay line name ("NDL2")
        speed : Travel speed (um/s)
                - converted to mm/s upon move calls
                - defaults to value in config.ini
        pos_min : lower bound of travel range (µm)
                - defaults to 0.0
        pos_max : upper bound of travel range (µm)
                - defaults to 12500.0 (CMA12PP open-loop stepper CMA actuator)
        """
        if speed is None:
            speed = float(config.getint('DL', 'default_speed'))
        super().__init__(opcua_conn, opcua_prefix, name, speed)
        self.pos_min = pos_min
        self.pos_max = pos_max
        self.backlash = backlash
        self.ongoing_sequence = False

    # Status checks

    @property
    def position_microns(self):
        # Current position in um.
        return self.getPositionAndSpeed()[0]*1000.

    @property
    def is_standing(self):
        # Motor sStatus == 'STANDING'?
        return self.getStatusInformation()[0] == 'STANDING'

    def await_motor(self, dt=0.1, timeout=10., initial=None, verbose=True):
        if self.is_standing:
            return
        thetarget = self.target_microns
        wait_start = time()
        while time() < wait_start + timeout:
            if self.is_standing:
                return
            else:
                if verbose:
                    position = self.position_microns
                    distance_to_go = self.target_microns - position
                    message = f"Waiting for {self.name} : {time() - wait_start :.1f}, {distance_to_go:.3f}: "
                    print("                                    ", end="\r")
                    print(message, end="\r", flush=True)
                sleep(dt)

    @property
    def target_microns(self):
        return self.getTargetPosition() * 1000.

    @property
    def time_to_target(self):
        if self.is_standing:
            est = 0.
        else:
            dist_to_go = self.target_microns - self.position_microns
            est = np.abs(dist_to_go) / self._speed
        return est

    @property
    def is_operational(self):
        # Motor sState == 'OPERATIONAL'?
        return self.getStatusInformation()[1] == 'OPERATIONAL'

    def is_in_travel_range(self, target_pos: float = None):
        # Target position within [pos_min, pos_max]?
        # If no target specified, use current position
        if target_pos is None:
            target_pos = self.position_microns
        return self.pos_min <= target_pos <= self.pos_max

    # Motion control

    def _valid_move(self, target_pos: float):
        # Is the imposed target position valid, i.e. within the travel range?
        if not self.is_in_travel_range(target_pos):
            raise ValueError(f"Target position {target_pos} um on {self.name} is"
                             f" out of the travel range [{self.pos_min, self.pos_max}] um.")

    def move_sequence(self, target_pos: float, check_valid: bool= True,
                    cp_backlash=True,
                    dt=0.1, timeout=10., initial=None, verbose=False):
        self.ongoing_sequence = True
        need_cp = not (target_pos - self.getPositionAndSpeed()[0]) > 0
        if need_cp and cp_backlash:
            self.move_abs(self.position_microns - self.backlash)
            self.await_motor(dt=dt, timeout=timeout, verbose=verbose)
        self.move_abs(target_pos)
        self.await_motor(dt=dt, timeout=timeout, verbose=verbose)

        self.ongoing_sequence = False

    def move_sequence_rel(self, rel_pos: float, check_valid: bool= True,
                    cp_backlash=True):
        target_pos = self.positio_microns + rel_pos
        
        

    def move_abs(self, target_pos: float, check_valid: bool= True):
        """
        Move to absolute position target_pos (um). 

        Args:
            target_pos : [µm]
            check_valid : (True) Verify validity of the command (bool)
            cp_backlash : (True) Compensate the backlash (bool)
        
        """
        if check_valid:
            self._valid_move(target_pos)
        self.command_move_absolute(target_pos * 1e-3).execute()

    def move_rel(self, delta_pos: float, check_valid: bool= True):
        """
            Move by a relative distance delta_pos (um).
        """
        target_pos = self.position_microns + delta_pos
        if check_valid:
            self._valid_move(target_pos)
        self.command_move_relative(delta_pos * 1e-3).execute()

# def DL_args(i):
#     prefix = "air"
#     output = {
#         "opcua_prefix": f"ns=4;s=MAIN.nott_ics.Delay_Lines.NDL{i+1}",
#         "name":f"NDL{i+1}",
#         "speed": 1e-3 * config.getfloat("ldc", prefix+"_speed"),
#         "pos_min": config.getfloat("ldc", prefix+"_pos_min"),
#         "pos_max": config.getfloat("ldc", prefix+"_pos_max"),
#         "backlash": config.getfloat("ldc", prefix+"_backlash"),
#         "available": config.getarray("ldc", prefix+"_idx_available", dtype=int),
#     }
#     return output

# def CO2_args(i):
#     prefix = "co2"
#     opcua_prefix = config.get("ldc", prefix+"_address")
#     basename = config.get("ldc", prefix+"_name")
#     output = {
#         "opcua_prefix": f"ns=4;s=MAIN.nott_ics.Delay_Lines.NDL{i+1}",
#         "opcua_prefix": f"ns=4;s={opcua_prefix}.{basename}",
#         "name":f"NDL{i+1}",
#         "speed": 1e-3 * config.getfloat("ldc", prefix+"_speed"),
#         "pos_min": config.getfloat("ldc", prefix+"_pos_min"),
#         "pos_max": config.getfloat("ldc", prefix+"_pos_max"),
#         "backlash": config.getfloat("ldc", prefix+"_backlash"),
#         "available": config.getarray("ldc", prefix+"_idx_available", dtype=int),
#     }
#     return output

# def glass_args(i):
#     prefix = "glass"
#     output = {
#         "opcua_prefix": f"ns=4;s=MAIN.nott_ics.Delay_Lines.NDL{i+1}",
#         "name":f"NDL{i+1}",
#         "speed": 1e-3 * config.getfloat("ldc", prefix+"_speed"),
#         "pos_min": config.getfloat("ldc", prefix+"_pos_min"),
#         "pos_max": config.getfloat("ldc", prefix+"_pos_max"),
#         "backlash": config.getfloat("ldc", prefix+"_backlash"),
#         "available": config.getarray("ldc", prefix+"_idx_available", dtype=int),
#     }
#     return output

def get_motor_args(prefix, i):
    """
    Args:
        prefix : either co2, glass, air
        i : index starting at 0
    """
    opcua_prefix = config.config_parser.get("ldc", prefix+"_address")
    basename = config.config_parser.get("ldc", prefix+"_name")
    output = {
        "opcua_prefix": f"ns=4;s={opcua_prefix}.{basename}",
        "name":f"{basename}{i+1}",
        "speed": 1e-3 * config.getfloat("ldc", prefix+"_speed"),# speed in mm/s in config
        "pos_min": config.getfloat("ldc", prefix+"_pos_min"),
        "pos_max": config.getfloat("ldc", prefix+"_pos_max"),
        "backlash": config.getfloat("ldc", prefix+"_backlash"),
    }
    return output

class MotorError(OSError):
    pass

class ActuatorCluster(object):
    def __init__(self, opcua_conn, prefix,
                ):
        self.opcua_conn = opcua_conn
        available = config.getarray("ldc", prefix+"_idx_available", dtype=int),
        self.motors = [
            DelayLine(self.opcua_conn,
                      get_motor_args(prefix, i))
                                for i in available
        ]
        self.threads = []

    def __getitem__(self, key):
        return self.motors[key]

    def __len__(self):
        return len(self.motors)

    @property
    def position_microns(self):
        return np.array([amotor.mosition_microns for amotor in self.motors])

    @property
    def is_standing(self):
        return np.array([amotor.is_standing for amotor in self.motors])

    @property
    def state(self):
        positions = np.nan * np.zeros(len(self.delay_lines))

        for i, amotor in enumerate(self.motors):
            if not amotor.is_operational:
                raise MotorError(f"Delay line {amotor.name} is not in OPERATIONAL state.")
            if not amotor.is_standing:
                raise MotorError(f"Delay line {amotor.name} is not in STANDING status.")
            positions[i] = amotor.position_microns

    @property
    def is_operational(self):
        return np.array([amotor.is_operational for amotor in self.motors])

    def is_valid(self, target_pos: float):
        return np.array([amotor._valid_move(apos)\
                             for amotor, apos in zip(self.motors, target_pos)])

    @property
    def target_microns(self):
        return np.array([amotor.target_microns for amotor in self.motors])


    def move_abs_all(self, target_pos: ArrayLike,
                    check_valid: bool= True,
                    cp_backlash=True,
                    dt=0.1,
                    timeout=10.,
                    initial=None,
                    verbose=False):
        assert self.threads == [], "The threads were not finished"
        for i, amotor in enumerate(self.motors):
            kwargs = {"target_pos":target_pos[i],
                        "check_valid":check_valid,
                        "dt":dt,
                        "timeout":timeout,
                        "verbose=":verbose
                    }
            t = threading.Thread(target=amotor.move_abs, kwargs=kwargs)
            self.threads.append(t)
        for t in self.threads:
            t.start()

    def await_all(self):
        for t in self.threads():
            t.join()
        self.threads = []

    def move_abs_one(self, target, cp_backlash=True):
        pass


class NOTT_LDC(object):
    def __init__(self):
        self.air_length
        self.air_eq_index
        self.co2_ppm
        self.co2_length
        self.co2_eq_index
        self.glass_length
        self.glass_eq_index
    

