"""Local TCP control channel for the H2RG GUI (script ↔ running window).

Line protocol (one request / one reply)::

    acquire          → ok;acquire_done   | nok;…
    load_newest      → ok;<filename>     | nok;…
    ping             → ok;pong
    status           → ok;initialized=…;busy=…;live=…

Default bind: 127.0.0.1:18765 (override in ``[H2RG DETECTOR]``).
"""

from __future__ import annotations

import socket
import threading
from typing import Callable

from nottcontrol import config

H2RG_SECTION = "H2RG DETECTOR"
DEFAULT_HOST = config.get(H2RG_SECTION, "gui_control_host", fallback="127.0.0.1")
DEFAULT_PORT = config.getint(H2RG_SECTION, "gui_control_port", fallback=18765)
DEFAULT_TIMEOUT_S = config.getfloat(
    H2RG_SECTION, "gui_control_timeout_s", fallback=600.0
)


def control_endpoint(
    host: str | None = None, port: int | None = None
) -> tuple[str, int]:
    return (host or DEFAULT_HOST, int(port if port is not None else DEFAULT_PORT))


class GuiControlServer:
    """Background TCP server; handlers run on the caller-provided callbacks."""

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        on_acquire: Callable[[], str] | None = None,
        on_load_newest: Callable[[], str] | None = None,
        on_status: Callable[[], str] | None = None,
    ) -> None:
        self.host, self.port = control_endpoint(host, port)
        self._on_acquire = on_acquire
        self._on_load_newest = on_load_newest
        self._on_status = on_status
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(8)
        self._sock.settimeout(0.5)
        self._thread = threading.Thread(
            target=self._serve, name="h2rg-gui-control", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def _serve(self) -> None:
        while not self._stop.is_set():
            sock = self._sock
            if sock is None:
                break
            try:
                conn, _addr = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                self._handle_client(conn)
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def _handle_client(self, conn: socket.socket) -> None:
        conn.settimeout(DEFAULT_TIMEOUT_S)
        try:
            raw = b""
            while b"\n" not in raw and len(raw) < 4096:
                chunk = conn.recv(256)
                if not chunk:
                    break
                raw += chunk
        except OSError:
            return
        line = raw.decode("utf-8", errors="replace").strip().split("\n", 1)[0].strip()
        reply = self._dispatch(line)
        try:
            conn.sendall((reply + "\n").encode("utf-8"))
        except OSError:
            pass

    def _dispatch(self, line: str) -> str:
        cmd = line.strip().lower()
        if not cmd or cmd == "ping":
            return "ok;pong"
        if cmd == "status":
            if self._on_status is None:
                return "nok;no_status_handler"
            try:
                return self._on_status()
            except Exception as exc:  # noqa: BLE001 — surface to client
                return f"nok;{exc}"
        if cmd == "acquire":
            if self._on_acquire is None:
                return "nok;no_acquire_handler"
            try:
                return self._on_acquire()
            except Exception as exc:  # noqa: BLE001
                return f"nok;{exc}"
        if cmd in ("load_newest", "load-newest", "newest"):
            if self._on_load_newest is None:
                return "nok;no_load_handler"
            try:
                return self._on_load_newest()
            except Exception as exc:  # noqa: BLE001
                return f"nok;{exc}"
        return f"nok;unknown_command:{cmd}"


def send_gui_command(
    command: str,
    *,
    host: str | None = None,
    port: int | None = None,
    timeout_s: float | None = None,
) -> str:
    """Send one command to a running H2RG GUI; return the reply line."""
    endpoint = control_endpoint(host, port)
    timeout = DEFAULT_TIMEOUT_S if timeout_s is None else float(timeout_s)
    with socket.create_connection(endpoint, timeout=min(5.0, timeout)) as sock:
        sock.settimeout(timeout)
        sock.sendall((command.strip() + "\n").encode("utf-8"))
        raw = b""
        while b"\n" not in raw and len(raw) < 8192:
            chunk = sock.recv(256)
            if not chunk:
                break
            raw += chunk
    return raw.decode("utf-8", errors="replace").strip().split("\n", 1)[0].strip()


def gui_reachable(host: str | None = None, port: int | None = None) -> bool:
    try:
        reply = send_gui_command("ping", host=host, port=port, timeout_s=2.0)
    except OSError:
        return False
    return reply.startswith("ok")
