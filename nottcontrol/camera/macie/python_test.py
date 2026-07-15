from nottcontrol.camera.macie.macie_interface import MacieInterface


with MacieInterface(offline_mode = True) as interface:
    interface.exposure_settings(True, 1, 2, 3, 4,5 ,6)
    interface.read_exposure_settings()
    interface.frame_settings(True, True, 10, 40, 100, 400)
    interface.read_frame_settings()
    interface.acquire()