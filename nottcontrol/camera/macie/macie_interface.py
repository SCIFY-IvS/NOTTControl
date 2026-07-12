import os
import ctypes
from enum import Enum
from threading import Thread, Event, Lock
import zmq

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILES_DIR = "macie_exe/config_files"


def server_config_path(config_file: str) -> str:
    """Path sent to zmq_server, relative to the camera/macie working directory."""
    name = os.path.basename(config_file.replace("\\", "/"))
    return f"{CONFIG_FILES_DIR}/{name}"


def parse_zmq_float(value: str | float | int) -> float:
    """Parse numeric ZMQ fields regardless of server locale decimal separator."""
    if isinstance(value, (int, float)):
        return float(value)
    normalized = str(value).strip().replace(",", ".")
    return float(normalized)


class DetectorMode(Enum):
    SLOW = 1
    FAST = 2


# Usage: calling init_camera puts the camera in a state where it is ready to acquire images.
# By using the python 'with' statement, you can ensure that both the initialization
# and the de-initialization are done
class MacieInterface():
    
    def __init__(
        self,
        offline_mode=False,
        config_file="basic_warm_slow.cfg",
        zmq_address="tcp://localhost:65534",
    ):
        self._config_file = server_config_path(config_file)
        self._offline_mode = offline_mode
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.REQ)
        self._socket.connect(zmq_address)
        self._lock = Lock()
        self._continuous_thread: Thread | None = None

        self.initialize(self._config_file, self._offline_mode)

        self.continuous_acquisition_running = False
        self._acquiring = Event()
        self._acquiring.clear()
        self._closing = Event()

    def __enter__(self):
        self.init_camera()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    def initialize(self, config_file, offline_mode):
        with self._lock:
            self._socket.send_string(f"init;{config_file};{str(offline_mode).lower()}")
            return self._receive_and_parse_reply()
    
    def power_off(self):
        return self._request("poweroff")
    
    def power_on(self):
        return self._request("poweron")

    def init_camera(self):
        # Re-send init so initcamera works after a zmq_server restart or a
        # stale client session that skipped the init command on the server.
        self.initialize(self._config_file, self._offline_mode)
        with self._lock:
            self._socket.send_string("initcamera")
            self._receive_and_parse_reply()

        if self._continuous_thread is None or not self._continuous_thread.is_alive():
            self._continuous_thread = Thread(
                target=self.continuous_acquisition, daemon=True
            )
            self._continuous_thread.start()
    
    def _request(self, message: str):
        with self._lock:
            self._socket.send_string(message)
            return self._receive_and_parse_reply()

    def _request_multipart(self, message: str):
        with self._lock:
            self._socket.send_string(message)
            return self._socket.recv_multipart()
    
    def acquire(self, no_recon = False):
        return self._request(f"acquire;{str(no_recon).lower()}")

    def get_save_dir(self) -> str | None:
        return self._request("getsavedir")

    def get_newest_fits_path(self) -> str | None:
        return self._request("newestfits")

    def fetch_newest_fits(self) -> tuple[str, bytes] | None:
        parts = self._request_multipart("fetchnewestfits")
        if not parts:
            return None
        header = parts[0].decode("utf-8")
        tokens = header.split(";")
        if tokens[0] != "ok":
            raise Exception(f"Operation failed: {tokens[1] if len(tokens) > 1 else header}")
        filename = tokens[1] if len(tokens) > 1 else "frame.fits"
        if len(parts) < 2:
            return None
        payload = parts[1]
        if isinstance(payload, str):
            payload = payload.encode("latin1")
        return filename, bytes(payload)
    
    def get_power(self):
        result = self._request("getpower")
        return result == "true"
    
    def close(self):
        self._closing.set()
        self._acquiring.clear()

        try:
            self._request("close")
        except Exception as e:
            print(e)

        with self._lock:
            self._socket.close()
            self._context.term()
    
    def halt_acquisition(self):
        return self._request("halt")
    
    def exposure_settings(self, save, ncoadds, nseq, ngroups, nreads, ndrops, nresets):
        message = f"expsettings;{str(save).lower()};{ncoadds};{nseq};{ngroups};{nreads};{ndrops};{nresets}"
        return self._request(message)
    
    def set_integration_time(
        self,
        tint_s: float,
        *,
        ngmax: int = 0,
        ncoadds: int = 1,
        nseq: int = 1,
        save: bool = True,
    ) -> tuple[float, int, int, int]:
        """Configure ramp timing via calc_ramp_settings (FromJarron intTime).

        Returns (actual_tint_ms, ngroups, ndrops, nreads).
        """
        tint_ms = float(tint_s) * 1000.0
        message = (
            f"inttime;{tint_ms};{ngmax};{ncoadds};{nseq};{str(save).lower()}"
        )
        answer = self._request(message)
        actual_ms = parse_zmq_float(answer[0])
        return actual_ms, int(answer[1]), int(answer[2]), int(answer[3])

    def read_integration_time_s(self) -> float:
        answer = self._request("readinttime")
        return parse_zmq_float(answer) / 1000.0

    def read_exposure_timing(self) -> dict[str, float]:
        answer = self._request("rexptiming")
        return {
            "inttime_s": parse_zmq_float(answer[0]) / 1000.0,
            "ramptime_s": parse_zmq_float(answer[1]) / 1000.0,
            "execution_s": parse_zmq_float(answer[2]),
            "efficiency": parse_zmq_float(answer[3]),
            "frametime_s": parse_zmq_float(answer[4]) / 1000.0,
        }
    
    def read_exposure_settings(self):
        answer = self._request("rexpsettings")
        
        save = True if answer[0] == "true" else False
        ncoadds = answer[1]
        nsaved_ramps = answer[2]
        ngroups = answer[3]
        nreads = answer[4]
        ndrops = answer[5]
        nresets = answer[6]
        return (save, ncoadds, nsaved_ramps, ngroups, nreads, ndrops, nresets)
    
    def frame_settings(self, xWindow: bool, yWindow: bool, x1:int, x2:int, y1:int, y2: int):
        message = f"framesettings;{str(xWindow).lower()};{str(yWindow).lower()};{x1};{x2};{y1};{y2}"
        return self._request(message)
    
    def read_frame_settings(self):
        answer = self._request("rframesettings")

        xWindow = True if answer[0] == "true" else False
        yWindow = True if answer[1] == "true" else False
        x1 = answer[2]
        x2 = answer[3]
        y1 = answer[4]
        y2 = answer[5]

        return (xWindow, yWindow, x1, x2, y1, y2)
    

    
    def get_detector_mode(self):
        """ Get the current detector mode (fast/slow)"""
        answer = self._request("getmode")
        if answer == "fast":
            return DetectorMode.FAST
        elif answer == "slow":
            return DetectorMode.SLOW
        else:
            raise Exception("Unexpected reply to getmode")
    
    def start_continuous_acquisition(self):
        self._acquiring.set()
    
    def stop_continuous_acquisition(self):
        self._acquiring.clear()
    
    def continuous_acquisition(self):
        #Run for as long as the interface is not closed
        while not self._closing.is_set():
            if (self._acquiring.wait(0.1)):
                self.acquire()
    
    def _receive_and_parse_reply(self):
        reply = self._socket.recv_string()
        print (f"Received reply {reply}")
        tokens = reply.split(";")

        if tokens[0] == "ok":
            if len(tokens) == 1:
                return
            if len(tokens) == 2:
                return tokens[1]
            else:
                return tokens[1:]
        else:
            raise Exception(f"Operation failed: {tokens[1]}")
