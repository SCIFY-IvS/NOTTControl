import redis
from datetime import datetime
from camera.utils.utils import BrightnessResults

class RedisClient:
    def __init__(self, url):
        self.db = redis.from_url(url)
        self.ts = self.db.ts()
        self.epoch = datetime.utcfromtimestamp(0)

    def add_dl_position(self, motor, time, pos):
        unix_time = self.unix_time_ms(time)
        self.ts.add(f'{motor}_pos', unix_time, pos)
    
    def add_shutter_position(self, shutter, time, position):
        unix_time = self.unix_time_ms(time)
        self.ts.add(f'{shutter}_pos', unix_time, position)
    
    def add_temperature_1(self, time, temp):
        unix_time = self.unix_time_ms(time)
        self.ts.add('dl_T1', unix_time, temp)

    def add_temperature_2(self, time, temp):
        unix_time = self.unix_time_ms(time)
        self.ts.add('dl_T2', unix_time, temp)

    def add_temperature_3(self, time, temp):
        unix_time = self.unix_time_ms(time)
        self.ts.add('dl_T3', unix_time, temp)

    def add_temperature_4(self, time, temp):
        unix_time = self.unix_time_ms(time)
        self.ts.add('dl_T4', unix_time, temp)

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
    
    def save_DL_pos(self, dl_pos_json):
        self.db.json().set("saved_pos", "$", dl_pos_json)
    
    def load_DL_pos(self):
        return self.db.json().get("saved_pos", "$",)