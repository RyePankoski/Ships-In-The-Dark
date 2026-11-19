import math

import pygame
from utility.constants import *
from ai.ai import AI


class Ship:
    def __init__(self, x=None, y=None, is_player=False, player_id=None, is_ai=False):
        self.player = is_player
        self.pos_x = x
        self.pos_y = y
        self.dx = 0
        self.dy = 0
        self.velocity = 0

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
        self.total_velocity = 0
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
        if self.velocity > 0.1:
            return False
        return True

    def cooldowns(self, dt):
        if self.missile_cooling_down:
            self.missile_cooldown_timer += dt
            if self.missile_cooldown_timer > self.missile_cooldown:
                self.missile_cooling_down = False
                self.missile_cooldown_timer = 0

    def move(self, dt):
        self.pos_x += (self.dx * self.velocity) * dt
        self.pos_y += (self.dy * self.velocity) * dt

        angle = math.atan2(self.dy, -self.dx)
        angle = math.degrees(angle) + 90

        self.heading = angle
        self.total_velocity = math.sqrt(self.dx ** 2 + self.dy ** 2)

    def apply_inputs(self, inputs, dt):
        boost_amount = 50 if inputs['left_shift'] else 1

        if inputs["tab"]:
            self.velocity *= SHIP_BRAKE_FORCE

        if inputs["left"]:
            self.dx -= ANGLE_CHANGE_SPEED * dt
            if self.dx < -1:
                self.dx = -1
        if inputs["right"]:
            self.dx += ANGLE_CHANGE_SPEED * dt
            if self.dx > 1:
                self.dx = 1
        if inputs["up"]:
            self.dy -= ANGLE_CHANGE_SPEED * dt
            if self.dy < -1:
                self.dy = -1
        if inputs["down"]:
            self.dy += ANGLE_CHANGE_SPEED * dt
            if self.dy > 1:
                self.dy = 1

        length = math.sqrt(self.dx ** 2 + self.dy ** 2)

        if length != 0:
            self.dx /= length
            self.dy /= length

        self.dx *= 0.95
        self.dy *= 0.95

        if inputs['up'] or inputs['left'] or inputs['down'] or inputs['right']:
            self.thrusting = True
            self.velocity += (SHIP_THRUST * boost_amount) * dt
        else:
            self.thrusting = False

        if self.velocity > SHIP_MAX_SPEED:
            if boost_amount >= 50:
                return

            self.velocity = SHIP_MAX_SPEED

    def dampen(self, dt):
        self.velocity *= (1 - DAMPENING_FORCE * dt)

    def bounce(self):
        if self.pos_x > WORLD_WIDTH or self.pos_x < 0:
            self.dx *= -1
        if self.pos_y > WORLD_HEIGHT or self.pos_y < 0:
            self.dy *= -1

    def update_rect(self):
        self.rect.x = self.pos_x
        self.rect.y = self.pos_y
