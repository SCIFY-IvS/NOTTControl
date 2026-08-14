# Author: Thomas
"""
nott_utils.py
-------------
This file contains utilities for the control of motors on the NOTT bench, shared across the NOTT Control package.
All infrastructure for actuator control and timing is bundled here. No other file should have to overwrite these definitions.

Functions and classes
---------------------
unix_to_datetime: convert redis timestamp (ms) to UTC datetime object
datetime_to_id  : convert UTC datetime object to an ID string by which NOTT IR camera frames can be queried
MotorError      : OSError subclass for actuator errors
LayeredRegister : layered position accumulator (bench, tuning, sky ...)
Actuator        : Subclass of Motor for general backlash-corrected linear stages
                  Unit is micrometer throughout.
                  Base class for DelayLine and LDC classes
                  Used directly to initialize TTM Actuators in nott_TTM_alignment
ActuatorCluster : Offers simultaneous threaded motion over a list of Actuator objects
                  Can be constructed in two ways
                  1) __init__(motors) : direct initialization, used by nott_TTM_alignment
                  2) from_prefix(opcua_conn, prefix) : initialisation based on the config defaults for actuator type 'prefix'
                     Prefices: (Delay lines: 'air', ZNSe prisms: 'glass', CO2 cells: 'co2', birefringence plates: 'biref')
                     Used by the DelayLine and LDC subclasses

Imported by
-----------
nott_utils is imported by
- delayline.py (Actuator, ActuatorCLuster, MotorError)
- ldc.py (Actuator, ActuatorCLuster, MotorError)
- human_interface.py
- nott_TTM_alignment.py

"""

import time as _time
import threading
import numpy as np
from datetime import datetime, timedelta, timezone

from nottcontrol.components.motor import Motor
from nottcontrol import config as nott_config

simulation = False
if simulation:
    from nottcontrol.components.motor import MotorSim as Motor

# -----------------------#
# Timestamp conversions |
# -----------------------#


def unix_to_datetime(unix_stamp):
    # Converting unix_stamp (milliseconds since 01/01/1970 00:00:00) to a datetime object (time in UTC)
    epoch = datetime.fromtimestamp(0, timezone.utc)
    dt = timedelta(milliseconds=unix_stamp)
    utc_stamp = epoch + dt
    return utc_stamp


def datetime_to_id(utc_stamp):
    # Converting datetime object utc_stamp to frame_id (Y%m%d_H%M%S formatted string, date and time separated by an underscore)
    Ymd = utc_stamp.strftime("%Y%m%d")
    HMS = utc_stamp.strftime("%H%M%S%f")[:-3]
    frame_id = Ymd + "_" + HMS
    return frame_id


# ------------#
# MotorError |
# ------------#


class MotorError(OSError):
    pass


# -----------------#
# LayeredRegister |
# -----------------#


class LayeredRegister(object):
    """
    This class stores position contributions from multiple named sources as separate layers.
    The sum across all layers then gives back the total accumulated position.

    Params
    ------
    len: int
       Number of actuators, the length of each position vector.
    layers: int
       Number of layers, amount of position sources.

    """

    def __init__(self, len: int = 4, layers: int = 5):
        self._buff = [np.zeros(len) for i in range(layers)]
        self.layers = {"bench": 0, "tuning": 1, "sky": 2, "dcomp": 3, "manual": 4}

    def __repr__(self):
        return self._buff.__repr__()

    def __str__(self):
        return self._buff.__str__()

    def set(self, values: np.ndarray, layer: int | str = -1):
        # If the layer indicator is a string, we convert it
        # to an integer using the dictionary
        if isinstance(layer, str):
            layer = self.layers[layer]
        self._buff[layer] = values.astype(float)

    def get(self, layer: int | str = -1):
        if isinstance(layer, str):
            layer = self.layers[layer]
        return self._buff[layer]

    def purge(self, layer: int | str = -1):
        if isinstance(layer, str):
            layer = self.layers[layer]
        self._buff[layer] = np.zeros_like(self._buff[layer])

    def purge_all(self):
        for alayer in self._buff:
            alayer = np.zeros_like(alayer)

    def consolidate_layers(self, layers: list, destination: int | str = 0):
        """
        Takes the sum of layers indentified by `layers`, and writes them in
        the layer `destination`
        """
        mylayers = []
        topurge = []
        for i, alayer in enumerate(layers):
            if isinstance(alayer, str):
                alayer = self.layers[alayer]
            mylayers.append(self._buff[alayer])
            topurge.append(alayer)
        newvalues = np.array(mylayers).sum(axis=0)
        for alayer in topurge:
            self.purge(alayer)
        self.set(newvalues, layer=destination)

    @property
    def buff(self):
        return np.array(self._buff)

    @property
    def total(self):
        return np.array(self._buff).sum(axis=0)


