from config.constants import *


from objects.base import DirectionSteered


class Bullet(DirectionSteered):
    kind = 'bullet'

    def __init__(self, x, y, dir_x, dir_y, speed):
        self.color = None
        self.pos_x = x
        self.pos_y = y
        self.dir_x = dir_x
        self.dir_y = dir_y
        self.speed = speed

        self.lifetime = BULLET_LIFETIME
        self.max_lifetime = BULLET_LIFETIME
        self.alive = True

    def run(self, dt, width, height):
        self.move(dt)
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.alive = False

        if self.pos_x < 0 or self.pos_x > width or self.pos_y < 0 or self.pos_y > height:
            self.alive = False

        ratio = max(0, self.lifetime / BULLET_LIFETIME) # noqa
        r = 255
        g = int(255 * ratio)
        b = int(255 * ratio)
        self.color = (r, g, b)

    def move(self, dt):
        self.pos_x += self.vel_x * dt
        self.pos_y += self.vel_y * dt
