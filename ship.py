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

        self.heading = 0
        self.rect = pygame.Rect(self.pos_x, self.pos_y, 200, 200)

        self.dampening = True

        self.total_velocity = 0

        self.missile_cooling_down = False
        self.missile_cooldown_timer = 0
        self.missile_cooldown = 1
        self.total_missiles = TOTAL_MISSILES

    def run(self, dt):
        self.move(dt)
        self.cooldowns(dt)
        self.update_rect()

        if self.dampening:
            self.dampen(dt)

        if not self.player:
            self.bounce()

    def fire(self):
        if not self.missile_cooling_down:
            self.missile_cooling_down = True
            self.total_missiles -= 1
            return True
        return False

    def can_fire(self):
        if self.missile_cooling_down:
            return False
        if self.total_missiles == 0:
            return False
        if self.total_velocity > 0.1:
            return False
        return True

    def cooldowns(self, dt):
        if self.missile_cooling_down:
            self.missile_cooldown_timer += dt
            if self.missile_cooldown_timer > self.missile_cooldown:
                self.missile_cooling_down = False
                self.missile_cooldown_timer = 0

    def move(self, dt):
        self.pos_x += self.vel_x * dt
        self.pos_y += self.vel_y * dt

        angle = math.atan2(self.vel_y, -self.vel_x)
        angle = math.degrees(angle) + 90

        self.heading = angle
        self.total_velocity = math.sqrt(self.vel_x ** 2 + self.vel_y ** 2)

    def apply_inputs(self, inputs, dt):
        boost_amount = 1

        if inputs['shift']:
            boost_amount = 20

        if inputs["space"]:
            if self.vel_y > 0:
                self.vel_y -= (SHIP_BRAKE_FORCE * dt)
            if self.vel_x > 0:
                self.vel_x -= (SHIP_BRAKE_FORCE * dt)
            if self.vel_x < 0:
                self.vel_x += (SHIP_BRAKE_FORCE * dt)
            if self.vel_y < 0:
                self.vel_y += (SHIP_BRAKE_FORCE * dt)

        if inputs["left"]:
            self.vel_x += (-SHIP_THRUST * dt) * boost_amount
        if inputs["right"]:
            self.vel_x += (SHIP_THRUST * dt) * boost_amount
        if inputs["up"]:
            self.vel_y += (-SHIP_THRUST * dt) * boost_amount
        if inputs["down"]:
            self.vel_y += (SHIP_THRUST * dt) * boost_amount

        if self.vel_x > SHIP_MAX_SPEED or self.vel_x < -SHIP_MAX_SPEED:
            self.vel_x *= 0.999
        if self.vel_y > SHIP_MAX_SPEED or self.vel_y < -SHIP_MAX_SPEED:
            self.vel_y *= 0.999

    def dampen(self, dt):
        self.vel_x *= (1 - DAMPENING_FORCE * dt)
        self.vel_y *= (1 - DAMPENING_FORCE * dt)

    def bounce(self):
        if self.pos_x > WORLD_WIDTH or self.pos_x < 0:
            self.vel_x *= -1
        if self.pos_y > WORLD_HEIGHT or self.pos_y < 0:
            self.vel_y *= -1

    def update_rect(self):
        self.rect.x = self.pos_x
        self.rect.y = self.pos_y
