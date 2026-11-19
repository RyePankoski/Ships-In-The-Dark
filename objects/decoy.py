from utility.constants import *

from objects.base import DirectionSteered


class Decoy(DirectionSteered):
    kind = 'decoy'

    def __init__(self, x, y, dir_x, dir_y, speed):
        self.pos_x = x
        self.pos_y = y
        self.dir_x = dir_x
        self.dir_y = dir_y
        self.speed = speed

        self.alive = True
        self.painted = False
        self.radar_cross_section = 100

        self.lifetime = DECOY_LIFETIME




    def run(self, dt):
        self.move(dt)
        self.life(dt)

    def move(self, dt):

        self.pos_x += self.vel_x * dt
        self.pos_y += self.vel_y * dt

    def life(self, dt):
        self.lifetime -= dt

        if self.lifetime <= 0:
            self.alive = False
