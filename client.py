from main_scene import MainScene
from util import collect_inputs
from network_layer import NetworkLayer
from server import Server

import json


class Client:
    def __init__(self):
        self.connected = False
        self.network_layer = None
        self.server = None


        self.main_scene = MainScene(self.connected)


        self.hosting = False
        self.joined = False

    def run(self, dt):
        user_inputs = collect_inputs()

        self.main_scene.connected = self.connected
        self.main_scene.run(user_inputs, dt)

        if self.server:
            self.server.run(dt)

        if self.connected:
            self.send_data_to_server(user_inputs)
            self.listen_for_server_data(dt)

        if user_inputs['h'] and not self.hosting:
            self.hosting = True
            self.start_netcode()
            self.start_server()
            self.connected = True

        if user_inputs['j'] and not self.joined:
            self.joined = True
            self.connect_to_server()
            self.connected = True

    def start_netcode(self):
        self.network_layer = NetworkLayer(True, 5000)
        self.network_layer.start()

    def connect_to_server(self):
        self.network_layer = NetworkLayer(False, 5000)
        self.network_layer.start()

        text = "I am connecting to your server"
        message = text.encode()

        server_address = input("Enter server address: ")

        self.network_layer.send_to(message, (server_address, 5000))

    def start_server(self):
        self.server = Server(self.network_layer)
        text = "I am hosting a server"
        message = text.encode()
        self.network_layer.send_to(message, ("127.0.0.1", 5000))

    def send_data_to_server(self, inputs):
        message_dict = {
            'input_data': inputs
        }
        message = json.dumps(message_dict).encode()
        self.network_layer.send_to(message, ("127.0.0.1", 5000))

    def listen_for_server_data(self, dt):
        message = self.network_layer.listen_for_messages()

        if message is not None:
            data, address = message
            try:
                decoded_data = data.decode()
                self.main_scene.inject_server_data(decoded_data)
            except Exception as e:
                print(f"Error decoding data: {e}")