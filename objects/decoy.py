from utility.constants import *

class Decoy:
    def __init__(self, x, y, dx, dy, v):
        self.pos_x = x
        self.pos_y = y
        self.dx = dx
        self.dy = dy
        self.v = v

        self.alive = True
        self.painted = False

        self.lifetime = DECOY_LIFETIME



    def run(self, dt):
        self.move(dt)
        self.life(dt)

    def move(self, dt):

        self.pos_x += (self.dx * self.v) * dt
        self.pos_y += (self.dy * self.v) * dt

    def life(self, dt):
        self.lifetime -= dt

        if self.lifetime <= 0:
            self.alive = False
