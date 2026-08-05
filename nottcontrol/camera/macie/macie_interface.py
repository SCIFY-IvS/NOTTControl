import os
import ctypes
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from threading import Thread, Event, Lock
import zmq

import numpy

from nottcontrol import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILES_DIR = "macie_exe/config_files"
H2RG_SECTION = "H2RG DETECTOR"

ZMQ_REQUEST_TIMEOUT_MS = config.getint(
    H2RG_SECTION, "zmq_request_timeout_ms", fallback=120_000
)
ZMQ_ACQUIRE_TIMEOUT_MS = config.getint(
    H2RG_SECTION, "zmq_acquire_timeout_ms", fallback=300_000
)
MACIE_SHUTDOWN_TIMEOUT_MS = config.getint(
    H2RG_SECTION, "shutdown_timeout_ms", fallback=2_000
)


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


@dataclass(frozen=True)
class AcquireResult:
    """Result of an acquire ZMQ round-trip.

    *frame* is the in-memory CDS/single-plane preview from the server when the
    multipart reply includes it; otherwise None (fall back to FITS).
    """

    frame: numpy.ndarray | None = None


def parse_acquire_preview_parts(
    parts: list[bytes] | tuple[bytes, ...] | None,
) -> AcquireResult:
    """Parse acquire multipart reply into an optional float32 image (ny, nx)."""
    if not parts:
        return AcquireResult()
    header = parts[0]
    if isinstance(header, bytes):
        header = header.decode("utf-8", errors="replace")
    tokens = str(header).split(";")
    if not tokens or tokens[0] != "ok":
        detail = tokens[1] if len(tokens) > 1 else str(header)
        raise Exception(f"Operation failed: {detail}")
    if len(parts) < 2 or len(tokens) < 5 or tokens[1] != "preview":
        return AcquireResult()
    try:
        nx = int(tokens[2])
        ny = int(tokens[3])
    except ValueError:
        print(f"H2RG acquire preview ignored (bad size): {header}")
        return AcquireResult()
    dtype_name = tokens[4].lower()
    if dtype_name not in ("float32", "f32"):
        print(f"H2RG acquire preview ignored (dtype {dtype_name})")
        return AcquireResult()
    if nx <= 0 or ny <= 0:
        return AcquireResult()
    payload = parts[1]
    if isinstance(payload, str):
        payload = payload.encode("latin1")
    expected = nx * ny * 4
    if len(payload) < expected:
        print(
            f"H2RG acquire preview ignored (truncated: {len(payload)}/{expected} bytes)"
        )
        return AcquireResult()
    frame = numpy.frombuffer(payload[:expected], dtype="<f4").reshape((ny, nx)).copy()
    return AcquireResult(frame=frame)


class DetectorMode(Enum):
    SLOW = 1
    FAST = 2


