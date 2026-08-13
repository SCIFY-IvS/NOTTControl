import os
from pathlib import Path
from nottcontrol.config import Config
from astropy.time import Time

parent = Path(__file__).parent.parent

class AsgardBridgeTest(Config):
    @classmethod
    def setupAsgard(cls):

        asgard_path = os.path.join(parent, "asgard_db.ini")
        myobj = cls(asgard_path,
                               inline_comment_prefixes = "#",
                               comment_prefixes = "#")
        return myobj

    def timestring(self):
        Time.now().isot

asgard_bridge = AsgardBridgeTest.setupAsgard()


class AsgardBridge(object):
    """
        This class must query the MCS relay in Asgard, which communicates with the MCS database.
    * The keywords subscribed by WAG are given by agmcfgMCS.cfg
    * The ESO reference is in issif.scan

    Checkout ``heimdallr.cpp`` for the available commands
    * `COMMANDER_REGISTER`
        - `set_gd_offsets` all in radians in K1
        - `tweak_gd_offsets` all in radians in K1
        - `get_gd_toml_offsets` all in radians in K1


    Mean filter bands
    * K1 : 2.1µm
    * K2 : 2.3µm

    GD tracking uncertainty is lower that PD uncertainty in Hdlr? Why?

    Zero deviation wavelength: 1.4118µm

    Heimdallr commands, found in `heimdallr.cpp` `COMMANDER_REGISTER`:
        * Status get_status
        * Settings get_settings
    """
    def __init__(self):
        pass
