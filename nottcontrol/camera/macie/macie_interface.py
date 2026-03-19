import os
import ctypes
from threading import Thread, Event

class MacieInterface():
    def __init__(self, offline_mode = True, config_file="basic_warm_slow.cfg"):
        self._macielib = ctypes.CDLL("macie_exe/libmacie_interface.so", mode = os.RTLD_LAZY)
        
        self._macielib.M_initialize.argtypes = [ctypes.c_char_p, ctypes.c_bool]
        self._macielib.M_powerOn.argtypes = []
        self._macielib.M_powerOff.argtypes = []
        self._macielib.M_getPower.argtypes = []
        self._macielib.M_initCamera.argtypes = []
        self._macielib.M_acquire.argtypes = [ctypes.c_bool]
        self._macielib.M_halt_acquisition.argtypes = []
        self._macielib.M_close.argtypes = []

        #Load ctypes dll, and call initialize
        #Should the config file be part of the constructor, or hard-coded?
        file = os.path.join("macie_exe/config_files", config_file)
        self._macielib.M_initialize(bytes(file, "utf-8"), offline_mode)

        self.continuous_acquisition_running = False
        self._acquiring = Event()
        self._acquiring.clear()
        self._closing = Event()
    
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

        #Start the thread for continuous acquisition - it won't execute anything until start_continuous_acquisition is called
        thread = Thread(target = self.continuous_acquisition)
        thread.start()
    
    def acquire(self, no_recon = False):
        self._macielib.M_acquire(no_recon)
    
    def get_power(self):
        self._macielib.M_getPower()
    
    def close(self):
        self._closing.set()
        self._macielib.M_close()
    
    def halt_acquisition(self):
        self._macielib.M_halt_acquisition()
    
    def start_continuous_acquisition(self):
        self._acquiring.set()
    
    def stop_continuous_acquisition(self):
        self._acquiring.clear()
    
    def continuous_acquisition(self):
        #Run for as long as the interface is not closed
        while not self._closing.is_set():
            self._acquiring.wait()
            self.acquire()