import redis
from datetime import datetime
from nottcontrol.camera.infratec.utils.utils import BrightnessResults
from nottcontrol.sensors import coerce_sensor_value
import json

class RedisClient:
    def __init__(self, url):
        self._url = url
        self.db = redis.from_url(url)
        self.ts = self.db.ts()
        self.epoch = datetime.utcfromtimestamp(0)
        self._available: bool | None = None
        self._last_error: str | None = None

    @property
    def url(self) -> str:
        return self._url

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def is_available(self, *, force: bool = False) -> bool:
        if not force and self._available is not None:
            return self._available
        try:
            self.db.ping()
        except redis.RedisError as exc:
            self._available = False
            self._last_error = str(exc)
            return False
        self._available = True
        self._last_error = None
        return True

    def _mark_unavailable(self, exc: Exception) -> None:
        self._available = False
        self._last_error = str(exc)

    def add_cam_framerate(self,time,framerate):
        unix_time = self.unix_time_ms(time)
        self.ts.add('cam_framerate', unix_time, framerate)
        
    def add_cam_integtime(self,time,integtime):
        unix_time = self.unix_time_ms(time)
        self.ts.add('cam_integtime', unix_time, integtime)

    def add_cam_integtimes(self, entries: list[tuple[datetime, int]]) -> None:
        if not entries:
            return
        pipe = self.ts.pipeline()
        for time, integtime in entries:
            pipe.add('cam_integtime', self.unix_time_ms(time), integtime)
        pipe.execute()
        
    def add_dl_position(self, motor, time, pos):
        unix_time = self.unix_time_ms(time)
        self.ts.add(f'{motor}_pos', unix_time, pos)
    
    def add_shutter_position(self, shutter, time, position):
        unix_time = self.unix_time_ms(time)
        self.ts.add(f'{shutter}_pos', unix_time, position)

    def add_roi_values(self, time, roi_results: dict[str, BrightnessResults]):
        unix_time = self.unix_time_ms(time)

        pipe = self.ts.pipeline()

        for key in roi_results.keys():
            brightness_result = roi_results[key]
            pipe.add(f'{key}_max', unix_time, brightness_result.max)
            pipe.add(f'{key}_avg', unix_time, brightness_result.avg)
            pipe.add(f'{key}_sum', unix_time, brightness_result.sum)

        pipe.execute()
        
    def unix_time_ms(self, time):
        return round((time - self.epoch).total_seconds() * 1000.0)

    def fetch_timeseries_range(
        self, key: str, start_ms: int, end_ms: int
    ) -> tuple[list[float], list[float]]:
        """Return (unix_seconds, values) for a Redis TimeSeries key."""
        if not self.is_available():
            return [], []
        try:
            samples = self.ts.range(key, start_ms, end_ms)
        except redis.RedisError as exc:
            self._mark_unavailable(exc)
            return [], []
        if not samples:
            return [], []
        times = [sample[0] / 1000.0 for sample in samples]
        values = [float(sample[1]) for sample in samples]
        return times, values
    
    def save_DL_pos(self, dl_pos_json):
        self.db.json().set("saved_pos", "$", dl_pos_json)
    
    def load_DL_pos(self):
        saved_pos = self.db.json().get("saved_pos", "$",)
        if saved_pos is None:
            return {}
        else:
            return saved_pos[0]
    
    def save_sensor_values(self, time, redis_keys, sensor_values):
        if not self.is_available():
            return 0, list(redis_keys)
        if len(redis_keys) != len(sensor_values):
            raise ValueError(
                f"sensor key/value count mismatch: {len(redis_keys)} keys, "
                f"{len(sensor_values)} values"
            )
        unix_time = self.unix_time_ms(time)
        pipe = self.ts.pipeline()
        skipped_keys = []
        for key, value in zip(redis_keys, sensor_values):
            number = coerce_sensor_value(value)
            if number is None:
                skipped_keys.append(key)
                continue
            pipe.add(key, unix_time, number)
        if skipped_keys:
            print(
                f"TSDB: skipped {len(skipped_keys)} invalid sensor value(s): "
                f"{', '.join(skipped_keys[:3])}"
                + (" ..." if len(skipped_keys) > 3 else "")
            )
        if len(skipped_keys) < len(redis_keys):
            try:
                pipe.execute()
            except redis.RedisError as exc:
                self._mark_unavailable(exc)
                return 0, list(redis_keys)
        return len(redis_keys) - len(skipped_keys), skipped_keys
