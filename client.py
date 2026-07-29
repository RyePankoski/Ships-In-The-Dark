from main_scene import MainScene
from util import collect_inputs
from network_layer import NetworkLayer
from server import Server


class Client:
    def __init__(self):
        self.network_layer = None
        self.server = None

        self.main_scene = MainScene()

        self.hosting = False
        self.joining = False

        self.start_server = True

    def run(self, dt):
        user_inputs = collect_inputs()
        self.main_scene.run(user_inputs, dt)

        if self.server:
            self.server.run()

        if user_inputs['j']:
            pass

        if user_inputs['h'] and not self.hosting:
            self.hosting = True
            self.start_netcode()


        if user_inputs['m']:
            text = "hello"
            message = text.encode()
            self.network_layer.send_to(message, ("127.0.0.1", 5000))

    def start_netcode(self):
        self.network_layer = NetworkLayer(True, 5000)
        self.network_layer.start()
        self.server = Server(self.network_layer)






