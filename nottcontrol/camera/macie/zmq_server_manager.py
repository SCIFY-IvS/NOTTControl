from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from nottcontrol import config

MACIE_DIR = Path(__file__).resolve().parent
DEFAULT_ZMQ_ADDRESS = config.get(
    "MACIE", "zmq_address", fallback="tcp://localhost:65534"
)
AUTO_START_ZMQ_SERVER = config.getboolean(
    "MACIE", "auto_start_zmq_server", fallback=True
)
ZMQ_SERVER_EXECUTABLE = config.get(
    "MACIE", "zmq_server_executable", fallback="macie_exe/zmq_server"
)
ZMQ_STARTUP_TIMEOUT_S = config.getfloat(
    "MACIE", "zmq_startup_timeout_s", fallback=10.0
)
MACIE_LIBRARY_PATH = config.get("MACIE", "macie_library_path", fallback="")


def parse_zmq_endpoint(address: str) -> tuple[str, int]:
    normalized = address if "://" in address else f"tcp://{address}"
    parsed = urlparse(normalized)
    host = parsed.hostname or "localhost"
    port = parsed.port or 65534
    return host, port


def is_zmq_port_open(address: str, timeout_s: float = 0.5) -> bool:
    host, port = parse_zmq_endpoint(address)
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def resolve_zmq_server_executable() -> Path | None:
    configured = Path(ZMQ_SERVER_EXECUTABLE)
    if not configured.is_absolute():
        configured = MACIE_DIR / configured
    if sys.platform == "win32" and configured.suffix == "":
        exe_candidate = configured.with_suffix(".exe")
        if exe_candidate.is_file():
            return exe_candidate
    if configured.is_file():
        return configured
    return None


def _server_environment() -> dict[str, str]:
    env = os.environ.copy()
    if MACIE_LIBRARY_PATH:
        current = env.get("LD_LIBRARY_PATH", "")
        paths = [p for p in (MACIE_LIBRARY_PATH, current) if p]
        env["LD_LIBRARY_PATH"] = os.pathsep.join(paths)
    return env


class MacieZmqServerProcess:
    """Start and stop the MACIE zmq_server subprocess."""

    def __init__(self, zmq_address: str = DEFAULT_ZMQ_ADDRESS) -> None:
        self._zmq_address = zmq_address
        self._process: subprocess.Popen | None = None

    @property
    def started_by_gui(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def ensure_running(self) -> None:
        if is_zmq_port_open(self._zmq_address):
            return
        if not AUTO_START_ZMQ_SERVER:
            raise RuntimeError(
                "MACIE ZMQ server is not running and auto_start_zmq_server is disabled"
            )

        executable = resolve_zmq_server_executable()
        if executable is None:
            raise FileNotFoundError(
                "MACIE zmq_server executable not found. Build it under "
                f"{MACIE_DIR / 'macie_exe'} and set zmq_server_executable in config.ini"
            )

        self._process = subprocess.Popen(
            [str(executable)],
            cwd=str(MACIE_DIR),
            env=_server_environment(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        deadline = time.monotonic() + ZMQ_STARTUP_TIMEOUT_S
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError(
                    f"zmq_server exited immediately with code {self._process.returncode}"
                )
            if is_zmq_port_open(self._zmq_address):
                return
            time.sleep(0.2)

        self.stop()
        raise TimeoutError(
            f"zmq_server did not open {self._zmq_address} within {ZMQ_STARTUP_TIMEOUT_S:g}s"
        )

    def stop(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=3.0)
        self._process = None
