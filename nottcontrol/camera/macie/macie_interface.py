import os
import ctypes
from threading import Thread, Event
import zmq

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

#Usage: calling init_camera puts the camera in a state where it is ready to acquire images.
#By using the python 'with' statement, you can ensure that both the initialization and the de-initialization are done
class MacieInterface():
    
    def __init__(self, offline_mode = False, config_file="basic_warm_slow.cfg"):
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.REQ)
        self._socket.connect("tcp://localhost:65534")

        #Load ctypes dll, and call initialize
        file = os.path.join(BASE_DIR + "/macie_exe/config_files", config_file)
        self.initialize(file, offline_mode)

        self.continuous_acquisition_running = False
        self._acquiring = Event()
        self._acquiring.clear()
        self._closing = Event()
    
    def __enter__(self):
        self.init_camera()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    def initialize(self, config_file, offline_mode):
        self._socket.send_string(f"init;{config_file};{str(offline_mode).lower()}")
        return self._receive_and_parse_reply()
    
    def power_off(self):
        self._socket.send_string("poweroff")
        return self._receive_and_parse_reply()
    
    def power_on(self):
        self._socket.send_string("poweron")
        return self._receive_and_parse_reply()

    def init_camera(self):
        self._socket.send_string("initcamera")
        
        self._receive_and_parse_reply()

        #Start the thread for continuous acquisition - it won't execute anything until start_continuous_acquisition is called
        thread = Thread(target = self.continuous_acquisition)
        thread.start()
    
    def acquire(self, no_recon = False):
        self._socket.send_string(f"acquire;{str(no_recon).lower()}")
        return self._receive_and_parse_reply()
    
    def get_power(self):
        self._socket.send_string("getpower")
        return self._receive_and_parse_reply()
    
    def close(self):
        self._closing.set()

        self._socket.send_string("close")
        try:
            self._receive_and_parse_reply()
        except Exception as e:
            print(e)
            pass #Best effort, clean up resources on our end anyway

        self._socket.close()
        self._context.term()
    
    def halt_acquisition(self):
        self._socket.send_string("halt")
        return self._receive_and_parse_reply()
    
    def exposure_settings(self, save, ncoadds, nseq, ngroups, nreads, ndrops, nresets):
        message = f"expsettings;{str(save).lower()};{ncoadds};{nseq};{ngroups};{nreads};{ndrops};{nresets}"
        self._socket.send_string(message)
        return self._receive_and_parse_reply()
    
    def frame_settings(self, xWindow: bool, yWindow: bool, x1:int, x2:int, y1:int, y2: int):
        message = f"framesettings;{str(xWindow).lower()};{str(yWindow).lower()};{x1};{x2};{y1};{y2}"
        self._socket.send_string(message)
        return self._receive_and_parse_reply()
    
    def start_continuous_acquisition(self):
        self._acquiring.set()
    
    def stop_continuous_acquisition(self):
        self._acquiring.clear()
    
    def continuous_acquisition(self):
        #Run for as long as the interface is not closed
        while not self._closing.is_set():
            if (self._acquiring.wait(0.1)):
                self.acquire()
    
    def _receive_and_parse_reply(self):
        reply = self._socket.recv_string()
        print (f"Received reply {reply}")
        tokens = reply.split(";")

        if tokens[0] == "ok":
            if len(tokens) == 1:
                return
            else:
                return tokens[1]
        else:
            raise Exception(f"Operation failed: {tokens[1]}")