# ----------#
# Actuator |
# ---------#


class Actuator(Motor):
    """
    General class for backlash-corrected linear stages.
    Base class for DelayLine, LDC actuators and TTM actuators.

    Positions and displacements are in um throughout.
    PLC expects mm, so move_abs does the conversion before calling command_move_absolute.

    Backlash correction is bi-directional and made direction-aware via the prev_dir field.
    Correction is carried out when the direction of the requested move differs from the previous move and the displacements exceeds deadband.
    The actuator retraces by {backlash} um in the direction of the requested move before making an accurate final approach.

    Parameters
    ----------
    opcua_conn : OPCUACOnnection
    opcua_prefix : str - OPCUA node prefix of actuator
    name : str - readable name of actuator
    speed : float - default motion speed (um/s)
    pos_min : float - lower travel limit (um). Defaults to 0.
    pos_max : float - upper travel limit (um). Defaults to 12500.
    backlash : float - retrace distance (um). Defaults to 4.
    deadband : float - minimal displacement to trigger a backlash correction (uim). Defaults to 0.02
    init_backlash : bool - if True, fire a retrace and return at actuator initialisation to establish a known direction state.
                           Defaults to False. Only set to True for the air delay lines.
    prev_dir : int - direction of last move. Defaults to 0. (unknown)

    """

    def __init__(
        self,
        opcua_conn,
        opcua_prefix: str,
        name: str,
        speed: float,
        pos_min: float = 0.0,
        pos_max: float = 12500.0,
        backlash: float = 4.0,
        deadband: float = 0.02,
        init_backlash: bool = False,
        prev_dir: int = 0,
    ):
        super().__init__(opcua_conn, opcua_prefix, name, speed)
        self.pos_min = pos_min
        self.pos_max = pos_max
        self.backlash = backlash
        self.deadband = deadband
        self.prev_dir = prev_dir
        self.ongoing_sequence = False

        if init_backlash:
            init_pos = self.position_microns
            # Move negative to neutralize backlash and establish direction. Make sure not to bump into lower limit.
            retrace_pos = max(init_pos - 3 * backlash, self.pos_min)
            self.move_sequence(retrace_pos, cp_backlash=False)
            # Return to initial position.
            self.move_sequence(init_pos, cp_backlash=True)

    # Status checks

    @property
    def position_microns(self):
        # Current position in um.
        return self.getPositionAndSpeed()[0] * 1000.0

    @property
    def target_microns(self):
        return self.getTargetPosition() * 1000.0

    @property
    def is_standing(self):
        status = self.getStatusInformation()[0]
        return status == "STANDING" or status == "Motor stopped - STANDING"

    @property
    def is_operational(self):
        # Motor sState == 'OPERATIONAL'?
        return self.getStatusInformation()[1] == "OPERATIONAL"

    @property
    def time_to_target(self):
        dist_to_go = self.target_microns - self.position_microns
        est = np.abs(dist_to_go) / self._speed
        return est

    # Validity checks

    def is_in_travel_range(self, target_pos=None):
        # Target position within [pos_min, pos_max]?
        # If no target specified, use current position
        if target_pos is None:
            target_pos = self.position_microns
        return self.pos_min <= target_pos <= self.pos_max

    def _valid_move(self, target_pos: float):
        # Is the imposed target position valid, i.e. within the travel range?
        if not self.is_in_travel_range(target_pos):
            raise ValueError(
                f"Target position {target_pos} um on {self.name} is"
                f" out of the travel range [{self.pos_min, self.pos_max}] um."
            )

    # Polling

    def await_motor(
        self, dt: float = 0.1, timeout: float = 30.0, verbose: bool = False
    ):
        if self.is_standing:
            return
        _time.sleep(0.2)
        t0 = _time.time()
        while _time.time() - t0 < timeout:
            if self.is_standing:
                return
            if verbose:
                dtg = self.target_microns - self.position_microns
                print(
                    f"  {self.name}: {_time.time() - t0:.1f} s, {dtg:.3f} µm to go",
                    end="\r",
                    flush=True,
                )
            _time.sleep(dt)

    # Motion

    def move_abs(self, target_pos: float, check_valid: bool = True):
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

    def move_rel(self, delta_pos: float, check_valid: bool = True):
        """
        Move by a relative distance delta_pos (um).
        """
        target_pos = self.position_microns + delta_pos
        if check_valid:
            self._valid_move(target_pos)
        self.command_move_relative(delta_pos * 1e-3).execute()

    def move_sequence(
        self,
        target_pos: float,
        check_valid: bool = True,
        cp_backlash: bool = True,
        dt: float = 0.1,
        timeout: float = 30.0,
        verbose: bool = False,
    ):
        """
        Function that moves actuator to target_pos (um) with bi-directional backlash correction.

        Correction fires only if cp_backlash is True AND
        the direction of the requested move differs from the previous move (self.prev_dir) AND
        the imposed displacement is larger than the deadband.

        Retraces by self.backlash (um) in the direction of the requested move, waits for arrival and then makes an accurate approach back.

        Updates self.prev_dir at the end of the move.

        Params
        ------
        target_pos : float (um)
        check_valid : bool - validate move against travel range
        cp_backlash : bool - apply bi-directional correction
        dt : float (s) - polling interval for await_motor
        timeout : float (s) - timeout for each sub move
        """
        timeout = np.max(timeout, self.time_to_target + 10.0)
        self.ongoing_sequence = True
        distance = target_pos - self.position_microns

        if abs(distance) < self.deadband:
            self.ongoing_sequence = False
            return

        curr_dir = int(np.sign(distance))
        need_cp = cp_backlash and curr_dir != self.prev_dir and self.prev_dir != 0

        if need_cp:
            retrace = self.position_microns + curr_dir * self.backlash
            self.move_abs(retrace, check_valid)
            _time.sleep(0.2)
            if verbose:
                print(f"  {self.name}: backlash → {retrace:.2f} µm")
            self.await_motor(dt=dt, timeout=timeout, verbose=verbose)

        self.move_abs(target_pos, check_valid)
        _time.sleep(0.2)
        if verbose:
            print(f"  {self.name}: → {target_pos:.1f} µm")
        self.await_motor(dt=dt, timeout=timeout, verbose=verbose)

        self.prev_dir = curr_dir
        self.ongoing_sequence = False

    def move_sequence_rel(self, rel_pos: float, **kwargs):
        """Move by rel_pos (um) relative to current position."""
        self.move_sequence(self.position_microns + rel_pos, **kwargs)


