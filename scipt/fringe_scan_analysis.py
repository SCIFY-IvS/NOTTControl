import redis
from datetime import datetime
from datetime import date
from datetime import timedelta

epoch = datetime.utcfromtimestamp(0)

def unix_time_ms(time):
    return round((time - epoch).total_seconds() * 1000.0)

def real_time(unix_time):
    return datetime.utcfromtimestamp(unix_time / 1000)

r = redis.from_url('redis://10.33.178.176:6379')

ts = r.ts()

#Get all data for the fringe scan


start = datetime(2023, 8, 10, 12, 54)
end = datetime(2023, 8, 10, 12, 55)

result_roi1 = ts.range('roi1_max', unix_time_ms(start), unix_time_ms(end))
result_roi2 = ts.range('roi2_max', unix_time_ms(start), unix_time_ms(end))
result_roi3 = ts.range('roi3_max', unix_time_ms(start), unix_time_ms(end))
result_roi4 = ts.range('roi4_max', unix_time_ms(start), unix_time_ms(end))


real_time_results_roi1 = [(real_time(x[0]), x[1]) for x in result_roi1]
real_time_results_roi2 = [(real_time(x[0]), x[1]) for x in result_roi2]
real_time_results_roi3 = [(real_time(x[0]), x[1]) for x in result_roi3]
real_time_results_roi4 = [(real_time(x[0]), x[1]) for x in result_roi4]
