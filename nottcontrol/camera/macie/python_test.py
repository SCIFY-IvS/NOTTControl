from macie_interface import MacieInterface

interface = MacieInterface(offline_mode = True)
interface.init_camera()
interface.acquire()
interface.power_off()