from client import Client


class Core:
    def __init__(self, screen):
        self.client = Client(screen)

    def run(self, dt):
        self.client.run(dt)
