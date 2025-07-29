from pathlib import Path
import os
from nottcontrol.config import Config
from nottcontrol.script.datafiles import DataFiles

_parent = Path(__file__).parent
_config_path_alignment = os.path.join(_parent, "cfg/config.cfg")
config_alignment = Config(_config_path_alignment)

_config_path_scripts = os.path.join(_parent, "config/config.cfg")
config_scripts = Config(_config_path_scripts)

data_files = DataFiles(os.path.join(_parent, "data"))