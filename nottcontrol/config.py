from configparser import ConfigParser
import logging
from pathlib import Path

logit = logging.getLogger(__name__)
import numpy as np
from platform import system

def getarray(self, section, key, dtype=np.float64):
    """
    An extra get method to parse arrays 
    
    **Parameters:**
    
    * section   : (str) The section to get the data from
    * key       : (str) The key of the data
    * dtype     : A data type for the array conversion
    """
    logit.info("Pulling an array from config file")
    thestring = self[section][key]
    thelist = thestring.split(sep=",")
    thearray = np.array( thelist, dtype=dtype)
    return thearray

ConfigParser.getarray = getarray

def getdate(self, section, key, mode=None):
    """
    An extra get method to parse dates in the GENIE .prm format
    
    **Parameters:**
    
    * section   : (str) The section to get the data from
    * key       : (str) The key of the data
    * mode      : In case we need other formats
    """
    from astropy.time import Time
    if mode is not None:
        raise NotImplementedError("No modes implemented yet")
    else:
        logit.info("Pulling an array from config file")
        rawstring = self[section][key]
        listargs = rawstring.replace(" ", "").split(",")
        formated = listargs[0]+"-"+listargs[1]+"-"+listargs[2]+"T"\
                +listargs[3]+":"+listargs[4]+":"+listargs[5]
        logit.debug(rawstring)
        logit.debug(formated)
        thetime = Time(formated)
    return thetime

ConfigParser.getdate = getdate


def local_config_path(base_path: str | Path) -> Path:
    """Return ``config.local.ini`` next to ``config.ini`` (or ``<stem>.local.ini``)."""
    path = Path(base_path)
    if path.name == "config.ini":
        return path.with_name("config.local.ini")
    return path.with_name(f"{path.stem}.local{path.suffix}")


class Config:
    """INI config with optional gitignored local overrides.

    Load order: ``config.ini``, then ``config.local.ini`` (if present) so lab
    ROI positions and other machine tweaks survive ``git pull``.
    """

    def __init__(self, path: str, comment_prefixes="#", **kwargs):
        self._path = path
        self._local_path = local_config_path(path)
        self.config_parser = ConfigParser(comment_prefixes=comment_prefixes, **kwargs)
        self.config_parser.optionxform = str  # Preserve case sensitivity
        self._local_parser = ConfigParser(comment_prefixes=comment_prefixes, **kwargs)
        self._local_parser.optionxform = str
        self.config_parser.read(path)
        if self._local_path.is_file():
            # Second read overrides matching keys in memory.
            self.config_parser.read(self._local_path)
            self._local_parser.read(self._local_path)
            logit.info("Loaded local config overrides from %s", self._local_path)

    def __getitem__(self, key):
        return self.config_parser[key]

    def getint(self, section, key, fallback=None):
        return self.config_parser.getint(section, key, fallback=fallback)

    def getfloat(self, section, key, fallback=None):
        return self.config_parser.getfloat(section, key, fallback=fallback)

    def get(self, section, key, fallback=None):
        return self.config_parser.get(section, key, fallback=fallback)

    def getboolean(self, section, key, fallback=None):
        return self.config_parser.getboolean(section, key, fallback=fallback)

    def write(self):
        """Persist machine overrides.

        Historically wrote ``config.ini``. That overwrote tracked defaults on
        ``git pull``, so ROI and similar lab tweaks now go to ``config.local.ini``.
        """
        self.write_local()

    def set_local(self, section: str, key: str, value: str) -> None:
        """Update in-memory config and the local-override store."""
        if not self.config_parser.has_section(section):
            self.config_parser.add_section(section)
        self.config_parser.set(section, key, value)
        if not self._local_parser.has_section(section):
            self._local_parser.add_section(section)
        self._local_parser.set(section, key, value)

    def write_local(self) -> None:
        """Persist local overrides to ``config.local.ini`` (not tracked by git)."""
        self._local_path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            "# Local overrides for this machine — not tracked by git.\n"
            "# Merged on top of config.ini at startup. Safe across git pull.\n"
            "# Edit ROIs in the GUI; they are saved here automatically.\n\n"
        )
        with open(self._local_path, "w", encoding="utf-8") as configfile:
            configfile.write(header)
            self._local_parser.write(configfile)

    def getarray(self, *args, **kwargs):
        return self.config_parser.getarray(*args, **kwargs)

    def getdate(self, *args, **kwargs):
        return self.config_parser.getdate(*args, **kwargs)
