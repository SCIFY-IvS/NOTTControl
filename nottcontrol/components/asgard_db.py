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
        Time.now().isot()

asgard_bridge = AsgardBridgeTest.setupAsgard()
