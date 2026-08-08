import math
import random

from utility.constants import *
from utility.util import squared_distance, sqrt_distance


class PlayerShipAI:
    def __init__(self):
        self.destination = None

    def run(self, ship):
        if self.destination:
            self.move_to_destination(ship)
        else:
            self.destination = random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT)

    def move_to_destination(self, ship):
        """Navigate ship to destination"""
        dx = self.destination[0] - ship.pos_x
        dy = self.destination[1] - ship.pos_y

        distance, in_range = sqrt_distance((ship.pos_x, ship.pos_y), (self.destination[0], self.destination[1]), 50)
        if in_range:
            self.destination = None
            return

        speed = min(SHIP_MAX_SPEED, distance)  # noqa
        ship.dx = (dx / distance) * speed
        ship.dy = (dy / distance) * speed

    def set_destination(self, destination):
        self.destination = destination
