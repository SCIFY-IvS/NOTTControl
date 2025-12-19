from configparser import ConfigParser

class Config:
    def __init__(self, path:str):
        self._path = path
        self.config_parser = ConfigParser()
        self.config_parser.optionxform = str # Preserve case sensitivity
        self.config_parser.read(path)

    def __getitem__(self, key):
        return self.config_parser[key]
    
    def getint(self, section, key):
        return self.config_parser.getint(section, key)
    
    def write(self):
        with open(self._path, 'w') as configfile:
            self.config_parser.write(configfile)