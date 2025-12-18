# import os
# import ctypes
# _macielib = ctypes.CDLL("macie_exe/libmacie_interface.so", mode = os.RTLD_LAZY)

# _macielib.M_initialize.argtypes = [ctypes.c_char_p]
# _macielib.M_initialize(b"macie_exe/config_files/basic_warm_slow.cfg")

# _macielib.M_initCamera.argtypes = []
# _macielib.M_initCamera()

# _macielib.M_acquire.argtypes = [ctypes.c_bool]
# _macielib.M_acquire(False)

# _macielib.M_powerOff.argtypes = []
# _macielib.M_powerOff()

from macie_interface import MacieInterface

interface = MacieInterface()
interface.init_camera()
interface.acquire()
interface.power_off()