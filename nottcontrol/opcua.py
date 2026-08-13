"""Synchronous OPC UA helpers on top of ``asyncua.sync.Client``.

``asyncua.sync.Client`` owns a background asyncio ``ThreadLoop``. After a
disconnect or a crashed loop that thread cannot be restarted on the same
instance — callers must construct a new ``Client``. This wrapper always
replaces the client on reconnect and serializes access with a lock so the
main GUI timers cannot race the cryo poll onto a half-dead loop.
"""

from __future__ import annotations

import threading

from asyncua.sync import Client, ThreadLoopNotRunning


class OPCUAConnection:
    def __init__(self, url, timeout=4.0):
        self.url = url
        self.timeout = timeout
        self.client: Client | None = None
        self._connected = False
        self._lock = threading.RLock()

    def _loop_alive(self) -> bool:
        client = self.client
        if client is None:
            return False
        tloop = getattr(client, "tloop", None)
        if tloop is None:
            return False
        try:
            loop = getattr(tloop, "loop", None)
            return bool(
                tloop.is_alive() and loop is not None and loop.is_running()
            )
        except Exception:
            return False

    def _discard_client(self) -> None:
        """Drop the sync client without requiring a live ThreadLoop."""
        client = self.client
        self.client = None
        self._connected = False
        if client is None:
            return
        try:
            client.disconnect()
        except Exception:
            tloop = getattr(client, "tloop", None)
            if tloop is not None and getattr(client, "close_tloop", False):
                try:
                    if tloop.is_alive():
                        tloop.stop()
                except Exception:
                    pass

    def connect(self):
        with self._lock:
            if self._connected and self._loop_alive():
                return
            if self.client is not None and not self._loop_alive():
                self._discard_client()
            if self.client is None:
                self.client = Client(self.url, timeout=self.timeout)
            try:
                self.client.connect()
            except Exception:
                self._discard_client()
                self.client = Client(self.url, timeout=self.timeout)
                self.client.connect()
            self._connected = True

    def disconnect(self):
        with self._lock:
            self._discard_client()

    def reconnect(self):
        with self._lock:
            self._discard_client()
            self.client = Client(self.url, timeout=self.timeout)
            self.client.connect()
            self._connected = True

    def _ensure_connected(self) -> Client:
        if not self._connected or not self._loop_alive():
            self.connect()
        assert self.client is not None
        return self.client

    def read_node(self, node_id):
        with self._lock:
            client = self._ensure_connected()
            node = client.get_node(node_id)
            return node.get_value()

    def read_nodes(self, node_ids, fallback_per_node=True):
        with self._lock:
            for attempt in range(2):
                try:
                    client = self._ensure_connected()
                    nodes = [client.get_node(node_id) for node_id in node_ids]
                    return client.read_values(nodes)
                except ThreadLoopNotRunning as batch_error:
                    print(
                        f"OPC UA thread loop stopped ({batch_error}); "
                        "recreating client"
                    )
                    try:
                        self.reconnect()
                    except Exception as reconnect_error:
                        print(f"OPC UA reconnect failed: {reconnect_error}")
                        if attempt == 0:
                            continue
                        if not fallback_per_node:
                            raise
                        break
                except Exception as batch_error:
                    if attempt == 0:
                        print(
                            f"OPC UA batch read failed ({batch_error}), "
                            "reconnecting"
                        )
                        try:
                            self.reconnect()
                        except Exception as reconnect_error:
                            print(
                                f"OPC UA reconnect failed: {reconnect_error}"
                            )
                        continue
                    if not fallback_per_node:
                        raise
                    print(
                        f"OPC UA batch read failed after reconnect "
                        f"({batch_error}), reading nodes individually"
                    )
                    break
            else:
                return []

            values = []
            for node_id in node_ids:
                try:
                    values.append(self.read_node(node_id))
                except Exception as node_error:
                    print(f"OPC UA read failed for {node_id}: {node_error}")
                    values.append(None)
            return values

    def write_node(self, node_id, value):
        with self._lock:
            client = self._ensure_connected()
            node = client.get_node(node_id)
            node.set_value(value)

    def execute_rpc(self, node_id, rpc, arguments):
        with self._lock:
            client = self._ensure_connected()
            parent = client.get_node(node_id)
            return parent.call_method(rpc, *arguments)
