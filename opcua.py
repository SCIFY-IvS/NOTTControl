import asyncio
from asyncua import ua
from asyncua.sync import Client
import time



class OPCUAConnection:
    def __init__(self):
        self.client = Client("opc.tcp://10.33.178.141:4840/freeopcua/server/")

    def connect(self):
        self.client.connect()

    def disconnect(self):
        self.client.disconnect()

    def read_node(self, node_id):
        node = self.client.get_node(node_id)
        return node.get_value()
    
    def read_nodes(self, node_ids):
        nodes = [self.client.get_node(node_id) for node_id in node_ids]
        return self.client.read_values(nodes)

    def write_node(self, node_id, value):
        node = self.client.get_node(node_id)
        node.set_value(value)

