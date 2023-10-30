from camera.infratec_interface import InfratecInterface, Image
import zmq
from datetime import datetime, timedelta
import pickle
import time
import threading
from queue import Queue

img_timestamp_ref = None

def callback(context,*args):#, aHandle, aStreamIndex):
    global img_timestamp_ref
    if img_timestamp_ref is None:
        recording_timestamp = datetime.utcnow()
    else:
        recording_timestamp = None
    
    context.prepare_image(recording_timestamp)

class InfratecInterfaceServer:
    def __init__(self):
        self._infratec_interface = InfratecInterface()
        self._context = zmq.Context()

        self._socket_rep = self._context.socket(zmq.REP)
        self._socket_rep.bind("tcp://*:5555")

        self._connected = False

        self._img_queue = Queue()

        publish_thread = threading.Thread(target = self._publish_images, args =([self._context]))
        publish_thread.start()

        self._handle_commands()
    
    def _handle_commands(self):
        while True:
            message = self._socket_rep.recv_string()
            print ("Received request: ", message)
            command = message.split()[0]
            params = message.split()[1:]


            match command:
                case "connect":
                    reply = self._connect()
                case "disconnect":
                    reply = self._disconnect()
                case "getparam_int32":
                    reply = self._getparam_int32(int(params[0]))
                case "getparam_int64":
                    reply = self._getparam_int64(int(params[0]))
                case "getparam_double":
                    reply = self._getparam_double(int(params[0]))
                case "getparam_single":
                    reply = self._getparam_single(int(params[0]))
                case "getparam_string":
                    reply = self._getparam_string(int(params[0]))
                case "setparam_int32":
                    reply = self._setparam_int32(int(params[0]), int(params[1]))
                case "setparam_int64":
                    reply = self._setparam_int64(int(params[0]), int(params[1]))
                case "setparam_double":
                    reply = self._setparam_double(int(params[0]), float(params[1]))
                case "setparam_single":
                    reply = self._setparam_single(int(params[0]), float(params[1]))
                case "setparam_string":
                    reply = self._setparam_string(int(params[0]), params[1])
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
    
    def _getparam_int32(self, param_nb):
        return str(self._infratec_interface.getparam_int32(int(param_nb)))
    def _getparam_int64(self, param_nb):
        return str(self._infratec_interface.getparam_int64(int(param_nb)))
    def _getparam_double(self, param_nb):
        return str(self._infratec_interface.getparam_double(int(param_nb)))
    def _getparam_single(self, param_nb):
        return str(self._infratec_interface.getparam_single(int(param_nb)))
    def _getparam_string(self, param_nb):
        return self._infratec_interface.getparam_string(int(param_nb))
    
    def _setparam_int32(self, param_nb, value):
        try:
            self._infratec_interface.setparam_int32(param_nb, value)
            return "ok"
        except Exception as e:
            return e
    def _setparam_int64(self, param_nb, value):
        try:
            self._infratec_interface.setparam_int64(param_nb, value)
            return "ok"
        except Exception as e:
            return e
    def _setparam_double(self, param_nb, value):
        try:
            self._infratec_interface.setparam_double(param_nb, value)
            return "ok"
        except Exception as e:
            return e
    def _setparam_single(self, param_nb, value):
        try:
            self._infratec_interface.setparam_single(param_nb, value)
            return "ok"
        except Exception as e:
            return e
    def _setparam_string(self, param_nb, value):
        try:
            self._infratec_interface.setparam_string(param_nb, value)
            return "ok"
        except Exception as e:
            return e
    
    def prepare_image(self, recording_timestamp):
        global img_timestamp_ref

        with self._infratec_interface.get_image() as image:
            img = image.get_image_data()
            timestamp_offset = image.get_timestamp()
        
        if img_timestamp_ref is None:
            img_timestamp_ref = recording_timestamp - timedelta(milliseconds=timestamp_offset)
        timestamp = img_timestamp_ref + timedelta(milliseconds=timestamp_offset)

        img_bytes = pickle.dumps(img)
        timestamp_bytes = pickle.dumps(timestamp)

        self._img_queue.put((img_bytes, timestamp_bytes))
    
    def _publish_images(self, context):
        self._socket_pub = self._context.socket(zmq.PUB)
        self._socket_pub.bind("tcp://*:5556")

        while(True):
            img_bytes, timestamp_bytes = self._img_queue.get()
            self._socket_pub.send_multipart([timestamp_bytes, img_bytes])

if __name__ == '__main__':
    server = InfratecInterfaceServer()
