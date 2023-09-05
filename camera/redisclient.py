import redis
from datetime import datetime

class RedisClient:
    def __init__(self, url):
        self.db = redis.from_url(url)
        self.ts = self.db.ts()
        self.epoch = datetime.utcfromtimestamp(0)

    def add_roi1_max(self, time, value):
        print(time)
        unix_time = self.unix_time_ms(time)
        self.ts.add('roi1_max', unix_time, value)

    def unix_time_ms(self, time):
        return round((time - self.epoch).total_seconds() * 1000.0)