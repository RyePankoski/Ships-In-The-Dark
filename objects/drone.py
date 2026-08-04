import math
import random
from utility.constants import *


class Drone:
    def __init__(self, x, y, dx=0, dy=0, v=0, is_painted=False):
        self.pos_x = x
        self.pos_y = y
        self.dx = dx
        self.dy = dy
        self.velocity = v
        self.is_painted = is_painted

        self.velocity = 50

        grid_x = int(x // GRID_SIZE)
        grid_y = int(y // GRID_SIZE)
        self.cell = (grid_x, grid_y)

        self.mining_time = 0
        self.mining_timer = 0
        self.mining_timer_cooldown = 10
        self.am_mining = False

        self.target = None

    def run_drone(self, asteroids, dt):

        self.velocity = random.randint(20, 100)

        if self.am_mining:
            self.mining(dt)
            return

        if self.target is None:
            all_asteroids = [a for cell in asteroids.values() for a in cell]
            if all_asteroids:
                self.target = random.choice(all_asteroids)
        else:
            self.move_to_target(dt)

    def mining(self, dt):
        self.mining_timer += dt
        if self.mining_timer > self.mining_timer_cooldown:
            self.mining_timer = 0
            self.am_mining = False

    def move_to_target(self, dt):
        dx = self.target.pos_x - self.pos_x
        dy = self.target.pos_y - self.pos_y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        # Check if arrived
        if distance < 50.0:
            self.target = None
            self.am_mining = True
            return

        # Normalize and apply velocity
        self.dx = (dx / distance) * self.velocity
        self.dy = (dy / distance) * self.velocity

        # Actually move
        self.pos_x += self.dx * dt
        self.pos_y += self.dy * dt
