import numpy as np

from nottcontrol.config import config, sf_config
from nottcontrol.components import Observatory
from kernuller.interferometers import get_list2layout


class NottBackend(object):
    def __init__(self, config, sf_config,
                 config_str=None,
                 config_order=None):
        location = sf_config["configuration"]["location"]
        config_name = sf_config["configuration"]["config"]
        self.stat_names = sf_config.getarray("configuration", "conf_string")
        stat_coords = get_list2layout(self.stat_names)
        statlocs = self.get_raw_array(stat_coords)
        self.obs = Observatory(statlocs, location,
                               verbose=False, multi_dish=True,
                               config=None)
    
