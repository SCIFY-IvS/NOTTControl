from macie_interface import MacieInterface

interface = MacieInterface(offline_mode = True)
interface.init_camera()
interface.acquire()
interface.close()

# import zmq

# context = zmq.Context()

# #  Socket to talk to server
# print ("Connecting to hello world server...")
# socket = context.socket(zmq.REQ)
# socket.connect("tcp://localhost:65534")

# socket.send_string("init;macie_exe/config_files/basic_warm_slow.cfg;true")
# message = socket.recv_string()
# print (f"Received reply {message}")

# socket.send_string("initcamera")
# message = socket.recv_string()
# print (f"Received reply {message}")

# socket.send_string("acquire;false")
# message = socket.recv_string()
# print (f"Received reply {message}")