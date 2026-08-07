"""Script control of the open H2RG GUI (same idea as Infratec ``Start record``).

The H2RG window binds a local ZMQ REP socket. From any Python process::

    from nottcontrol.camera.macie.gui_remote import acquire
    acquire()   # runs the GUI Acquire button (display + FITS wait)

Raw ZMQ (Infratec-style)::

    import zmq
    s = zmq.Context.instance().socket(zmq.REQ)
    s.connect("tcp://127.0.0.1:18765")
    s.send_string("acquire")
    print(s.recv_string())   # ok;acquire_done  |  nok;…

Commands: ``acquire``, ``load_newest``, ``ping``, ``status``.

Default bind: ``127.0.0.1:18765`` (``[H2RG DETECTOR] gui_control_*``).
"""

from __future__ import annotations

import threading
from typing import Callable

import zmq

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


def control_address(host: str | None = None, port: int | None = None) -> str:
    h, p = control_endpoint(host, port)
    return f"tcp://{h}:{p}"


class GuiControlServer:
    """Background ZMQ REP server (same pattern as Infratec camera ``socket_server``)."""

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
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._socket: zmq.Socket | None = None

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        ctx = zmq.Context.instance()
        sock = ctx.socket(zmq.REP)
        sock.setsockopt(zmq.LINGER, 0)
        sock.bind(control_address(self.host, self.port))
        self._socket = sock
        self._thread = threading.Thread(
            target=self._serve, name="h2rg-gui-control", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        sock = self._socket
        self._socket = None
        if sock is not None:
            try:
                sock.close(0)
            except zmq.ZMQError:
                pass
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def _serve(self) -> None:
        sock = self._socket
        if sock is None:
            return
        poller = zmq.Poller()
        poller.register(sock, zmq.POLLIN)
        while not self._stop.is_set():
            try:
                events = dict(poller.poll(timeout=500))
            except zmq.ZMQError:
                break
            if sock not in events:
                continue
            try:
                message = sock.recv_string()
            except zmq.ZMQError:
                break
            reply = self._dispatch(message)
            try:
                sock.send_string(reply)
            except zmq.ZMQError:
                break

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
    """Send one command to a running H2RG GUI; return the reply string."""
    address = control_address(host, port)
    timeout = DEFAULT_TIMEOUT_S if timeout_s is None else float(timeout_s)
    timeout_ms = max(1, int(timeout * 1000))
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.LINGER, 0)
    sock.setsockopt(zmq.RCVTIMEO, timeout_ms)
    sock.setsockopt(zmq.SNDTIMEO, min(5_000, timeout_ms))
    try:
        sock.connect(address)
        sock.send_string(command.strip())
        return sock.recv_string().strip()
    finally:
        sock.close(0)


def gui_reachable(host: str | None = None, port: int | None = None) -> bool:
    try:
        reply = send_gui_command("ping", host=host, port=port, timeout_s=2.0)
    except (OSError, zmq.ZMQError, zmq.Again):
        return False
    return reply.startswith("ok")


def acquire(
    *,
    host: str | None = None,
    port: int | None = None,
    timeout_s: float | None = None,
) -> str:
    """Ask the open H2RG GUI to run Acquire (display + FITS wait).

    Requires the H2RG window to be open, Initialized, and not in Live mode.
    Raises ``RuntimeError`` if the GUI is unreachable or acquire fails.
    """
    try:
        reply = send_gui_command(
            "acquire", host=host, port=port, timeout_s=timeout_s
        )
    except zmq.Again as exc:
        raise RuntimeError("H2RG GUI acquire timed out") from exc
    except (OSError, zmq.ZMQError) as exc:
        raise RuntimeError(
            f"H2RG GUI not reachable at {control_address(host, port)} "
            "(open the H2RG window first)"
        ) from exc
    if not reply.startswith("ok"):
        raise RuntimeError(f"H2RG acquire failed: {reply}")
    return reply


def load_newest(
    *,
    host: str | None = None,
    port: int | None = None,
    timeout_s: float = 60.0,
) -> str:
    """Ask the open H2RG GUI to load the newest ramp into the display."""
    try:
        reply = send_gui_command(
            "load_newest", host=host, port=port, timeout_s=timeout_s
        )
    except zmq.Again as exc:
        raise RuntimeError("H2RG GUI load_newest timed out") from exc
    except (OSError, zmq.ZMQError) as exc:
        raise RuntimeError(
            f"H2RG GUI not reachable at {control_address(host, port)}"
        ) from exc
    if not reply.startswith("ok"):
        raise RuntimeError(f"H2RG load_newest failed: {reply}")
    return reply
