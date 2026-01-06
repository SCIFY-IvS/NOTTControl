from macie_interface import MacieInterface

interface = MacieInterface()
interface.init_camera()
interface.acquire()
interface.power_off()