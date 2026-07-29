from client import Client


class Core:
    def __init__(self):
        self.client = Client()

    def run(self, dt):
        self.client.run(dt)
