# Author: Thomas
"""
ldc.py
------
Wrapper of the ActuatorCluster class, specifically tailored for Longitudinal Dispersion Corrector (LDC) actuator cluster for the NOTT instrument.
Hosts ActuatorClusters for the actuators of the ZnSe glass prisms, the CO2 gas cells and the birefringent rotators.

Classes
-------
GlassLDC(ActuatorCluster)
    ZnSe glass prism actuators (NGP1-4) - prefix 'glass'

CO2LDC(ActuatorCluster)
    CO2 gas cell actuators (NCP1-4) - prefix 'co2'

BirefLDC(ActuatorCluster)
    Birefringent rotator actuators (NPC1-4) - prefix = 'biref'

All positions and speeds are in um. No init_backlash sequence, LDC actuators are deliberately not moved upon startup to not disturb the optical state they were in.
prev_dir starts at 0 (direction unknown) for each actuator of the LDCs. Backlash correction fires on the first direction change after the first commanded move.

"""

import numpy as np
import astropy.units as u

from nottcontrol.opcua import OPCUAConnection
from nottcontrol import config as nott_config
from nottcontrol.script.lib.nott_utils import Actuator, ActuatorCluster, MotorError


class GlassLDC(ActuatorCluster):
    """
    ActuatorCluster for the ZnSe glass prism actuators (NGP1-4).
    Reads config.ini [ldc] - 'glass_*' keys. No initialization backlash sequence (init_backlash = False).

    Params
    ------
    opcua_conn : OPCUAConnection

    """

    def __init__(self, opcua_conn: OPCUAConnection):
        cluster = ActuatorCluster.from_prefix(
            opcua_conn, prefix="glass", init_backlash=False
        )
        super().__init__(cluster.motors)


class CO2LDC(ActuatorCluster):
    """
    ActuatorCluster for the CO2 gas cell actuators (NCP1-4).
    Reads config.ini [ldc] - 'co2_*' keys. No initialization backlash sequence (init_backlash = False).

    Provides volume-conserving coordinated motion. Piston positions can be chosen as long as the total enclosed gas volume is preserved.

    Params
    ------
    opcua_conn : OPCUAConnection

    """

    def __init__(self, opcua_conn: OPCUAConnection):
        cluster = ActuatorCluster.from_prefix(
            opcua_conn, prefix="co2", init_backlash=False
        )
        super().__init__(cluster.motors)

        # Physical geometry (from config.ini) for calculations of volume.
        co2_pos_min = nott_config.getfloat("ldc", "co2_pos_min")  # um
        co2_pos_max = nott_config.getfloat("ldc", "co2_pos_max")  # um
        co2_diameter = nott_config.getfloat("ldc", "co2_meandiameter")  # m
        self.stroke = (co2_pos_max - co2_pos_min) * 1e-6  # m
        self.diameter = co2_diameter  # m
        self.section = np.pi * self.diameter**2 / 4.0  # m2
        self.vmax = self.stroke * self.section * len(self)  # m3
        self.vmin = 0.0  # m3
        self.vcenter = (self.vmax - self.vmin) / 2.0
        self.vwork = self.get_volume()

    @property
    def gaz_lengths_m(self):
        """Current lengths of the gas columns (m)."""
        return self.stroke - self.position_microns * u.micron.to(u.m)

    @property
    def volumes(self):
        """Current gas volumes per cell (m3)."""
        pos_m = self.position_microns * u.micron.to(u.m)
        return self.stroke * self.section - pos_m * self.section

    def get_volume(self):
        """Total enclosed gas volume (m3)."""
        return float(np.sum(self.volumes))

    def move_length_isovol(self, positions_m: np.ndarray):
        """
        Move gas cells to positions_m [m] while preserving total volume.

        Centers the requested positions around the volume-defined center
        so that the sum of enclosed volumes remains self.vwork.

        Parameters
        ----------
        positions_m : (N,) array (m)
            Desired gas column lengths per cell.
        """
        centered_pos = positions_m - np.mean(positions_m)
        volume_defined_center = (self.vmax - self.vwork) / (len(self) * self.section)
        target_pos_m = volume_defined_center + centered_pos  # m
        target_pos_um = target_pos_m * u.m.to(u.micron)  # um
        self.tbuff.set(target_pos_um)
        self.move_abs_all_sync(target_pos_um)

    def set_volume(self, volume: float):
        """
        Set the working gas volume (m3) and move to preserve it.

        Parameters
        ----------
        volume : float [m³]
        """
        self.vwork = volume
        self.move_length_isovol(self.gaz_lengths_m)


class BirefLDC(ActuatorCluster):
    """
    ActuatorCluster for the birefringent rotator LDC actuators (NPC1-4).
    Reads config.ini [ldc] - 'biref_*' keys. No initialization backlash sequence (init_backlash = False).
    pos_max = 360 um, representing 360 degrees in the convention of config.ini.

    Params
    ------
    opcua_conn : OPCUAConnection

    """

    def __init__(self, opcua_conn: OPCUAConnection):
        cluster = ActuatorCluster.from_prefix(
            opcua_conn, prefix="biref", init_backlash=False
        )
        super().__init__(cluster.motors)


class NOTT_LDC:
    """Placeholder for a higher-level class that contains all (air, glass, CO2, birefringence)
    LDC clusters in one object. Not yet implemented."""

    pass
