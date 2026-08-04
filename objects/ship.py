import math

import pygame
from utility.constants import *
from ai.ai import AI


class Ship:
    def __init__(self, x=None, y=None, is_player=False, player_id=None, is_ai=False):
        self.player = is_player
        self.pos_x = x
        self.pos_y = y
        self.vel_x = 0
        self.vel_y = 0
        self.velocity = 0
        self.player_id = player_id

        self.heading = 0

        if is_ai:
            self.ai = AI(self)
        else:
            self.ai = None

        self.screen_width, self.screen_height = pygame.display.get_desktop_sizes()[0]
        self.rect = pygame.Rect(self.pos_x, self.pos_y, 200, 200)

        self.total_velocity = 0
        self.radar_cross_section = 100

        self.total_missiles = TOTAL_MISSILES
        self.missile_cooling_down = False
        self.missile_cooldown_timer = 0
        self.missile_cooldown = 1

        self.enemy_has_missile_solution = False
        self.catastrophic_warning = False
        self.has_missile_solution = True
        self.close_range_scanning = True
        self.manual_control = True
        self.dfs_scanned = True
        self.scan_used = False
        self.dampening = True
        self.laser_on = False
        self.painted = True
        self.dfs_on = False
        self.alive = True

        self.scan_type = None

        self.ships = []
        self.missiles = []
        self.explosions = []
        self.deep_field_contacts = []
        self.close_range_contacts = []
        self.confirmed_signatures = []
        self.unconfirmed_signatures = []
        self.enemy_radar_ping_coordinates = []

        self.drones = {}
        self.asteroids = {}

    def run(self, dt):

        if self.ai is not None:
            self.ai.run_ai()

        self.move(dt)
        self.cooldowns(dt)
        self.update_rect()

        if self.dampening:
            self.dampen(dt)

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
