import math

import pygame
from utility.constants import *
from ai.ai import AI
from objects.base import DirectionSteered


class Ship(DirectionSteered):
    """Newtonian ship: heading is an angle you turn, thrust pushes along it, and
    velocity is its own vector that keeps going until drag or brakes slow it.

    Velocity is stored as (dir_x, dir_y, speed) so that the rest of the game
    (snapshots, AI, sensors) can keep reading it the same way. Heading is kept
    separately in degrees (0 = up the screen, increasing counter-clockwise).
    """

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
        self.turn_speed = 0.0  # degrees per second, eased toward the turn the keys ask for

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
        self.braking = False  # tab held; drives the BRAKE readout (set from local input)
        self.dampening = True

        self.painted = False  # someone else's laser is on this ship
        self.alive = True
        self.repair_rate = 1

        # Radar hits write here (see RadarSystem); purely informational.
        self.enemy_radar_ping_coordinates = []

        self.took_damage = False
        self.damage_timer = 0
        self.damage_cooldown = 0.2

        # Bumped on every non-fatal asteroid contact. The scene watches for changes
        # and times the on-screen failure effect from there.
        self.impact_count = 0

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

        if not self.thrusting:
            self.dampen(dt)

        self.bounce()

    def coast(self, dt):
        self.move(dt)
        self.update_rect()

        if not self.thrusting:
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

        # Player heading is driven by turning in apply_inputs. AI ships have no
        # turn controls; they steer by setting dir/speed, so they keep facing their motion.
        if self.ai is not None:
            angle = math.atan2(self.dir_y, -self.dir_x)
            self.heading = math.degrees(angle) + 90

    def facing(self):
        """Unit vector the ship's nose points along (screen coordinates)."""
        rad = math.radians(self.heading)
        return -math.sin(rad), -math.cos(rad)

    def apply_inputs(self, inputs, dt):
        boosting = inputs['left_shift']
        speed_cap = SHIP_MAX_SPEED * (BOOST_SPEED_MULT if boosting else 1)

        # Turning: left and right set a turn rate that eases toward its target,
        # so the nose swings up to speed and settles out smoothly.
        turn_input = (1 if inputs['left'] else 0) - (1 if inputs['right'] else 0)
        slowdown = 1 - SHIP_TURN_SLOWDOWN * min(1.0, self.speed / SHIP_MAX_SPEED)
        target = turn_input * SHIP_TURN_RATE * slowdown
        step = SHIP_TURN_ACCEL * dt
        self.turn_speed += max(-step, min(step, target - self.turn_speed))
        self.heading = (self.heading + self.turn_speed * dt) % 360

        # Thrust: up pushes along the nose, down is a weaker reverse burn
        thrust = 0.0
        if inputs['up']:
            thrust = 1.0
        elif inputs['down']:
            thrust = -RETRO_THRUST_FRACTION
        self.thrusting = thrust != 0

        if self.thrusting:
            accel = SHIP_THRUST * (BOOST_THRUST_MULT if boosting else 1) * thrust
            fx, fy = self.facing()
            # Never let thrust add speed beyond the cap, but don't cut a ship that is already over it
            self._set_velocity(self.vel_x + fx * accel * dt,
                               self.vel_y + fy * accel * dt,
                               max(speed_cap, self.speed))

        # Brakes: a hard, frame-rate independent bleed of velocity
        self.braking = bool(inputs['tab'])
        if self.braking:
            factor = math.exp(-BRAKE_DRAG * dt)
            self._set_velocity(self.vel_x * factor, self.vel_y * factor)

    def dampen(self, dt):
        """Drag while coasting. Flight assist (dampener on) bleeds speed quickly;
        with it off the ship keeps drifting."""
        k = FLIGHT_ASSIST_DRAG if self.dampening else DRIFT_DRAG
        factor = math.exp(-k * dt)
        self._set_velocity(self.vel_x * factor, self.vel_y * factor)

    def _set_velocity(self, vx, vy, max_speed=SHIP_MAX_SPEED):
        """Store a velocity vector as (dir, speed), clamped to max_speed."""
        s = math.hypot(vx, vy)
        if s > max_speed:
            vx *= max_speed / s
            vy *= max_speed / s
            s = max_speed
        self.speed = s
        if s > 0:
            self.dir_x = vx / s
            self.dir_y = vy / s
        else:
            self.dir_x = 0
            self.dir_y = 0

    def bounce(self):
        if self.pos_x > WORLD_WIDTH or self.pos_x < 0:
            self.dir_x *= -1
        if self.pos_y > WORLD_HEIGHT or self.pos_y < 0:
            self.dir_y *= -1

    def update_rect(self):
        self.rect.x = self.pos_x
        self.rect.y = self.pos_y
