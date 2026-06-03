from nottcontrol.camera.macie.macie_interface import MacieInterface

interface = MacieInterface(offline_mode = True)
interface.init_camera()
interface.exposure_settings(True, 1, 2, 3, 4,5 ,6)
interface.frame_settings(True, True, 10, 40, 100, 400)
interface.acquire()

interface.close()