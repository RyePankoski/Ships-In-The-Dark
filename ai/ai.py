import math
import random

from utility.constants import *
from utility.util import squared_distance, sqrt_distance


class AI:
    def __init__(self, ship):
        self.destination = None
        self.ship = ship

    def run(self):
        if self.destination is None:
            self.destination = random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT)
        else:
            self.move_to_destination()

    def move_to_destination(self):
        distance, in_range = sqrt_distance((self.ship.pos_x, self.ship.pos_y), (self.destination[0], self.destination[1]), 50)
        if in_range:
            self.destination = None
            return

        dx = self.destination[0] - self.ship.pos_x
        dy = self.destination[1] - self.ship.pos_y

        speed = min(SHIP_MAX_SPEED, distance)  # noqa
        self.ship.dx = (dx / distance) * speed
        self.ship.dy = (dy / distance) * speed
