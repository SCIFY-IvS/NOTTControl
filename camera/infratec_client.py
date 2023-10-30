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
    
    def connect(self):
        self._req_socket.send_string("connect")
        reply = self._req_socket.recv_string()
        self.subscribe_to_images()

        return reply == "ok"
    
    def disconnect(self):
        self.unsubscribe_to_images()

        self._req_socket.send_string("disconnect")
        reply = self._req_socket.recv_string()

        return reply == "ok"
    
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
