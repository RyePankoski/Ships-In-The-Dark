import math
import random
from config.constants import *
from objects.base import WorldObject


class Drone(WorldObject):
    kind = 'drone'
    material = 'metallic'

    def __init__(self, x, y, vel_x=0, vel_y=0, speed=0):
        self.pos_x = x
        self.pos_y = y
        self.vel_x = vel_x
        self.vel_y = vel_y

        self.speed = 50
        self.radar_cross_section = 60

        grid_x = int(x // GRID_SIZE)
        grid_y = int(y // GRID_SIZE)
        self.cell = (grid_x, grid_y)

        self.mining_timer = 0
        self.mining_timer_cooldown = 10
        self.am_mining = False

        self.target = None
        self.painted = False

        self.alive = True

    def run_drone(self, asteroids, dt):

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

        distance = math.dist((self.pos_x, self.pos_y), (self.target.pos_x, self.target.pos_y))

        if distance < 50:
            self.target = None
            self.am_mining = True
            return

        # Normalize and apply velocity
        self.vel_x = (dx / distance) * self.speed
        self.vel_y = (dy / distance) * self.speed

        # Actually move
        self.pos_x += self.vel_x * dt
        self.pos_y += self.vel_y * dt
