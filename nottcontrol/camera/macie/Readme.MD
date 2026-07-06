This folder contains C++ code that manages the HAWAII science camera, as well as a python interface that communicates to the C++ code using ZMQ.
At the moment, the zmq interface is hardcoded on port 65534 on the same machine (ie. localhost).

In order to compile the C++ code, there are detailed instructions in the MACIE_Installation_notes.txt document. In short:
- Set LD_LIBRARY_PATH:
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib/macie_lib
We don't use .bashrc for this as it interferes with other code!
- Compile the C++ code by running the make files under /libmacie and then /macie_exe
- Run the zmq_server executable. As of now, it needs to be run from this folder! So from here execute ./macie_exe/zmq_server

Now you're able to instantiate the macie_interface class and use it to communicate to the camera.