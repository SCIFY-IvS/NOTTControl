from camera.infratec_interface import InfratecInterface, Image
import zmq
from datetime import datetime, timedelta
import pickle
import time
import threading

img_timestamp_ref = None

def callback(context,*args):#, aHandle, aStreamIndex):
    print(datetime.utcnow())
    global img_timestamp_ref
    if img_timestamp_ref is None:
        recording_timestamp = datetime.utcnow()
    else:
        recording_timestamp = None
    
    context.publish_image(recording_timestamp)

class InfratecInterfaceServer:
    def __init__(self):
        self._infratec_interface = InfratecInterface()
        self._context = zmq.Context()

        self._socket_rep = self._context.socket(zmq.REP)
        self._socket_rep.bind("tcp://*:5555")

        self._socket_pub = self._context.socket(zmq.PUB)
        self._socket_pub.bind("tcp://*:5556")

        self._connected = False

        self._handle_commands()
    
    def _handle_commands(self):
        while True:
            message = self._socket_rep.recv_string()
            print ("Received request: ", message)

            match message:
                case "connect":
                    reply = self._connect()
                case "disconnect":
                    reply = self._disconnect()
                case other:
                    reply = "command not known"

            print("Sending reply: ", reply)
            self._socket_rep.send_string(reply)
        print("Done!")
    
    def _connect(self):
        if self._connected:
            return "Already connected"

        success = self._infratec_interface.connect(callback, self)
        if success:
            self._connected = True
            return "ok"
        else:
            return "connect failed"
    
    def _disconnect(self):
        if not self._connected:
            return "Not connected"
        
        success = self._infratec_interface.disconnect()
        if success:
            self._connected = False
            return "ok"
        else:
            return "disconnect failed"
    
    def publish_image(self, recording_timestamp):
        global img_timestamp_ref

        start = time.perf_counter()

        with self._infratec_interface.get_image() as image:
            img = image.get_image_data()
            timestamp_offset = image.get_timestamp()
        
        if img_timestamp_ref is None:
            img_timestamp_ref = recording_timestamp - timedelta(milliseconds=timestamp_offset)
        timestamp = img_timestamp_ref + timedelta(milliseconds=timestamp_offset)

        print(timestamp_offset)

        print("Publishing message!")
        print(timestamp)
        img_bytes = pickle.dumps(img)
        timestamp_bytes = pickle.dumps(timestamp)
        self._socket_pub.send_multipart([timestamp_bytes, img_bytes])

        stop = time.perf_counter()

        print(stop - start)


if __name__ == '__main__':
    server = InfratecInterfaceServer()