# -----------------#
# ActuatorCluster |
# -----------------#


def _get_actuator_args(prefix: str, i: int):
    """
    Build a dictionary of the keyword arguments used in the Actuator constructor for index i from config.ini [ldc].
    Function is generic as all four actuator types (air/glass/co2/biref) share the same key structure in config.ini.

    Parameters
    ----------
    prefix : str — 'air', 'glass', 'co2', or 'biref'
    i      : int — zero-based index
    """
    opcua_prefix = nott_config.config_parser.get("ldc", prefix + "_address")
    basename = nott_config.config_parser.get("ldc", prefix + "_name")
    return {
        "opcua_prefix": f"ns=4;s={opcua_prefix}.{basename}{i + 1}",
        "name": f"{basename}{i + 1}",
        "speed": nott_config.getfloat("ldc", prefix + "_speed"),
        "pos_min": nott_config.getfloat("ldc", prefix + "_pos_min"),
        "pos_max": nott_config.getfloat("ldc", prefix + "_pos_max"),
        "backlash": nott_config.getfloat("ldc", prefix + "_backlash"),
    }


class ActuatorCluster:
    """
    A cluster of Actuator objects. Supports simultaneous threaded motion and a layered position register.

    An ActuatorCluster can be constructed via two paths:
    1) Direct: pass a pre-built list of Actuator (or a subclass of Actuator) objects.
               used by nott_TTM_alignment.py for the TTM actuators.
               cluster = ActuatorCluster(motors=[act1, act2, act3, act4])
    2) Via configuration: use the from_prefix method with a given prefix to read the device addresses and parameters from config.ini [ldc].
                          used by the DelayLine and LDC subclasses.
                          cluster = ActuatorCluster.from_prefix(opcua_conn, 'air')

    All Actuator objects / subclasses must implement
    position_microns, is_standing, is_operational, move_sequence

    """

    def __init__(self, motors: list):
        self.motors = motors
        self.threads: list[threading.Thread] = []
        self.tbuff = LayeredRegister(len=len(motors), layers=5)

    @classmethod
    def from_prefix(cls, opcua_conn, prefix: str, init_backlash: bool = False):
        """
        Build an ActuatorCluster from config.ini [ldc] for the given
        prefix ('air', 'glass', 'co2', 'biref').

        Parameters
        ----------
        opcua_conn    : OPCUAConnection
        prefix        : str — prefix in config.ini ('air', 'glass', 'co2' or 'biref')
        init_backlash : bool — forwarded to each Actuator.__init__.
                               Only ever True for physical delay lines ('air'),
                               which are moved back and forth at startup to establish a known previous direction.
        """
        available = nott_config.getarray("ldc", prefix + "_idx_available", dtype=int)
        motors = [
            Actuator(
                opcua_conn, init_backlash=init_backlash, **_get_actuator_args(prefix, i)
            )
            for i in available
        ]
        return cls(motors)

    def __getitem__(self, key):
        return self.motors[key]

    def __len__(self):
        return len(self.motors)

    # STatus

    @property
    def position_microns(self):
        return np.array([m.position_microns for m in self.motors])

    @property
    def target_microns(self):
        return np.array([m.target_microns for m in self.motors])

    @property
    def is_standing(self):
        return np.array([m.is_standing for m in self.motors])

    @property
    def is_operational(self):
        return np.array([m.is_operational for m in self.motors])

    @property
    def state(self):
        """Return positions (um) of all Actuators in the cluster.
        Raise a MotorError if any motor is not ready."""
        positions = np.full(len(self.motors), np.nan)
        for i, m in enumerate(self.motors):
            if not m.is_operational:
                raise MotorError(f"{m.name} is not OPERATIONAL.")
            if not m.is_standing:
                raise MotorError(f"{m.name} is not STANDING.")
            positions[i] = m.position_microns
        return positions

    # Motion

    def move_abs_all(
        self,
        target_pos=None,
        cp_backlash: bool = True,
        verbose: bool = False,
        **move_sequence_kwargs,
    ):
        """
        Fire simultaneous moves on all actuators in the cluster, starting one thread for each.
        Does not block, combine with await_all() to guarantee completion.

        Parameters
        ----------
        target_pos : (N,) array (um)
            Pass np.nan to skip an actuator.
        cp_backlash : bool — forwarded to move_sequence.
        verbose     : bool — forwarded to move_sequence.
        **move_sequence_kwargs — other kwargs for move_sequence.
        """
        assert self.threads == [], "The threads were not finished. Call await_all()."
        if target_pos is None:
            target_pos = self.tbuff.total
        target_pos = np.asarray(target_pos, dtype=float)
        for motor, tgt in zip(self.motors, target_pos):
            if np.isnan(tgt):
                continue
            t = threading.Thread(
                target=motor.move_sequence,
                kwargs=dict(
                    target_pos=tgt,
                    cp_backlash=cp_backlash,
                    verbose=verbose,
                    **move_sequence_kwargs,
                ),
            )
            self.threads.append(t)
        for t in self.threads:
            t.start()

    def await_all(self):
        """Block until all fired move thread are complete."""
        for t in self.threads:
            t.join()
        self.threads = []

    def move_abs_all_sync(
        self,
        target_pos: np.ndarray,
        cp_backlash: bool = True,
        verbose: bool = False,
        **move_sequence_kwargs,
    ):
        """move_abs_all + await_all in one call."""
        self.move_abs_all(
            target_pos, cp_backlash=cp_backlash, verbose=verbose, **move_sequence_kwargs
        )
        self.await_all()
