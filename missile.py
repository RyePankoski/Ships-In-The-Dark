import math
from constants import *

import pygame


class Missile:
    def __init__(self, x, y, vx, vy, contact, owner):
        self.fuel = MISSILE_FUEL

        self.pos_x = x
        self.pos_y = y
        self.velocity = 0
        self.vel_x = vx
        self.vel_y = vy

        self.contact = contact
        self.owner = owner

        self.heading = 0
        self.rect = pygame.Rect(self.pos_x, self.pos_y, 200, 200)
        self.has_solution = False
        self.alive = True
        self.reached_target = False

        # Smoothed avoidance vector (eases toward the feeler's push instead of
        # snapping, so on/off transitions glide rather than jerk).
        self.avoid_x = 0.0
        self.avoid_y = 0.0

    def run(self, dt, asteroids):

        if self.contact is not None:
            self.has_solution = True

        if self.fuel > 0:
            self.propel(dt)

        if self.has_solution:
            self.steer(asteroids)

        self.move(dt)
        self.update_rect()

    def steer(self, asteroids):
        dx = self.contact.pos_x - self.pos_x
        dy = self.contact.pos_y - self.pos_y
        distance = math.hypot(dx, dy)

        if distance < 50:
            self.alive = False
            self.reached_target = True
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

        self.vel_x = (desired_x / d) * self.velocity
        self.vel_y = (desired_y / d) * self.velocity

    def _avoidance(self, tx, ty, asteroids):
        """One feeler marched ahead along the seek direction. On the first rock,
        return a perpendicular push away from it, strength scaled by nearness.
        Returns (0.0, 0.0) if the path ahead is clear."""
        travelled = 0.0
        fx, fy = self.pos_x, self.pos_y

        while travelled < MISSILE_FEELER_LENGTH:
            travelled += MISSILE_FEELER_STEP
            fx += tx * MISSILE_FEELER_STEP
            fy += ty * MISSILE_FEELER_STEP
            cell = (int(fx // GRID_SIZE), int(fy // GRID_SIZE))

            for rock in asteroids.get(cell, []):
                rx, ry = rock.pos_x - fx, rock.pos_y - fy
                if rx * rx + ry * ry < (rock.size + MISSILE_AVOID_CLEARANCE) ** 2:
                    cross = tx * ry - ty * rx           # which side is the rock on?
                    if cross > 0:
                        px, py = ty, -tx                # rock left  -> push right
                    else:
                        px, py = -ty, tx                # rock right -> push left
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
        self.velocity += MISSILE_THRUST * dt
        if self.velocity > MISSILE_MAX_SPEED:
            self.velocity = MISSILE_MAX_SPEED
        self.fuel -= MISSILE_FUEL_USE_RATE * dt

    def update_rect(self):
        self.rect.x = self.pos_x
        self.rect.y = self.pos_y