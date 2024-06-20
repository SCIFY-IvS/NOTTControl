import redis
from datetime import datetime

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

    def add_roi_values(self, time, max1, avg1, sum1, max2, avg2, sum2, max3, avg3, sum3, max4, avg4, sum4):
        unix_time = self.unix_time_ms(time)

        pipe = self.ts.pipeline()
        pipe.add('roi1_max', unix_time, max1)
        pipe.add('roi2_max', unix_time, max2)
        pipe.add('roi3_max', unix_time, max3)
        pipe.add('roi4_max', unix_time, max4)

        pipe.add('roi1_avg', unix_time, avg1)
        pipe.add('roi2_avg', unix_time, avg2)
        pipe.add('roi3_avg', unix_time, avg3)
        pipe.add('roi4_avg', unix_time, avg4)

        pipe.add('roi1_sum', unix_time, sum1)
        pipe.add('roi2_sum', unix_time, sum2)
        pipe.add('roi3_sum', unix_time, sum3)
        pipe.add('roi4_sum', unix_time, sum4)

        pipe.execute()
    def unix_time_ms(self, time):
        return round((time - self.epoch).total_seconds() * 1000.0)