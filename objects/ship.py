import math

import pygame
from config.constants import *
from objects.base import DirectionSteered
from utility.geometry import map_to_range_linear, map_to_range_log
from utility.timer import Timer


class Ship(DirectionSteered):
    kind = 'ship'
    material = 'metallic'

    def __init__(self, x=None, y=None, player_id=None, is_ai=False):
        self.pos_x = x
        self.pos_y = y
        self.dir_x = 0
        self.dir_y = 0
        self.speed = 0
        self.is_ai = is_ai

        self.player_id = player_id

        self.heading = 0
        self.turn_speed = 0.0
        self.turning = False

        self.screen_width, self.screen_height = pygame.display.get_desktop_sizes()[0]
        self.rect = pygame.Rect(self.pos_x, self.pos_y, 200, 200)

        # Stealth related
        self.radar_cross_section = 100
        self.visibility = 0
        self.health = SHIP_MAX_HEALTH

        # Power related
        self.fuel = SHIP_MAX_FUEL
        self.current_draw = 0
        self.fuel_acknowledge = False
        self.low_fuel = False
        self.laser_on = False
        # Mining beam: the switch is a power flag; target and progress are facts the
        # world works out (see simulation/world.py: _step_mining).
        self.mining_on = False
        self.mining_target = None  # net_id of the rock being mined
        self.mining_progress = 0.0  # 0.0 to 1.0
        self.prox_scan_on = False
        self.blinking = False
        self.deep_field_on = False
        self.radar_scan_on = False
        self.material_assessor_on = False
        self.dfs_detector_on = True
        self.range_bands_on = False

        self.max_speed = SHIP_MAX_SPEED

        self.total_missiles = TOTAL_MISSILES
        self.missile_cooling_down = False
        self.missile_cooldown_timer = 0
        self.missile_cooldown = 5

        self.mining_vessel_sees_you = False
        self.health_low = False
        self.thrusting = False
        self.retro_thrust = False
        self.rotate_left = False
        self.rotate_right = False
        self.translate_left = False
        self.translate_right = False
        self.go_silent = False
        self.cloaking_value = 0.0
        self.radiation_buildup = 0.0
        self.time_not_moving = 0.0

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
        self.called_print = 0

        self.position_record = []
        self.position_record.append((self.pos_x, self.pos_y))
        self.record_position_timer = Timer()
        self.was_blinking = False  # blinking as record_flights saw it last frame

    def run_ship(self, dt, width, height):
        self.calculate_draw_and_use_fuel(dt)
        self.calculate_visibility()

        if self.fuel <= 0:
            self.max_speed = THROTTLED_SPEED
            self.cloaking_value = 0.0
        else:
            self.max_speed = SHIP_MAX_SPEED

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

        self.move(dt)
        self.handle_radiation_buildup(dt)
        self.cooldowns(dt)
        self.update_rect()

        if not self.thrusting:
            self.dampen(dt)

        self.bounce(width, height)

    def record_position(self, dt):

        if not self.record_position_timer.is_running():
            self.record_position_timer.start(POSITION_RECORD_SECONDS)
            self.position_record.append((int(self.pos_x), int(self.pos_y)))
        else:
            self.record_position_timer.update(dt)

    def calculate_visibility(self):
        self.visibility = map_to_range_log(self.cloaking_value, 0, 5, 255, 0, 0.08)

    def calculate_draw_and_use_fuel(self, dt):

        if self.is_ai:
            return

        if self.fuel < SHIP_MAX_FUEL * LOW_FUEL_FRACTION:
            self.low_fuel = True
        else:
            self.low_fuel = False

        self.current_draw = 0

        cloak_draw = map_to_range_linear(self.cloaking_value, 0, 5, 0, 10)
        self.current_draw += cloak_draw

        if self.thrusting:
            self.current_draw += THRUST_DRAW
        if self.braking:
            self.current_draw += BRAKING_DRAW  # Up from 0.5
        if self.dampening:
            self.current_draw += DAMPENING_DRAW  # Down from 1
        if self.turning:
            self.current_draw += TURNING_DRAW  # Down from 0.5

        if self.laser_on:
            self.current_draw += LASER_DRAW
        if self.deep_field_on:
            self.current_draw += DEEP_FIELD_DRAW  # Down from 1
        if self.prox_scan_on:
            self.current_draw += PROXIMITY_SCAN_DRAW
        if self.radar_scan_on:
            self.current_draw += RADAR_SCAN_DRAW

        if self.material_assessor_on:
            self.current_draw += MATERIAL_ASSESSOR_DRAW  # Down from 0.5
        if self.dfs_detector_on:
            self.current_draw += DFS_DETECTOR_DRAW
        if self.range_bands_on:
            self.current_draw += RANGE_BANDS_DRAW  # Up from 0.5

        if self.mining_on and self.mining_target is not None:
            self.current_draw += MINING_DRAW
        if self.blinking:
            self.current_draw += BLINKING_DRAW

        use = self.current_draw / 45 * dt * TICK_RATE
        self.fuel -= use

    @property
    def net_id(self):
        return self.player_id

    @property
    def center(self):
        return self.rect.center

    def on_radar_ping(self, angle):
        self.enemy_radar_ping_coordinates.append(angle)

    def coast(self, dt, width, height):
        self.move(dt)
        self.update_rect()

        if not self.thrusting:
            self.dampen(dt)

        self.bounce(width, height)

    def fire(self):
        if not self.missile_cooling_down:
            self.missile_cooling_down = True
            self.total_missiles -= 1
            return True
        return False

    def can_fire_missile(self):
        if self.missile_cooling_down:
            return False
        return self.total_missiles > 0

    def cooldowns(self, dt):
        if self.missile_cooling_down:
            self.missile_cooldown_timer += dt
            if self.missile_cooldown_timer > self.missile_cooldown:
                self.missile_cooling_down = False
                self.missile_cooldown_timer = 0

    def handle_radiation_buildup(self, dt):
        if self.speed < 1:
            self.time_not_moving += dt
            self.radiation_buildup += ((self.time_not_moving ** 2.0) / 10000.0)
            self.radiation_buildup = min(self.radiation_buildup, 500)
        elif self.speed > 1:
            self.radiation_buildup -= map_to_range_linear(self.speed, 0, 80, 0, 10) * dt
            self.radiation_buildup = max(0.0, self.radiation_buildup)
            self.time_not_moving = 0.0

    def move(self, dt):
        self.pos_x += self.vel_x * dt
        self.pos_y += self.vel_y * dt

    def facing(self):
        rad = math.radians(self.heading)
        return -math.sin(rad), -math.cos(rad)

    def right_vector(self):
        rad = math.radians(self.heading)
        return math.cos(rad), -math.sin(rad)

    def apply_inputs(self, inputs, dt):

        translate = inputs['left_shift']
        speed_cap = self.max_speed

        if self.health < 20:
            speed_cap = THROTTLED_SPEED

        # Turning: left and right set a turn rate that eases toward its target,
        # so the nose swings up to speed and settles out smoothly. With shift held
        # left and right, slide the ship sideways instead, so the nose doesn't turn.
        turn_input = 0 if translate else (1 if inputs['left'] else 0) - (1 if inputs['right'] else 0)
        slowdown = 1 - SHIP_TURN_SLOWDOWN * min(1.0, self.speed / SHIP_MAX_SPEED)
        target = turn_input * SHIP_TURN_RATE * slowdown
        step = SHIP_TURN_ACCEL * dt
        self.turn_speed += max(-step, min(step, target - self.turn_speed))
        self.heading = (self.heading + self.turn_speed * dt) % 360

        self.rotate_left = bool(inputs['left']) and not translate
        self.rotate_right = bool(inputs['right']) and not translate
        self.turning = self.rotate_left or self.rotate_right

        # Thrust: up pushes along the nose, down is a weaker reverse burn
        thrust = 0.0
        if inputs['up']:
            thrust = 1.0
        elif inputs['down']:
            self.retro_thrust = True
            thrust = -RETRO_THRUST_FRACTION
        else:
            self.retro_thrust = False

        # Slide: with shift held, left and right push across the nose
        slide = 0
        if translate:

            slide = (1 if inputs['right'] else 0) - (1 if inputs['left'] else 0)

            if 0 > self.heading > 90 or 270 < self.heading < 360:
                slide = slide
            else:
                slide = -slide

            self.translate_left = slide < 0
            self.translate_right = slide > 0
        else:
            self.translate_left = False
            self.translate_right = False

        self.thrusting = thrust != 0 or slide != 0

        if thrust != 0:
            accel = SHIP_THRUST * 1 * thrust
            fx, fy = self.facing()
            # Never let thrust add speed beyond the cap, but don't cut a ship that is already over it
            self.set_velocity(self.vel_x + fx * accel * dt,
                              self.vel_y + fy * accel * dt,
                              max(speed_cap, self.speed))

        if slide != 0:
            accel = SHIP_THRUST * slide
            rx, ry = self.right_vector()
            self.set_velocity(self.vel_x + rx * accel * dt,
                              self.vel_y + ry * accel * dt,
                              max(speed_cap, self.speed))

        # Brakes: a hard, frame-rate independent bleed of velocity
        self.braking = bool(inputs['tab'])
        if self.braking:
            factor = math.exp(-BRAKE_DRAG * dt)
            self.set_velocity(self.vel_x * factor, self.vel_y * factor)

    def dampen(self, dt):
        k = FLIGHT_ASSIST_DRAG if self.dampening else DRIFT_DRAG
        factor = math.exp(-k * dt)
        self.set_velocity(self.vel_x * factor, self.vel_y * factor)

    def set_velocity(self, vx, vy, max_speed=SHIP_MAX_SPEED):
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

    def bounce(self, width, height):
        if self.pos_x > width or self.pos_x < 0:
            self.dir_x *= -1
        if self.pos_y > height or self.pos_y < 0:
            self.dir_y *= -1

    def update_rect(self):
        self.rect.x = self.pos_x
        self.rect.y = self.pos_y

    def increase_cloaking(self):
        self.cloaking_value += 1
        self.cloaking_value = min(5.0, self.cloaking_value)

    def decrease_cloaking(self):
        self.cloaking_value -= 1
        self.cloaking_value = max(0.0, self.cloaking_value)
