from commands.sync_command import SyncCommand

class StopCameraRecordingCommand(SyncCommand):
    def __init__(self, camera_window):
        self._camera_window = camera_window

    def execute(self):
        print('stop recording')
        self.camera_window.stop_recording()
    
    def text(self):
        return "Stopping camera recording"
