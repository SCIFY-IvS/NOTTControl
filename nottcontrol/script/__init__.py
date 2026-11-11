from pathlib import Path
import logging
import os

from nottcontrol.config import Config
from nottcontrol.script.datafiles import DataFiles

_parent = Path(__file__).parent
_log = logging.getLogger(__name__)

# Legacy script config was removed as a duplicate of nottcontrol/config.ini.
# Keep the hook optional so ``import nottcontrol.script.backup…`` works.
_config_path_scripts = os.path.join(_parent, "config/config.cfg")
config_scripts = None
if Path(_config_path_scripts).is_file():
    config_scripts = Config(_config_path_scripts)
else:
    _log.debug(
        "Optional script config missing (%s); using nottcontrol/config.ini only",
        _config_path_scripts,
    )

data_files = DataFiles(os.path.join(_parent, "data"))
