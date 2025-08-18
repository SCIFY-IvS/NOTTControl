from pathlib import Path
import os
from nottcontrol.config import Config

parent = Path(__file__).parent
config_path = os.path.join(parent, "config.ini")
config = Config(config_path)