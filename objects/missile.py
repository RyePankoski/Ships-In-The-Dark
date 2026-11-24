import math

from objects.asteroid import Asteroid
from config.constants import *

import pygame

from objects.base import WorldObject
from objects.ship import Ship


class Missile(WorldObject):
    kind = 'missile'

    def __init__(self, x, y, vel_x, vel_y, target, owner):
        self.fuel = MISSILE_FUEL
        self.pos_x = x
        self.pos_y = y
        self.speed = 0
        self.vel_x = vel_x
        self.vel_y = vel_y

        self.target = target
        self.owner = owner  # player_id of whoever fired it

        self.heading = 0
        self.has_solution = False
        self.alive = True
        self.reached_target = False
        self.radar_cross_section = 30

        self.exploded_on_type = None
        self.exploded_on_player = False

        # Smoothed avoidance vector (eases toward the feeler's push instead of
        # snapping, so on/off transitions glide rather than jerk).
        self.avoid_x = 0.0
        self.avoid_y = 0.0

    def run(self, dt, asteroids, authoritative=True):
        """authoritative=False is a client guessing between snapshots: it flies the
        same way but never decides a hit (the server does, and tells us)."""

        if self.target is not None:
            self.has_solution = True

        if self.fuel > 0:
            self.propel(dt)

        if self.has_solution:
            self.steer(asteroids, authoritative)

        self.move(dt)

    def steer(self, asteroids, authoritative=True):

        target_x, target_y = self.target.center
        dx = target_x - self.pos_x
        dy = target_y - self.pos_y

        distance = math.hypot(dx, dy)

        if distance < 50:
            if not authoritative:
                return
            self.alive = False
            self.reached_target = True

            if hasattr(self.target, 'alive'):
                print(type(self.target), self.target.alive)

                if isinstance(self.target, Ship):
                    self.target.health -= 90
                else:
                    self.target.alive = False

                self.exploded_on_type = type(self.target)
                # Human pilots have ai set to None; AI ships and other targets don't count
                self.exploded_on_player = getattr(self.target, 'ai', True) is None
            return

        # Seek: unit vector straight at the target
        tx, ty = dx / distance, dy / distance

        # Avoid: raw feeler push this frame (0,0 if path is clear)
        target_ax, target_ay = self._avoidance(tx, ty, asteroids)

        # Ease the stored avoid vector toward the raw push. This is what turns a
        # snappy on/off swerve into a smooth glide, and also damps the side-flip
        # oscillation when a rock sits near dead-center.
        self.avoid_x += (target_ax - self.avoid_x) * MISSILE_AVOID_SMOOTH
        self.avoid_y += (target_ay - self.avoid_y) * MISSILE_AVOID_SMOOTH

        # Blend seek + smoothed avoid, renormalize, scale by speed.
        desired_x = tx + self.avoid_x
        desired_y = ty + self.avoid_y
        d = math.hypot(desired_x, desired_y) or 1.0

        self.vel_x = (desired_x / d) * self.speed
        self.vel_y = (desired_y / d) * self.speed

    def _avoidance(self, tx, ty, asteroids):

        if isinstance(self.target, Asteroid):
            return 0.0, 0.0

        """One feeler marched ahead along the seek direction. On the first rock,
        return a perpendicular push away from it, strength scaled by nearness.
        Returns (0.0, 0.0) if the path ahead is clear."""
        travelled = 0.0
        fx, fy = self.pos_x, self.pos_y

        while travelled < MISSILE_FEELER_LENGTH:
            travelled += MISSILE_FEELER_STEP
            fx += tx * MISSILE_FEELER_STEP
            fy += ty * MISSILE_FEELER_STEP
            for rock in asteroids.near(fx, fy):
                rx, ry = rock.pos_x - fx, rock.pos_y - fy
                if rx * rx + ry * ry < (rock.size + MISSILE_AVOID_CLEARANCE) ** 2:
                    cross = tx * ry - ty * rx  # which side is the rock on?
                    if cross > 0:
                        px, py = ty, -tx  # rock left  -> push right
                    else:
                        px, py = -ty, tx  # rock right -> push left
                    strength = (1.0 - travelled / MISSILE_FEELER_LENGTH) * MISSILE_AVOID_WEIGHT
                    return px * strength, py * strength

        return 0.0, 0.0

    def move(self, dt):
        self.pos_x += self.vel_x * dt
        self.pos_y += self.vel_y * dt

        angle = math.atan2(self.vel_y, -self.vel_x)
        angle = math.degrees(angle) + 90
        self.heading = angle

    def propel(self, dt):
        self.speed += MISSILE_THRUST * dt
        if self.speed > MISSILE_MAX_SPEED:
            self.speed = MISSILE_MAX_SPEED
        self.fuel -= MISSILE_FUEL_USE_RATE * dt
