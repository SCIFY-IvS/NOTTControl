import zmq
from datetime import datetime, timezone
import json

#TODO: this returns an empty string if the parameter value is '0'
# It will return the literal 'ERROR' if the parameter does not exist
def read_parameter(param_name: str):
    #  Socket to talk to server
    context = zmq.Context()
    print ("Connecting to MCS...")
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://10.33.179.102:7050")

    obj = {"command" : {"name" : "read", "time" : datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'), "parameter" : {"name" : param_name}}} 

    message = json.dumps(obj)
    print ("Sending request ", message,"...")
    socket.send_string(message)

    #  Get the reply.
    reply = socket.recv_string()
    print ("Received reply ", message, "[", reply, "]")
    #Trim \x00 character(which indicates end of the string)
    reply_trim = reply.removesuffix(f'\x00')
    #Extract parameter value from the JSON reply:
    reply_json = json.loads(reply_trim)
    param_value = reply_json['reply']['content']
    return param_value

def read_parameter_guiding():
    value = read_parameter('guiding')
    return value == 1

def read_parameter_alt():
    value = read_parameter('alt')
    return float(value)

def read_parameter_lst():
    value = read_parameter('lst')
    return float(value)

def read_parameter_seeing():
    value = read_parameter('seeing')
    return float(value)