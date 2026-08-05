from utility.constants import *


class Bullet:
    def __init__(self, x, y, dx, dy, v):
        self.color = None
        self.pos_x = x
        self.pos_y = y
        self.dx = dx
        self.dy = dy
        self.v = v

        self.lifetime = BULLET_LIFETIME
        self.max_lifetime = BULLET_LIFETIME
        self.alive = True

    def run(self, dt):
        self.move(dt)
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.alive = False

        ratio = max(0, self.lifetime / BULLET_LIFETIME) # noqa
        r = 255
        g = int(255 * ratio)
        b = int(255 * ratio)
        self.color = (r, g, b)

    def move(self, dt):
        self.pos_x += (self.dx * self.v) * dt
        self.pos_y += (self.dy * self.v) * dt
