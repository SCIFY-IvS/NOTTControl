""" Basic time functions of the NOTT control software """

# Import stuff
from datetime import datetime

# Get epoch
epoch = datetime.utcfromtimestamp(0)

# Function definitions
def unix_time_ms(time):
    return round((time - epoch).total_seconds() * 1000.0)

def real_time(unix_time):
    return datetime.utcfromtimestamp(unix_time / 1000)