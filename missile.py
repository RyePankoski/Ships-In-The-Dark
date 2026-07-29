import math
from constants import *

import pygame


class Missile:
    def __init__(self, x, y, vx, vy, contact):
        self.fuel = MISSILE_FUEL

        self.pos_x = x
        self.pos_y = y
        self.velocity = 0
        self.vel_x = vx
        self.vel_y = vy

        self.contact = contact

        self.heading = 0
        self.rect = pygame.Rect(self.pos_x, self.pos_y, 200, 200)
        self.has_solution = False
        self.alive = True
        self.reached_target = False

    def run(self, dt):

        if self.contact is not None:
            self.has_solution = True

        if self.fuel > 0:
            self.propel(dt)

        if self.has_solution:
            self.steer()

        self.move()
        self.update_rect()

    def steer(self):
        dx = self.contact.pos_x - self.pos_x
        dy = self.contact.pos_y - self.pos_y

        distance = math.sqrt(dx ** 2 + dy ** 2)

        if distance < 25:
            self.alive = False
            self.reached_target = True

        self.vel_x = (dx / distance) * self.velocity
        self.vel_y = (dy / distance) * self.velocity

    def move(self):
        self.pos_x += self.vel_x
        self.pos_y += self.vel_y

        angle = math.atan2(self.vel_y, -self.vel_x)
        angle = math.degrees(angle) + 90
        self.heading = angle

    def propel(self, dt):
        self.velocity += MISSILE_THRUST * dt
        self.fuel -= MISSILE_FUEL_USE_RATE * dt

    def update_rect(self):
        self.rect.x = self.pos_x
        self.rect.y = self.pos_y
