from configparser import ConfigParser
import logging
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

class Config:
    
    def __init__(self, path:str, comment_prefixes=None):
        self._path = path
        self.config_parser = ConfigParser(comment_prefixes=comment_prefixes)
        self.config_parser.optionxform = str # Preserve case sensitivity
        self.config_parser.read(path)

    def __getitem__(self, key):
        return self.config_parser[key]
    
    def getint(self, section, key):
        return self.config_parser.getint(section, key)
    
    def write(self):
        with open(self._path, 'w') as configfile:
            self.config_parser.write(configfile)
    def getarray(self, *args, **kwargs):
        return self.config_parser.getarray(*args, **kwargs)
    def getdate(self, *args, **kwargs):
        return self.config_parser.getdate(*args, **kwargs)
            
