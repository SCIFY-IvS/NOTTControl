from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from nottcontrol import config

logger = logging.getLogger(__name__)

MACIE_DIR = Path(__file__).resolve().parent
H2RG_SECTION = "H2RG DETECTOR"
DEFAULT_ZMQ_ADDRESS = config.get(
    H2RG_SECTION, "zmq_address", fallback="tcp://nott-server.ster.kuleuven.be:65534"
)
DEFAULT_ZMQ_ADDRESS_ALT = config.get(
    H2RG_SECTION, "zmq_address_alt", fallback="tcp://nott-server.ster.kuleuven.be:5900"
).strip()
AUTO_START_ZMQ_SERVER = config.getboolean(
    H2RG_SECTION, "auto_start_zmq_server", fallback=False
)
ZMQ_SERVER_EXECUTABLE = config.get(
    H2RG_SECTION, "zmq_server_executable", fallback="macie_exe/zmq_server"
)
ZMQ_STARTUP_TIMEOUT_S = config.getfloat(
    H2RG_SECTION, "zmq_startup_timeout_s", fallback=10.0
)
MACIE_LIBRARY_PATH = config.get(H2RG_SECTION, "macie_library_path", fallback="")


def macie_zmq_addresses() -> list[str]:
    """Primary and optional alternate ZMQ endpoints from config."""
    addresses: list[str] = []
    for candidate in (DEFAULT_ZMQ_ADDRESS, DEFAULT_ZMQ_ADDRESS_ALT):
        normalized = candidate.strip()
        if normalized and normalized not in addresses:
            addresses.append(normalized)
    return addresses or [DEFAULT_ZMQ_ADDRESS]


def select_macie_zmq_address(timeout_s: float = 0.5) -> str:
    """Return the first reachable MACIE ZMQ endpoint, else the primary address."""
    addresses = macie_zmq_addresses()
    for address in addresses:
        if is_zmq_port_open(address, timeout_s=timeout_s):
            return address
    return addresses[0]


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


def _decode_stderr(data: bytes | str | None) -> str:
    if not data:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace").strip()
    return str(data).strip()


class MacieZmqServerProcess:
    """Start and stop the MACIE zmq_server subprocess."""

    def __init__(self, zmq_address: str = DEFAULT_ZMQ_ADDRESS) -> None:
        self._zmq_address = zmq_address
        self._process: subprocess.Popen | None = None
        self._stderr_file = None

    @property
    def zmq_address(self) -> str:
        return self._zmq_address

    @property
    def started_by_gui(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _read_stderr_file(self) -> str:
        handle = self._stderr_file
        if handle is None:
            return ""
        try:
            handle.flush()
            handle.seek(0)
            return _decode_stderr(handle.read())
        except Exception:
            return ""

    def _close_stderr_file(self) -> None:
        handle = self._stderr_file
        self._stderr_file = None
        if handle is None:
            return
        try:
            handle.close()
        except Exception:
            pass

    def ensure_running(self) -> None:
        if is_zmq_port_open(self._zmq_address):
            return
        for alternate in macie_zmq_addresses():
            if alternate == self._zmq_address:
                continue
            if is_zmq_port_open(alternate):
                self._zmq_address = alternate
                return
        if not AUTO_START_ZMQ_SERVER:
            raise RuntimeError(
                "MACIE ZMQ server is not reachable at "
                f"{', '.join(macie_zmq_addresses())}. "
                "Ensure zmq_server is running on nott-server."
            )

        executable = resolve_zmq_server_executable()
        if executable is None:
            raise RuntimeError(
                "MACIE zmq_server executable not found. Build it under "
                f"{MACIE_DIR / 'macie_exe'} and set zmq_server_executable in config.ini"
            )

        cmd = [str(executable)]
        env = _server_environment()
        ld_path = env.get("LD_LIBRARY_PATH", "")
        logger.debug(
            "Auto-starting zmq_server: cmd=%s cwd=%s LD_LIBRARY_PATH=%r",
            cmd,
            MACIE_DIR,
            ld_path,
        )

        self._close_stderr_file()
        stderr_file = tempfile.TemporaryFile()
        self._stderr_file = stderr_file
        try:
            self._process = subprocess.Popen(
                cmd,
                cwd=str(MACIE_DIR),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
            )
        except OSError as exc:
            self._close_stderr_file()
            raise RuntimeError(
                f"Failed to launch MACIE zmq_server {cmd!r} "
                f"(cwd={MACIE_DIR}, LD_LIBRARY_PATH={ld_path!r}): {exc}"
            ) from exc

        deadline = time.monotonic() + ZMQ_STARTUP_TIMEOUT_S
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                code = self._process.returncode
                stderr = self._read_stderr_file()
                self._process = None
                self._close_stderr_file()
                detail = f"zmq_server exited immediately with code {code}"
                if stderr:
                    detail = f"{detail}: {stderr}"
                raise RuntimeError(detail)
            if is_zmq_port_open(self._zmq_address):
                return
            time.sleep(0.2)

        stderr = self._read_stderr_file()
        self.stop()
        detail = (
            f"zmq_server did not open {self._zmq_address} "
            f"within {ZMQ_STARTUP_TIMEOUT_S:g}s"
        )
        if stderr:
            detail = f"{detail}: {stderr}"
        raise RuntimeError(detail)

    def stop(self) -> None:
        if self._process is None:
            self._close_stderr_file()
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                try:
                    self._process.wait(timeout=3.0)
                except Exception:
                    pass
        self._process = None
        self._close_stderr_file()
