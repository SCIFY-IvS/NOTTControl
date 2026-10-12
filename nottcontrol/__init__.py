from pathlib import Path
import logging
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
        "Copy config.ini.example to config.ini, then put lab IPs in "
        "config.local.ini (see config.local.ini.example)."
    ) from exc

# Imported after config so a missing config.ini fails with a clear message.
from nottcontrol.components.asgard_db import asgard_bridge  # noqa: E402

# SCIFYsim nott_config.ini is optional for most tools (H2RG plots, MACIE, …).
# On Linux we try to load it, but a missing/placeholder path must not break
# ``import nottcontrol`` — put the real path under [SCIFYSIM] in config.local.ini.
sf_config = None
if system() == "Linux":
    sf_path = config["SCIFYSIM"]["config"]
    try:
        sf_config = Config(
            sf_path,
            inline_comment_prefixes="#",
            comment_prefixes="#",
        )
    except FileNotFoundError as exc:
        logging.getLogger(__name__).warning(
            "SCIFYSIM config not loaded (%s). "
            "Set [SCIFYSIM] config = /path/to/nott_config.ini in "
            "nottcontrol/config.local.ini if you need SCIFYsim.",
            exc,
        )

sensor_config_path = os.path.join(parent, "sensors.ini")
cryo_status_config_path = os.path.join(parent, "cryo_status.ini")
