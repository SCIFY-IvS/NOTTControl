# Author: Thomas
"""
delayline.py
------------
Wrapper of the ActuatorCluster class, specifically tailored for air delay lines (OPD control) for the NOTT instrument.

Classes
-------
DelayLine(ActuatorCluster)
    Cluster of four air OPD delay lines (NDL1-4), built from parameters in config.ini [ldc] - prefix 'air'.
    All motion control logic lives in nottcontrol/script/lib/nott_utils.py: Actuator, ActuatorCluster, LayeredRegister, MotorError, _get_actuator_args).

"""

from nottcontrol.opcua import OPCUAConnection
from nottcontrol.script.lib.nott_utils import (
    Actuator,
    ActuatorCluster,
    LayeredRegister,
    MotorError,
)


class DelayLine(ActuatorCluster):
    """
    A cluster of NOTT air OPD delay lines (NDL1-4).

    Construction reads the device addresses, travel range, speed and backlash from config.ini [ldc] - prefix 'air'.
    A backlash initialisation sequence is fired at the startup of each Actuator to establish a known direction state.

    All positions and speeds are in units of um.
    All motion is performed through the inherited (from ActuatorCluster) methods move_abs_all and await_all or move_abs_all_sync (previous two combined into one).

    Params
    ------
    opcua_conn : OPCUAConnection

    """

    def __init__(self, opcua_conn: OPCUAConnection):
        # from_prefix reads the parameters in config.ini [ldc] - prefix 'air_*' to build one Actuator per available index.
        # init_backlash = True for each, such that the backlash initialisation sequence is fired.
        cluster = ActuatorCluster.from_prefix(
            opcua_conn, prefix="air", init_backlash=True
        )
        super().__init__(cluster.motors)

    @property
    def positions(self):
        """Current positions of all the delay lines (um)."""
        return self.position_microns
