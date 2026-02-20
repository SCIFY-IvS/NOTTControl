from pathlib import Path
import os
from nottcontrol.config import Config
from platform import system

parent = Path(__file__).parent
config_path = os.path.join(parent, "config.ini")
config = Config(config_path)
if system() == "Linux":
    sf_path = config["SCIFYSIM"]["config"]
    sf_config = Config(sf_path,
                       inline_comment_prefixes = "#",
                       comment_prefixes = "#")
