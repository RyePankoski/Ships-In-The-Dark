import math
import random

import pygame

from objects.bullet import Bullet
from utility.constants import *


class MiningVessel:
    def __init__(self, x, y, dx=0, dy=0, v=0):
        self.pos_x = x
        self.pos_y = y
        self.dx = dx
        self.dy = dy
        self.v = v
        self.heading = 0
        self.radar_cross_section = 200

        self.rect = pygame.Rect(self.pos_x, self.pos_y, 100, 100)
        self.target = None
        self.painted = False

        self.resting = True

        self.resting_timer = 0
        self.resting_cooldown = 10

        self.shooting = False
        self.shoot_timer = 0
        self.shoot_cooldown = 0.07

        self.player_id = -3
        self.alive = True

        self.asteroids_destroyed = 0

    def run(self, ships, bullets, laser_list, asteroids, dt):
        if not self.alive:
            return

        self.fire_at_enemies(ships, bullets)
        self.gun_timer(dt)
        self.detect_asteroids(laser_list, asteroids)

        if self.resting:
            self.rest(dt)
            return

        if self.asteroids_destroyed == 50:
            self.target = -1000, -1000

        if self.target is None:
            self.target = (random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT))
        else:
            self.move_to_target(dt)

        self.update_rect()

    def detect_asteroids(self, laser_list, asteroids):
        detect_radius = 300
        radius_sq = detect_radius ** 2

        cell_x = int(self.pos_x // GRID_SIZE)
        cell_y = int(self.pos_y // GRID_SIZE)

        # How many cells the radius can reach past the ship's own cell.
        reach = math.ceil(detect_radius / GRID_SIZE)

        for gx in range(cell_x - reach, cell_x + reach + 1):
            for gy in range(cell_y - reach, cell_y + reach + 1):
                cell = (gx, gy)
                if cell not in asteroids:
                    continue

                for asteroid in asteroids[cell]:
                    dx = self.pos_x - asteroid.pos_x
                    dy = self.pos_y - asteroid.pos_y
                    distance_sq = dx ** 2 + dy ** 2

                    if distance_sq < radius_sq:
                        if not any(laser[3] is asteroid for laser in laser_list):
                            self.asteroids_destroyed += 1
                            laser_list.append(
                                [self, (asteroid.pos_x, asteroid.pos_y), 1.5, asteroid]
                            )

    def fire_at_enemies(self, ships, bullets):
        for ship in ships:
            ship_x = ship.pos_x if hasattr(ship, 'pos_x') else ship.rect.center[0]
            ship_y = ship.pos_y if hasattr(ship, 'pos_y') else ship.rect.center[1]

            distance = math.sqrt((ship_x - self.pos_x) ** 2 + (ship_y - self.pos_y) ** 2)
            if distance < 700:
                ship.mining_vessel_sees_you = True
                if not self.shooting:
                    self.shooting = True

                    dx = ship.rect.center[0] - self.rect.center[0]
                    dy = ship.rect.center[1] - self.rect.center[1]

                    length = math.hypot(dx, dy)
                    if length > 0:
                        dx /= length  # Normalize
                        dy /= length

                    spread = 0.15
                    dx += random.uniform(-spread, spread)
                    dy += random.uniform(-spread, spread)

                    bullet = Bullet(self.pos_x, self.pos_y, dx, dy, BULLET_SPEED)
                    bullets.append(bullet)
            else:
                ship.mining_vessel_sees_you = False

    def gun_timer(self, dt):
        if self.shooting:
            self.shoot_timer += dt
            if self.shoot_timer >= self.shoot_cooldown:
                self.shoot_timer = 0
                self.shooting = False

    def rest(self, dt):
        self.resting_timer += dt
        if self.resting_timer > self.resting_cooldown:
            self.resting_timer = 0
            self.resting = False

    def move_to_target(self, dt):
        dx = self.target[0] - self.pos_x
        dy = self.target[1] - self.pos_y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        # Check if arrived
        if distance < 50.0:
            self.target = None
            self.resting = True

            if self.asteroids_destroyed < 50:
                self.alive = False

            return

        # Normalize and apply velocity
        self.dx = (dx / distance) * self.v
        self.dy = (dy / distance) * self.v

        # Actually move
        self.pos_x += self.dx * dt
        self.pos_y += self.dy * dt

        angle = math.atan2(self.dy, -self.dx)
        angle = math.degrees(angle) + 90

        self.heading = angle

    def update_rect(self):
        self.rect.x = self.pos_x
        self.rect.y = self.pos_y
