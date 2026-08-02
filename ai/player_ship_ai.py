import math
import random

from utility.constants import *


class PlayerShipAI:
    def __init__(self):
        self.destination = None

    def run_ship_ai(self, ship):
        if self.destination:
            self.move_to_destination(ship)
        else:
            self.destination = random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT)

    def move_to_destination(self, ship):
        """Navigate ship to destination"""
        dx = self.destination[0] - ship.pos_x
        dy = self.destination[1] - ship.pos_y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        # Check if arrived
        if distance < 50.0:
            self.destination = None
            return

        speed = min(SHIP_MAX_SPEED, distance)  # noqa
        ship.vel_x = (dx / distance) * speed
        ship.vel_y = (dy / distance) * speed

    def set_destination(self, destination):
        self.destination = destination
