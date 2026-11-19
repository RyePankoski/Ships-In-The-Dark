import math

import pygame
from utility.constants import *
from ai.ai import AI
from objects.base import DirectionSteered


class Ship(DirectionSteered):
    kind = 'ship'

    def __init__(self, x=None, y=None, is_player=False, player_id=None, is_ai=False):
        self.player = is_player
        self.pos_x = x
        self.pos_y = y
        self.dir_x = 0
        self.dir_y = 0
        self.speed = 0

        self.player_id = player_id

        self.heading = 0

        if is_ai:
            self.ai = AI(self)
        else:
            self.ai = None

        self.screen_width, self.screen_height = pygame.display.get_desktop_sizes()[0]
        self.rect = pygame.Rect(self.pos_x, self.pos_y, 200, 200)

        # Everything on a Ship is a *fact about the world*: the server owns it in
        # multiplayer and sends it to every client. What a player has switched on
        # or detected lives in core/cockpit.py instead and never leaves the client.
        self.radar_cross_section = 100
        self.health = 100

        self.total_missiles = TOTAL_MISSILES
        self.missile_cooling_down = False
        self.missile_cooldown_timer = 0
        self.missile_cooldown = 1

        self.mining_vessel_sees_you = False
        self.health_low = False
        self.thrusting = False
        self.dampening = True

        self.painted = False  # someone else's laser is on this ship
        self.alive = True
        self.repair_rate = 1

        # Radar hits write here (see RadarSystem); purely informational.
        self.enemy_radar_ping_coordinates = []

        self.took_damage = False
        self.damage_timer = 0
        self.damage_cooldown = 0.2

    @property
    def net_id(self):
        return self.player_id

    @property
    def center(self):
        return self.rect.center

    def on_radar_ping(self, angle):
        self.enemy_radar_ping_coordinates.append(angle)

    def run(self, dt):

        if self.took_damage:
            self.damage_timer += dt
            if self.damage_timer > self.damage_cooldown:
                self.damage_timer = 0
                self.took_damage = False
                self.health -= 1

        if self.health < 20:
            self.health_low = True

            self.health += 1 * dt

        else:
            self.health_low = False

        if self.health <= 0:
            self.alive = False
            return

        if self.ai is not None:
            self.ai.run()

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
        if self.speed > 10:
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

        angle = math.atan2(self.dir_y, -self.dir_x)
        angle = math.degrees(angle) + 90

        self.heading = angle

    def apply_inputs(self, inputs, dt):
        boost_amount = 50 if inputs['left_shift'] else 1

        if inputs["tab"]:
            self.speed *= SHIP_BRAKE_FORCE

        if inputs["left"]:
            self.dir_x -= ANGLE_CHANGE_SPEED * dt
            if self.dir_x < -1:
                self.dir_x = -1
        if inputs["right"]:
            self.dir_x += ANGLE_CHANGE_SPEED * dt
            if self.dir_x > 1:
                self.dir_x = 1
        if inputs["up"]:
            self.dir_y -= ANGLE_CHANGE_SPEED * dt
            if self.dir_y < -1:
                self.dir_y = -1
        if inputs["down"]:
            self.dir_y += ANGLE_CHANGE_SPEED * dt
            if self.dir_y > 1:
                self.dir_y = 1

        length = math.sqrt(self.dir_x ** 2 + self.dir_y ** 2)

        if length != 0:
            self.dir_x /= length
            self.dir_y /= length

        self.dir_x *= 0.95
        self.dir_y *= 0.95

        if inputs['up'] or inputs['left'] or inputs['down'] or inputs['right']:
            self.thrusting = True
            self.speed += (SHIP_THRUST * boost_amount) * dt
        else:
            self.thrusting = False

        if self.speed > SHIP_MAX_SPEED:
            if boost_amount >= 50:
                return

            self.speed = SHIP_MAX_SPEED

    def dampen(self, dt):
        self.speed *= (1 - DAMPENING_FORCE * dt)

    def bounce(self):
        if self.pos_x > WORLD_WIDTH or self.pos_x < 0:
            self.dir_x *= -1
        if self.pos_y > WORLD_HEIGHT or self.pos_y < 0:
            self.dir_y *= -1

    def update_rect(self):
        self.rect.x = self.pos_x
        self.rect.y = self.pos_y
