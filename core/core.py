from .client import Client # noqa


class Core:
    def __init__(self, screen):
        self.client = Client(screen)

    def run(self, dt):
        self.client.run(dt)
