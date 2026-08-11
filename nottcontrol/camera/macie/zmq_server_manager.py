from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from nottcontrol import config

MACIE_DIR = Path(__file__).resolve().parent
H2RG_SECTION = "H2RG DETECTOR"
DEFAULT_ZMQ_ADDRESS = config.get(
    H2RG_SECTION, "zmq_address", fallback="tcp://nott-server.ster.kuleuven.be:65534"
)
DEFAULT_ZMQ_ADDRESS_ALT = config.get(
    H2RG_SECTION, "zmq_address_alt", fallback="tcp://nott-server.ster.kuleuven.be:5900"
).strip()
AUTO_START_ZMQ_SERVER = config.getboolean(
    H2RG_SECTION, "auto_start_zmq_server", fallback=True
)
ZMQ_SERVER_EXECUTABLE = config.get(
    H2RG_SECTION, "zmq_server_executable", fallback="macie_exe/zmq_server"
)
ZMQ_STARTUP_TIMEOUT_S = config.getfloat(
    H2RG_SECTION, "zmq_startup_timeout_s", fallback=10.0
)
# Teledyne MACIE shared libs live here on nott-server (see Readme.MD).
DEFAULT_MACIE_LIBRARY_PATH = "/usr/local/lib/macie_lib"
MACIE_LIBRARY_PATH = config.get(
    H2RG_SECTION, "macie_library_path", fallback=DEFAULT_MACIE_LIBRARY_PATH
).strip()


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


def _library_path_entries() -> list[str]:
    """Directories to prepend to LD_LIBRARY_PATH for zmq_server."""
    entries: list[str] = []
    for candidate in (
        MACIE_LIBRARY_PATH,
        DEFAULT_MACIE_LIBRARY_PATH,
        str(MACIE_DIR / "libmacie"),
    ):
        path = (candidate or "").strip()
        if not path or path in entries:
            continue
        # Always keep an explicit config value; only auto-add others if present.
        if path == MACIE_LIBRARY_PATH or Path(path).is_dir():
            entries.append(path)
    return entries


def _server_environment() -> dict[str, str]:
    env = os.environ.copy()
    extras = _library_path_entries()
    if extras:
        current = env.get("LD_LIBRARY_PATH", "")
        paths = [p for p in (*extras, current) if p]
        seen: set[str] = set()
        ordered: list[str] = []
        for path in paths:
            if path not in seen:
                seen.add(path)
                ordered.append(path)
        env["LD_LIBRARY_PATH"] = os.pathsep.join(ordered)
    return env


def _local_bind_address(configured: str) -> str:
    """Address to probe after spawning a local zmq_server (binds *:port)."""
    _host, port = parse_zmq_endpoint(configured)
    return f"tcp://127.0.0.1:{port}"


def _read_startup_log(path: Path | None, limit: int = 2000) -> str:
    if path is None or not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    if len(text) > limit:
        return text[-limit:]
    return text


class MacieZmqServerProcess:
    """Start and stop the MACIE zmq_server subprocess."""

    def __init__(self, zmq_address: str = DEFAULT_ZMQ_ADDRESS) -> None:
        self._zmq_address = zmq_address
        self._process: subprocess.Popen | None = None
        self._startup_log: Path | None = None

    @property
    def zmq_address(self) -> str:
        return self._zmq_address

    @property
    def started_by_gui(self) -> bool:
        return self._process is not None and self._process.poll() is None

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
            raise FileNotFoundError(
                "MACIE zmq_server executable not found. Build it under "
                f"{MACIE_DIR / 'macie_exe'} and set zmq_server_executable in config.ini"
            )

        env = _server_environment()
        log_file = tempfile.NamedTemporaryFile(
            prefix="nott_zmq_server_",
            suffix=".log",
            delete=False,
        )
        self._startup_log = Path(log_file.name)
        log_file.close()
        with open(self._startup_log, "w", encoding="utf-8") as log_handle:
            self._process = subprocess.Popen(
                [str(executable)],
                cwd=str(MACIE_DIR),
                env=env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
            )

        local_address = _local_bind_address(self._zmq_address)
        deadline = time.monotonic() + ZMQ_STARTUP_TIMEOUT_S
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                detail = _read_startup_log(self._startup_log)
                ld_path = env.get("LD_LIBRARY_PATH", "")
                message = (
                    f"zmq_server exited immediately with code {self._process.returncode}"
                    f" (LD_LIBRARY_PATH={ld_path!r})"
                )
                if detail:
                    message = f"{message}: {detail}"
                else:
                    message = (
                        f"{message}. Usually missing shared libs under "
                        f"{DEFAULT_MACIE_LIBRARY_PATH} "
                        "(set macie_library_path in config.ini)."
                    )
                raise RuntimeError(message)
            # Prefer configured host; also accept localhost after a local spawn
            # (avoids hairpin/DNS failures when connecting to nott-server's FQDN).
            if is_zmq_port_open(self._zmq_address):
                return
            if is_zmq_port_open(local_address):
                self._zmq_address = local_address
                return
            time.sleep(0.2)

        self.stop()
        raise TimeoutError(
            f"zmq_server did not open {self._zmq_address} (or {local_address}) "
            f"within {ZMQ_STARTUP_TIMEOUT_S:g}s"
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
