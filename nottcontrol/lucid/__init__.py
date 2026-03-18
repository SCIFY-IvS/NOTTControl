# -*- coding: utf-8 -*-
"""
Created on Wed Dec 17 17:13:16 2025

@author: Thomas
"""

from pathlib import Path
import os
from nottcontrol.config import Config

_parent = Path(__file__).parent
_config_path_lucid = os.path.join(_parent, "cfg/config.cfg")
config_lucid = Config(_config_path_lucid)
