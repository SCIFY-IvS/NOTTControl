from asyncua.sync import Client


class OPCUAConnection:
    def __init__(self, url, timeout=4.0):
        self.url = url
        self.timeout = timeout
        self.client = Client(url, timeout=timeout)
        self._connected = False

    def connect(self):
        if not self._connected:
            self.client.connect()
            self._connected = True

    def disconnect(self):
        if self._connected:
            try:
                self.client.disconnect()
            finally:
                self._connected = False

    def reconnect(self):
        self.disconnect()
        self.client = Client(self.url, timeout=self.timeout)
        self.connect()

    def read_node(self, node_id):
        node = self.client.get_node(node_id)
        return node.get_value()

    def read_nodes(self, node_ids, fallback_per_node=True):
        nodes = [self.client.get_node(node_id) for node_id in node_ids]
        for attempt in range(2):
            try:
                return self.client.read_values(nodes)
            except Exception as batch_error:
                if attempt == 0:
                    print(f"OPC UA batch read failed ({batch_error}), reconnecting")
                    self.reconnect()
                    nodes = [self.client.get_node(node_id) for node_id in node_ids]
                    continue
                if not fallback_per_node:
                    raise
                print(
                    f"OPC UA batch read failed after reconnect ({batch_error}), "
                    "reading nodes individually"
                )
                values = []
                for node_id in node_ids:
                    try:
                        values.append(self.read_node(node_id))
                    except Exception as node_error:
                        print(f"OPC UA read failed for {node_id}: {node_error}")
                        values.append(None)
                return values

    def write_node(self, node_id, value):
        node = self.client.get_node(node_id)
        node.set_value(value)

    def execute_rpc(self, node_id, rpc, arguments):
        parent = self.client.get_node(node_id)
        res = parent.call_method(rpc, *arguments)
        return res