# Usage: calling init_camera puts the camera in a state where it is ready to acquire images.
# By using the python 'with' statement, you can ensure that both the initialization
# and the de-initialization are done
class MacieInterface():

    _LIVE_MAX_FAILURES = 3

    def __init__(
        self,
        offline_mode=False,
        config_file="teledyne_cold_slow.cfg",
        zmq_address="tcp://localhost:65534",
    ):
        self._config_file = server_config_path(config_file)
        self._offline_mode = offline_mode
        self._zmq_address = zmq_address
        self._request_timeout_ms = ZMQ_REQUEST_TIMEOUT_MS
        self._context = zmq.Context()
        self._lock = Lock()
        self._continuous_thread: Thread | None = None
        self._socket = None
        self._create_socket()

        self.initialize(self._config_file, self._offline_mode)

        self.continuous_acquisition_running = False
        self._acquiring = Event()
        self._acquiring.clear()
        self._closing = Event()
        self._pause_live = Event()
        self._live_session_open = False
        self._live_error_callback: Callable[[Exception], None] | None = None
        self._live_frame_callback: Callable[[numpy.ndarray | None], None] | None = None
        self._live_first_acquire = True

    def set_live_error_callback(
        self, callback: Callable[[Exception], None] | None
    ) -> None:
        self._live_error_callback = callback

    def set_live_frame_callback(
        self, callback: Callable[[numpy.ndarray | None], None] | None
    ) -> None:
        """Optional hook after each live acquire; may receive the ZMQ preview frame."""
        self._live_frame_callback = callback

    def _set_live_session(self, keep: bool) -> None:
        """Enable/disable GigE keep-alive; no-op if already in the requested state."""
        if keep == self._live_session_open:
            return
        self._request(f"livesession;{str(keep).lower()}")
        self._live_session_open = keep

    def _reset_live_science_interface(self) -> None:
        """Ensure GigE is closed after a failed live ramp (no keep-alive)."""
        try:
            if self._live_session_open:
                self._request("livesession;false")
                self._live_session_open = False
            self._live_first_acquire = True
        except Exception as exc:
            print(f"Live science interface reset failed: {exc}")

    def _attempt_halt_after_timeout(self) -> None:
        try:
            self._socket.send_string("halt")
            self._receive_and_parse_reply()
        except Exception as exc:
            print(f"MACIE halt after timeout failed: {exc}")

    def _handle_timeout(self, message: str, exc: zmq.Again) -> TimeoutError:
        command = message.split(";", 1)[0]
        self._reset_socket()
        if command in ("acquire", "fetchnewestfits"):
            # _request / _request_multipart already hold self._lock.
            self._attempt_halt_after_timeout()
        return TimeoutError(f"ZMQ request timed out ({command})")

    def __enter__(self):
        self.init_camera()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()

    def _send_shutdown_command(self, command: str, *, timeout_ms: int) -> bool:
        if self._socket is None:
            return False
        restore_rcv = self._socket.getsockopt(zmq.RCVTIMEO)
        restore_snd = self._socket.getsockopt(zmq.SNDTIMEO)
        try:
            self._socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
            self._socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
            self._socket.send_string(command)
            self._receive_and_parse_reply()
            return True
        except Exception as exc:
            print(f"MACIE {command} during shutdown: {exc}")
            return False
        finally:
            try:
                self._socket.setsockopt(zmq.RCVTIMEO, restore_rcv)
                self._socket.setsockopt(zmq.SNDTIMEO, restore_snd)
            except Exception:
                pass

    def disconnect(
        self,
        *,
        halt_server: bool = False,
        shutdown_server: bool = False,
        request_timeout_ms: int | None = None,
    ) -> None:
        """Drop the client ZMQ connection.

        By default the MACIE zmq_server keeps running so another GUI session can
        reconnect. Only request server halt/close when acquisition may still be
        active, or when shutting down a GUI-started local zmq_server process.
        """
        timeout_ms = (
            MACIE_SHUTDOWN_TIMEOUT_MS
            if request_timeout_ms is None
            else request_timeout_ms
        )
        self._closing.set()
        self._acquiring.clear()

        if self._continuous_thread is not None and self._continuous_thread.is_alive():
            self._continuous_thread.join(timeout=0.5)

        commands: list[str] = []
        if halt_server or shutdown_server:
            commands.append("halt")
        if shutdown_server:
            commands.append("close")

        acquired = self._lock.acquire(timeout=timeout_ms / 1000.0) if commands else False
        halt_ok = not halt_server and not shutdown_server
        try:
            if acquired and self._socket is not None:
                for command in commands:
                    if command == "close" and not halt_ok:
                        break
                    command_ok = self._send_shutdown_command(
                        command, timeout_ms=timeout_ms
                    )
                    if command == "halt":
                        halt_ok = command_ok
            elif commands and not acquired:
                print("MACIE shutdown: aborting blocked ZMQ socket")
                self._abort_socket_unlocked()
        finally:
            if acquired:
                self._lock.release()

        self._teardown_zmq()

    def close(self, *, request_timeout_ms: int | None = None) -> None:
        """Backward-compatible alias for disconnect()."""
        self.disconnect(request_timeout_ms=request_timeout_ms)

    def _create_socket(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close(linger=0)
            except Exception:
                pass
        self._socket = self._context.socket(zmq.REQ)
        self._socket.setsockopt(zmq.RCVTIMEO, self._request_timeout_ms)
        self._socket.setsockopt(zmq.SNDTIMEO, self._request_timeout_ms)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.connect(self._zmq_address)

    def _reset_socket(self) -> None:
        self._create_socket()

    def initialize(self, config_file, offline_mode):
        self._config_file = server_config_path(config_file)
        return self._request(
            f"init;{self._config_file};{str(offline_mode).lower()}"
        )

    def set_config_file(self, config_file: str) -> None:
        self._config_file = server_config_path(config_file)

    def reinit_camera(self, config_file: str | None = None) -> None:
        if config_file is not None:
            self.set_config_file(config_file)
        self.init_camera()

    def power_off(self):
        return self._request("poweroff")

    def power_on(self):
        return self._request("poweron")

    def init_camera(self):
        # Re-send init so initcamera works after a zmq_server restart or a
        # stale client session that skipped the init command on the server.
        self.initialize(self._config_file, self._offline_mode)
        self._request("initcamera")

        if self._continuous_thread is None or not self._continuous_thread.is_alive():
            self._continuous_thread = Thread(
                target=self.continuous_acquisition, daemon=True
            )
            self._continuous_thread.start()

    def _request(self, message: str, *, timeout_ms: int | None = None):
        with self._lock:
            restore_timeout = False
            if timeout_ms is not None and timeout_ms != self._request_timeout_ms:
                self._socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
                self._socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
                restore_timeout = True
            try:
                self._socket.send_string(message)
                return self._receive_and_parse_reply()
            except zmq.Again as exc:
                raise self._handle_timeout(message, exc) from exc
            finally:
                if restore_timeout:
                    self._socket.setsockopt(zmq.RCVTIMEO, self._request_timeout_ms)
                    self._socket.setsockopt(zmq.SNDTIMEO, self._request_timeout_ms)

    def _request_multipart(self, message: str, *, timeout_ms: int | None = None):
        with self._lock:
            restore_timeout = False
            if timeout_ms is not None and timeout_ms != self._request_timeout_ms:
                self._socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
                self._socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
                restore_timeout = True
            try:
                self._socket.send_string(message)
                parts = self._socket.recv_multipart()
            except zmq.Again as exc:
                raise self._handle_timeout(message, exc) from exc
            finally:
                if restore_timeout:
                    self._socket.setsockopt(zmq.RCVTIMEO, self._request_timeout_ms)
                    self._socket.setsockopt(zmq.SNDTIMEO, self._request_timeout_ms)
            return parts

    def acquire(self, no_recon=False) -> AcquireResult:
        parts = self._request_multipart(
            f"acquire;{str(no_recon).lower()}",
            timeout_ms=ZMQ_ACQUIRE_TIMEOUT_MS,
        )
        return parse_acquire_preview_parts(parts)

    def get_save_dir(self) -> str | None:
        return self._request("getsavedir")

    def get_newest_fits_path(self) -> str | None:
        return self._request("newestfits")

    def fetch_newest_fits(self) -> tuple[str, bytes] | None:
        parts = self._request_multipart(
            "fetchnewestfits",
            timeout_ms=ZMQ_ACQUIRE_TIMEOUT_MS,
        )
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

    def _abort_socket_unlocked(self) -> None:
        socket = self._socket
        self._socket = None
        if socket is not None:
            try:
                socket.close(linger=0)
            except Exception:
                pass

    def _teardown_zmq(self) -> None:
        if self._lock.acquire(timeout=2.0):
            try:
                if self._socket is not None:
                    try:
                        self._socket.close(linger=0)
                    except Exception:
                        pass
                    self._socket = None
            finally:
                self._lock.release()
        try:
            self._context.term()
        except Exception:
            pass

    def halt_acquisition(self):
        return self._request("halt")

    def exposure_settings(self, save, ncoadds, nseq, ngroups, nreads, ndrops, nresets):
        message = f"expsettings;{str(save).lower()};{ncoadds};{nseq};{ngroups};{nreads};{ndrops};{nresets}"
        return self._request(message)

    def set_exp_mode(self, mode: int) -> bool:
        return self._request(f"expmode;{int(mode)}")

    def configure_ramp_exposure(
        self,
        tint_ms: float,
        *,
        ramp_mode: str = "CDS",
        fowler_pairs: int = 2,
        ngmax: int = 2,
        ncoadds: int = 1,
        nseq: int = 1,
        save: bool = True,
        windowed_cds: bool = False,
    ) -> dict[str, float | int]:
        """Apply CDS or Fowler ramp plan for the requested integration time."""
        from nottcontrol.camera.macie.ramp_plan import calc_ramp_plan, exp_mode_for_ramp

        timing = self.read_exposure_timing()
        frametime_ms = timing["frametime_s"] * 1000.0
        plan = calc_ramp_plan(
            float(tint_ms),
            frametime_ms,
            mode=ramp_mode,  # type: ignore[arg-type]
            fowler_pairs=fowler_pairs,
            ngmax=ngmax,
            windowed_cds=windowed_cds,
        )
        self.set_exp_mode(exp_mode_for_ramp(ramp_mode))  # type: ignore[arg-type]
        _save, _ncoadds, _nseq, _ng, _nr, _nd, nresets = self.read_exposure_settings()
        self.exposure_settings(
            save,
            ncoadds,
            nseq,
            plan["ngroups"],
            plan["nreads"],
            plan["ndrops"],
            nresets,
        )
        timing = self.read_exposure_timing()
        return {
            **plan,
            "inttime_ms": timing["inttime_s"] * 1000.0,
            "ramptime_ms": timing["ramptime_s"] * 1000.0,
            "execution_s": timing["execution_s"],
            "frametime_ms": timing["frametime_s"] * 1000.0,
            "efficiency": timing["efficiency"],
            "ncoadds": int(ncoadds),
            "nseq": int(nseq),
            "ramp_mode": ramp_mode,
        }

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
        self._live_first_acquire = True
        # Do not use livesession keep-alive: leaving GigE open between ramps
        # caused channel-edge blink / desync and Live stop on SC. Each ramp
        # opens and closes the science interface instead (ZMQ preview still
        # avoids the FITS round-trip).
        try:
            self._set_live_session(False)
        except Exception as exc:
            print(f"Live session clear failed: {exc}")
        self._acquiring.set()

    def stop_continuous_acquisition(self):
        self._acquiring.clear()
        try:
            self._set_live_session(False)
        except Exception as exc:
            print(f"Live session stop failed: {exc}")

    def pause_live_acquisition(self) -> None:
        self._pause_live.set()

    def resume_live_acquisition(self) -> None:
        self._pause_live.clear()

    def continuous_acquisition(self):
        # Run for as long as the interface is not closed
        failures = 0
        while not self._closing.is_set():
            if self._acquiring.wait(0.1):
                if self._pause_live.is_set():
                    continue
                try:
                    # Always reconfigure on Live: skipping recon with keep-alive
                    # produced alternating column-shifted frames (channel seams).
                    result = self.acquire(no_recon=False)
                    self._live_first_acquire = False
                    failures = 0
                    frame_callback = self._live_frame_callback
                    if frame_callback is not None:
                        try:
                            frame_callback(result.frame)
                        except Exception as callback_exc:
                            print(f"Live frame callback failed: {callback_exc}")
                    if self._acquiring.is_set() and not self._closing.is_set():
                        time.sleep(0.005)
                except Exception as exc:
                    failures += 1
                    print(f"Live acquire failed ({failures}/{self._LIVE_MAX_FAILURES}): {exc}")
                    self._reset_live_science_interface()
                    if failures < self._LIVE_MAX_FAILURES and self._acquiring.is_set():
                        time.sleep(0.5)
                        continue
                    self._acquiring.clear()
                    try:
                        self._set_live_session(False)
                    except Exception:
                        pass
                    callback = self._live_error_callback
                    if callback is not None:
                        try:
                            callback(exc)
                        except Exception as callback_exc:
                            print(f"Live error callback failed: {callback_exc}")

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
