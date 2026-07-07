from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from typing import Callable

import cv2
import numpy
from pathlib import Path

from nottcontrol.redisclient import RedisClient


@dataclass(frozen=True)
class SaveJob:
    filepath: str
    image: numpy.ndarray
    timestamp: datetime
    integtime: int


class FrameWriter:
    """Background disk writer with batched Redis integration-time updates."""

    def __init__(
        self,
        redis_client: RedisClient,
        *,
        queue_size: int = 256,
        png_compression: int = 1,
        redis_batch_size: int = 20,
        on_frame_saved: Callable[[str], None] | None = None,
    ) -> None:
        self._redis = redis_client
        self._png_compression = png_compression
        self._redis_batch_size = redis_batch_size
        self._on_frame_saved = on_frame_saved
        self._queue: queue.Queue[SaveJob | None] = queue.Queue(maxsize=queue_size)
        self._pending_redis: list[tuple[datetime, int]] = []
        self._pending_lock = threading.Lock()
        self._created_dirs: set[str] = set()
        self._dropped = 0
        self._saved = 0
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="frame-writer"
        )
        self._thread.start()

    def enqueue(
        self, filepath: str, image: numpy.ndarray, timestamp: datetime, integtime: int
    ) -> bool:
        try:
            self._queue.put_nowait(
                SaveJob(filepath, image, timestamp, integtime)
            )
            return True
        except queue.Full:
            self._dropped += 1
            return False

    def pending(self) -> int:
        return self._queue.qsize()

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def saved(self) -> int:
        return self._saved

    def flush_redis(self) -> None:
        with self._pending_lock:
            self._flush_redis_locked()

    def drain(self, timeout: float = 30.0) -> None:
        deadline = time.perf_counter() + timeout
        while self.pending() > 0 and time.perf_counter() < deadline:
            time.sleep(0.02)
        self.flush_redis()

    def stop(self, timeout: float = 10.0) -> None:
        self._running = False
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            try:
                self._queue.put_nowait(None)
                break
            except queue.Full:
                time.sleep(0.02)
        remaining = max(0.0, deadline - time.perf_counter())
        self._thread.join(timeout=remaining)
        self.flush_redis()

    def _run(self) -> None:
        while True:
            try:
                job = self._queue.get(timeout=0.1)
            except queue.Empty:
                self.flush_redis()
                if not self._running:
                    break
                continue

            if job is None:
                self._queue.task_done()
                break

            self._write_frame(job)
            self._queue.task_done()

        self.flush_redis()

    def _write_frame(self, job: SaveJob) -> None:
        path = Path(job.filepath)
        parent_key = str(path.parent)
        if parent_key not in self._created_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._created_dirs.add(parent_key)

        cv2.imwrite(
            job.filepath,
            job.image,
            [cv2.IMWRITE_PNG_COMPRESSION, self._png_compression],
        )
        self._saved += 1
        if self._on_frame_saved is not None:
            self._on_frame_saved(job.filepath)

        with self._pending_lock:
            self._pending_redis.append((job.timestamp, job.integtime))
            if len(self._pending_redis) >= self._redis_batch_size:
                self._flush_redis_locked()

    def _flush_redis_locked(self) -> None:
        if not self._pending_redis:
            return
        batch = self._pending_redis
        self._pending_redis = []
        self._redis.add_cam_integtimes(batch)
