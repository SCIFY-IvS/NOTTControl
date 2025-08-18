from nottcontrol.commands.sync_command import SyncCommand

class StartCameraRecordingCommand(SyncCommand):
    def __init__(self, camera_window):
        self._camera_window = camera_window

    def execute(self):
        print('start recording')
        self._camera_window.start_recording()
    
    def text(self):
        return "Starting camera recording"
