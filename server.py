from network_layer import NetworkLayer


class Server:
    def __init__(self, network_layer):
        self.network_layer = network_layer
        self.message_queue = []

    def run(self):
        self.listen_for_messages()
        self.parse_messages()

    def listen_for_messages(self):
        while True:
            message = self.network_layer.listen_for_messages()
            if message is not None:
                self.message_queue.append(message)
            else:
                break

    def parse_messages(self):
        for message in self.message_queue:
            if message is not None:
                print(message)

        self.message_queue.clear()



