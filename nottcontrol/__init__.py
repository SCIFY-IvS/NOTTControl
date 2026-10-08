from pathlib import Path
import os
from platform import system

from nottcontrol.config import Config

parent = Path(__file__).parent
config_path = os.path.join(parent, "config.ini")
try:
    config = Config(
        config_path,
        inline_comment_prefixes="#",
        comment_prefixes="#",
    )
except FileNotFoundError as exc:
    raise FileNotFoundError(
        "Missing nottcontrol/config.ini. "
        "Copy config.ini.example to config.ini and fill in your site values "
        "before first run."
    ) from exc

# Imported after config so a missing config.ini fails with a clear message.
from nottcontrol.components.asgard_db import asgard_bridge  # noqa: E402

if system() == "Linux":
    sf_path = config["SCIFYSIM"]["config"]
    sf_config = Config(sf_path,
                       inline_comment_prefixes = "#",
                       comment_prefixes = "#")

sensor_config_path = os.path.join(parent, "sensors.ini")
cryo_status_config_path = os.path.join(parent, "cryo_status.ini")
