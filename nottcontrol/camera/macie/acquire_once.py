#!/usr/bin/env python3
"""Trigger one H2RG acquire via the running GUI (preferred) or ZMQ.

Prefer the GUI local control socket so the window runs Acquire itself
(display + FITS wait). Falls back to a direct ZMQ ``acquire`` if the GUI
is not listening (display then relies on the FITS watcher, if enabled).

Do **not** run during Live mode.

Example::

    ./nottcontrol/camera/macie/acquire_once.sh
    ./nottcontrol/camera/macie/acquire_once.sh --zmq-only
    ./nottcontrol/camera/macie/acquire_once.sh --zmq-address tcp://nott-server:65534
"""

from __future__ import annotations

import argparse
import sys
import time

import zmq

from nottcontrol import config
from nottcontrol.camera.macie.gui_remote import (
    DEFAULT_HOST as GUI_HOST,
    DEFAULT_PORT as GUI_PORT,
    gui_reachable,
    send_gui_command,
)

H2RG_SECTION = "H2RG DETECTOR"
DEFAULT_ZMQ = config.get(
    H2RG_SECTION, "zmq_address", fallback="tcp://localhost:65534"
)
ACQUIRE_TIMEOUT_MS = config.getint(
    H2RG_SECTION, "zmq_acquire_timeout_ms", fallback=300_000
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire one ramp: prefer the open H2RG GUI control socket, "
            "else talk to zmq_server directly (no ASIC re-Init)."
        )
    )
    parser.add_argument(
        "--gui-host",
        default=GUI_HOST,
        help=f"H2RG GUI control host (default: {GUI_HOST})",
    )
    parser.add_argument(
        "--gui-port",
        type=int,
        default=GUI_PORT,
        help=f"H2RG GUI control port (default: {GUI_PORT})",
    )
    parser.add_argument(
        "--gui-only",
        action="store_true",
        help="Fail if the GUI control socket is not reachable",
    )
    parser.add_argument(
        "--zmq-only",
        action="store_true",
        help="Skip the GUI and send acquire over ZMQ only",
    )
    parser.add_argument(
        "--zmq-address",
        default=DEFAULT_ZMQ,
        help=f"ZMQ endpoint (default: {DEFAULT_ZMQ})",
    )
    parser.add_argument(
        "--recon",
        action="store_true",
        help="Allow ASIC reconfigure on ZMQ acquire (default: no_recon=true)",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=ACQUIRE_TIMEOUT_MS,
        help=f"Timeout in ms (default: {ACQUIRE_TIMEOUT_MS})",
    )
    return parser.parse_args(argv)


def acquire_via_gui(args: argparse.Namespace) -> int:
    timeout_s = max(5.0, args.timeout_ms / 1000.0)
    print(f"Sending acquire → GUI tcp://{args.gui_host}:{args.gui_port}")
    t0 = time.perf_counter()
    try:
        reply = send_gui_command(
            "acquire",
            host=args.gui_host,
            port=args.gui_port,
            timeout_s=timeout_s,
        )
    except (OSError, zmq.ZMQError, zmq.Again) as exc:
        print(f"error: GUI control failed: {exc}", file=sys.stderr)
        return 1
    elapsed = time.perf_counter() - t0
    print(f"Reply ({elapsed:.2f} s): {reply}")
    if not reply.startswith("ok"):
        print("error: GUI acquire failed", file=sys.stderr)
        return 1
    print("Acquire OK (GUI display refreshed).")
    return 0


def acquire_via_zmq(args: argparse.Namespace) -> int:
    no_recon = not args.recon
    message = f"acquire;{str(no_recon).lower()}"

    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.LINGER, 0)
    sock.setsockopt(zmq.RCVTIMEO, int(args.timeout_ms))
    sock.setsockopt(zmq.SNDTIMEO, int(args.timeout_ms))
    sock.connect(args.zmq_address)

    print(f"Sending {message!r} → {args.zmq_address}")
    t0 = time.perf_counter()
    try:
        sock.send_string(message)
        parts = sock.recv_multipart()
    except zmq.Again:
        print("error: ZMQ acquire timed out", file=sys.stderr)
        return 1
    finally:
        sock.close(0)

    elapsed = time.perf_counter() - t0
    header = parts[0].decode("utf-8", errors="replace") if parts else ""
    print(f"Reply ({elapsed:.2f} s): {header}")
    if len(parts) > 1:
        print(f"Preview payload: {len(parts[1])} bytes")
    if not header.startswith("ok"):
        print("error: acquire failed", file=sys.stderr)
        return 1
    print(
        "Acquire OK (if the GUI is open with FITS watch enabled, "
        "the display should refresh shortly)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.gui_only and args.zmq_only:
        print("error: use only one of --gui-only / --zmq-only", file=sys.stderr)
        return 2

    if not args.zmq_only:
        if gui_reachable(args.gui_host, args.gui_port):
            return acquire_via_gui(args)
        if args.gui_only:
            print(
                f"error: H2RG GUI not listening on {args.gui_host}:{args.gui_port}",
                file=sys.stderr,
            )
            return 1
        print(
            f"GUI control not reachable at {args.gui_host}:{args.gui_port}; "
            "falling back to ZMQ."
        )

    return acquire_via_zmq(args)


if __name__ == "__main__":
    raise SystemExit(main())
