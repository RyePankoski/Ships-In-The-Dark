import math

import pygame
from constants import *


class Ship:
    def __init__(self, x=None, y=None, is_player=False, player_id=None):
        self.screen_width, self.screen_height = pygame.display.get_desktop_sizes()[0]

        self.player = is_player


        self.pos_x = x
        self.pos_y = y
        self.vel_x = 0
        self.vel_y = 0
        self.player_id = player_id

        self.heading = None
        self.rect = pygame.Rect(self.pos_x, self.pos_y, 200, 200)

        self.dampening = True

        self.total_velocity = 0

    def run(self, dt):
        self.move()
        self.update_rect()

        if self.dampening:
            self.dampen(dt)

        if not self.player:
            self.bounce()

    def move(self):
        self.pos_x += self.vel_x
        self.pos_y += self.vel_y

        angle = math.atan2(self.vel_y, -self.vel_x)
        angle = math.degrees(angle) + 90

        self.heading = angle
        self.total_velocity = math.sqrt(self.vel_x ** 2 + self.vel_y ** 2)

    def apply_inputs(self, inputs, dt):

        if inputs["space"]:
            if self.vel_y > 0:
                self.vel_y -= SHIP_BRAKE_FORCE * dt
            if self.vel_x > 0:
                self.vel_x -= SHIP_BRAKE_FORCE * dt
            if self.vel_x < 0:
                self.vel_x += SHIP_BRAKE_FORCE * dt
            if self.vel_y < 0:
                self.vel_y += SHIP_BRAKE_FORCE * dt

        if inputs["left"]:
            self.vel_x += -SHIP_THRUST * dt
        if inputs["right"]:
            self.vel_x += SHIP_THRUST * dt
        if inputs["up"]:
            self.vel_y += -SHIP_THRUST * dt
        if inputs["down"]:
            self.vel_y += SHIP_THRUST * dt

        if self.vel_x > SHIP_MAX_SPEED:
            self.vel_x = SHIP_MAX_SPEED
        if self.vel_x < -SHIP_MAX_SPEED:
            self.vel_x = -SHIP_MAX_SPEED
        if self.vel_y > SHIP_MAX_SPEED:
            self.vel_y = SHIP_MAX_SPEED
        if self.vel_y < -SHIP_MAX_SPEED:
            self.vel_y = -SHIP_MAX_SPEED

    def dampen(self, dt):
        self.vel_x *= (1 - DAMPENING_FORCE * dt)
        self.vel_y *= (1 - DAMPENING_FORCE * dt)

    def bounce(self):
        if self.pos_x > self.screen_width or self.pos_x < 0 :
            self.vel_x *= -1
        if self.pos_y > self.screen_height or self.pos_y < 0:
            self.vel_y *= -1


    def update_rect(self):
        self.rect.x = self.pos_x
        self.rect.y = self.pos_y


