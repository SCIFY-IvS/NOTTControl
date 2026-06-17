import numpy as np

from nottcontrol import config, sf_config
from nottcontrol.components.observatory import Observatory
from kernuller.interferometers import get_list2layout
from scifysim import utilities

from astropy.time import Time
import astropy.units as u

import astroplan
from astroplan import plots

class NottBackend(object):
    def __init__(self, config, sf_config,
                 asgard_link,
                 config_str=None,
                 config_order=None,
                 verbose=False):
        self.asgard_link = asgard_link
        self.verbose = verbose
        self.update_obs()
        # self.update_offband_ft(self.asgard_link)
        # self.update_conditions(self.asgard_link)
        # self.update_target(self.asgard_link)

    def point(self, time=None, target=None,
              ft_mode="phase"):
        self.obs.point(time, target)
        # TODO More maintenance
        pass

    def update_obs(self, stat_names=None, pdiams=None, order=None, config_name="", location="Paranal"):
        if config_name is None:
            config_name = self.asgard_link["vlti", "conf_name"]
        if order is None:
            order = self.asgard_link.getarray("vlti", "order", dtype=int)
        if stat_names is None:
            stat_names = self.asgard_link.getarray("vlti", "conf_string",
                                              dtype=str)
        if pdiams is None:
            pdiams = self.asgard_link.getarray("vlti", "diam")
        self.obs = Observatory(statnames=stat_names, location=location,
                   pdiams=pdiams,
                   verbose=self.verbose, multi_dish=True, config=None,
                   order=order)

    def update_conditions(self, asgard_link):
        # Update self.
        pass
    def update_target(self, asgard_link):
        pass

        
