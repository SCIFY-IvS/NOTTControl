import zmq
import time
import threading
import pickle

class InfratecClient:

    def __init__(self, callback):
        self._context = zmq.Context()

        self._req_socket = self._context.socket(zmq.REQ)
        self._req_socket.connect("tcp://172.16.245.130:5555")

        self._callback = callback
    
    def _send_command(self, command):
        self._req_socket.send_string(command)
        reply = self._req_socket.recv_string()

        if not reply == "ok":
            raise Exception(reply)
        return True
    
    def _send_request(self, command):
        self._req_socket.send_string(command)
        reply = self._req_socket.recv_string()

        return reply
    
    def connect(self):
        reply = self._send_command("connect")
        self.subscribe_to_images()
        return reply
    
    def disconnect(self):
        self.unsubscribe_to_images()
        return self._send_command("disconnect")

    def getparam_int32(self, number):
        return self._send_request(f"getparam_int32 {number}")
    
    def setparam_int32(self, number, value):
        return self._send_command(f"setparam_int32 {number} {value}")
            
    def getparam_int64(self, number):
        return self._send_request(f"getparam_int64 {number}") 
        
    def setparam_int64(self, number, value):
        return self._send_command(f"setparam_int64 {number} {value}")
        
    def getparam_double(self, number):
        return self._send_request(f"getparam_double {number}") 
    
    def setparam_double(self, number, value):
        return self._send_command(f"setparam_double {number} {value}")
    
    def getparam_single(self, number):
        return self._send_request(f"getparam_single {number}") 
    
    def setparam_single(self, number, value):
        return self._send_command(f"setparam_single {number} {value}")
    
    def getparam_string(self, number):
        return self._send_request(f"getparam_string {number}") 
    
    def setparam_string(self, number, value):
        return self._send_command(f"setparam_string {number} {value}")
    
    def getparam_idx_int32(self, number, index):
        res = self.irbgrab_object.getparam_idx_int32(number, index)
        return self.extract_parameter_result(res)
        
    def setparam_idx_int32(self, number, index, value):
        res = self.irbgrab_object.setparam_idx_int32(number, index, value)
        
        if hirb.TIRBG_RetDef[res]=='Success':
            return
        else: 
            raise Exception(hirb.TIRBG_RetDef[res]) 

    def getparam_idx_string(self, number, index):
        res = self.irbgrab_object.getparam_idx_string(number, index)
        return self.extract_parameter_result(res)
    
    def setparam_idx_string(self, number, index, string):
        res = self.irbgrab_object.setparam_idx_string(number, index, string)
        
        if hirb.TIRBG_RetDef[res]=='Success':
            return
        else: 
            raise Exception(hirb.TIRBG_RetDef[res]) 
    
    def subscribe_to_images(self):
        self._images_thread = threading.Thread(target = self.listen_to_images, args =([]))
        self._images_thread.start()

    
    def listen_to_images(self):
        self._sub_socket = self._context.socket(zmq.SUB)
        self._sub_socket.connect ("tcp://172.16.245.130:5556")
        self._sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        self._cancel_listen = False
        while not self._cancel_listen:
            [timestamp_bytes, img_bytes] = self._sub_socket.recv_multipart()
            print("Update received")
            start = time.perf_counter()
            img = pickle.loads(img_bytes)
            timestamp = pickle.loads(timestamp_bytes)
            print(timestamp)

            self._callback(timestamp, img)
            stop = time.perf_counter()

            print(stop - start)
    
    def unsubscribe_to_images(self):
        self._cancel_listen = True
        self._images_thread.join()
        self._sub_socket.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    def close(self):
        self._req_socket.close()
        self.unsubscribe_to_images()
        self._context.term()
