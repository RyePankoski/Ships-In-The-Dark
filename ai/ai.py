import math
import random

from utility.constants import *

class AI:
    def __init__(self, ship):
        self.destination = None
        self.ship = ship

    def run_ai(self):
        if self.destination is None:
            self.destination = random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT)
        else:
            self.move_to_destination()

    def move_to_destination(self):
        """Navigate ship to destination"""
        dx = self.destination[0] - self.ship.pos_x
        dy = self.destination[1] - self.ship.pos_y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        # Check if arrived
        if distance < 50.0:
            self.destination = None
            return

        speed = min(SHIP_MAX_SPEED, distance)  # noqa
        self.ship.vel_x = (dx / distance) * speed
        self.ship.vel_y = (dy / distance) * speed

