from pathlib import Path
import os
from nottcontrol import config

parent = Path(__file__).parent
config_path = os.path.join(parent, "config.ini")
config = config.Config(config_path)