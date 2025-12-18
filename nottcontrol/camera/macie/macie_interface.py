import os
import ctypes

class MacieInterface():
    def __init__(self):
        self._macielib = ctypes.CDLL("macie_exe/libmacie_interface.so", mode = os.RTLD_LAZY)
        
        self._macielib.M_initialize.argtypes = [ctypes.c_char_p]
        self._macielib.M_powerOn.argtypes = []
        self._macielib.M_powerOff.argtypes = []
        self._macielib.M_getPower.argtypes = []
        self._macielib.M_initCamera.argtypes = []
        self._macielib.M_acquire.argtypes = [ctypes.c_bool]
        self._macielib.M_close.argtypes = []

        #Load ctypes dll, and call initialize
        #Should the config file be part of the constructor, or hard-coded?
        self._macielib.M_initialize(b"macie_exe/config_files/basic_warm_slow.cfg")
    
    def __enter__(self):
        self.init_camera()
        return self
    
    def __exit__(self):
        self.close()
    
    def power_off(self):
        self._macielib.M_powerOff()
    
    def power_on(self):
        self._macielib.M_powerOn()
    
    def init_camera(self):
        self._macielib.M_initCamera()
    
    def acquire(self, no_recon = False):
        self._macielib.M_acquire(no_recon)
    
    def get_power(self):
        self._macielib.M_getPower()
    
    def close(self):
        self._macielib.M_close()
    

