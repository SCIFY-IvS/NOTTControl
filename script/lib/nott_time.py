""" Basic time functions of the NOTT control software """

import time
from datetime import datetime
from datetime import date
from datetime import timedelta

epoch = datetime.utcfromtimestamp(0)

# Function definitions
def unix_time_ms(time):
    return round((time - epoch).total_seconds() * 1000.0)

def real_time(unix_time):
    return datetime.utcfromtimestamp(unix_time / 1000)