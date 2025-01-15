import redis
import time
from datetime import datetime, timedelta
import numpy as np

epoch = datetime.utcfromtimestamp(0)

def unix_time_ms(time):
    return round((time - epoch).total_seconds() * 1000.0)

r = redis.from_url('redis://10.33.178.176:6379')
# Extract data
ts = r.ts()

end   = datetime(2024, 7, 23, 11-2, 19, 57)
start = end - timedelta(seconds=10)

result1 = ts.range('roi1_max', unix_time_ms(start), unix_time_ms(end))

result1 = np.array(result1)

print(result1.shape)

end   = datetime(2024, 7, 23, 11, 19, 57)
start = end - timedelta(seconds=10)
result2 = ts.range('roi1_max', round(start.timestamp()*1000), round(end.timestamp()*1000))
result2 = np.array(result2)

print(result2.shape)
print(np.all(result2 == result1))

