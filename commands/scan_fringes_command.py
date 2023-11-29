from commands.command_sequence import CommandSequence
from commands.move_abs_command import MoveAbsCommand
from commands.stop_camera_recording_command import StopCameraRecordingCommand
from commands.start_camera_recording_command import StartCameraRecordingCommand
from opcua import OPCUAConnection

class ScanFringesCommand(CommandSequence):
    # scan fringes does the following:
    # 1) Move (abs) to start position (async)
    # 2) Start recording on camera (sync)
    # 3) Move (abs) to final position (async)
    # 4) Stop recording on camera (sync)

    def __init__(self, opcua_conn, start_pos, end_pos, speed, camera_window):
        moveToStart = MoveAbsCommand(opcua_conn, start_pos, speed)
        startRecording = StartCameraRecordingCommand(camera_window)
        moveToFinish = MoveAbsCommand(opcua_conn, end_pos, speed)
        stopRecording = StopCameraRecordingCommand(camera_window)
        super().__init__([moveToStart, startRecording, moveToFinish, stopRecording], 'Scan fringes')
