import math

import pygame

from instruments.instrument import Instrument
from config.constants import LASER_RANGE, LASER_STEP, GRID_SIZE, LASER_DWELL_TIME


class LaserAssessor(Instrument):
    """The targeting laser: sweep it onto something, lock it, and that's a missile solution.
    Whatever it touches is 'painted', which the other player's ship will notice."""

    def __init__(self, shared_references):
        super().__init__(shared_references)
        self.dwell_timer = 0.0
        self.on = False
        self.painted = False
        self.direction = 0

        self.signature_position = (0, 0)
        self.previous_signature_position = (0, 0)

        self.current_target = None  # the last thing the beam touched, kept after the beam leaves it
        self.previous_target = None
        self.missile_target = None  # what the beam is touching now: the thing a missile would go for
        self.laser_locked = False
        self.tracking_lost = False  # set by the beam; main_scene plays the sound and clears it
        self.turning = False  # swung by hand this frame; main_scene plays the sound from it

        self.see_enemy = False

        self.endpoint = (0, 0)  # where the beam ended last frame
        self.target_type = "Nothing"  # what it ended on
        self.hit_id = None  # net_id of what it is touching: sent to the world as the command's laser_target
        self._unpainted = False
        self.target_distance = 0

    # --- Instrument ---------------------------------------------------------
    def update(self, dt, held_button):
        pressed = pygame.key.get_pressed()
        left = pressed[pygame.K_LEFT] or held_button == 'arrow_key_left'
        right = pressed[pygame.K_RIGHT] or held_button == 'arrow_key_right'

        if self.laser_locked:
            self._lock_laser()

        self.contacts.clear_painted(exclude=self.ship)

        if self.on:
            self.turning = left or right
            self.endpoint, self.target_type = self._march_ray(dt)
            self._change_direction(left, right, dt)
            self._unpainted = False
        else:
            self.see_enemy = False
            self._unpainted = True
            self.turning = None

        # Tell the world what our laser is touching, so the other player gets painted
        # Missiles (and anything else that needs a target) follow what the beam is touching.
        # The lock only keeps the beam on it; it is not required.
        touching = self.on and self.target_type != "NOTHING"
        self.hit_id = getattr(self.current_target, 'net_id', None) if touching else None
        self.missile_target = self.current_target if touching else None

    def toggle_laser(self):
        self.on = not self.on
        self.laser_locked = False
        self.shared_references.sfx('laser')

    def toggle_lock(self):
        if not self.on:
            return
        if self.laser_locked:
            self.shared_references.sfx('laser_turn_off')
            self.laser_locked = False
        elif self.current_target is not None:
            self.shared_references.sfx('laser_locked')
            self.laser_locked = True

    def _march_ray(self, dt):
        rad = math.radians(self.direction)
        dx, dy = math.cos(rad), math.sin(rad)

        ray_x, ray_y = self.ship.center
        travelled = 0.0
        reach = math.ceil(LASER_STEP / GRID_SIZE)

        while 0 < ray_x < self.world.width and 0 < ray_y < self.world.height and travelled < LASER_RANGE:
            travelled += LASER_STEP
            ray_x += dx * LASER_STEP
            ray_y += dy * LASER_STEP

            for contact in self.contacts.near(ray_x, ray_y, reach, exclude=self.ship):
                if not contact.alive:
                    continue

                c_x, c_y = contact.center
                if (c_x - ray_x) ** 2 + (c_y - ray_y) ** 2 < contact.radar_cross_section ** 2:
                    target_type, distance = self.assess_target(c_x, c_y, contact, dt)
                    self.target_distance = distance
                    contact.painted = True
                    self.current_target = contact
                    return (ray_x, ray_y), target_type
        self.dwell_timer = 0
        self.see_enemy = False
        return (ray_x, ray_y), "NOTHING"

    def assess_target(self, x, y, contact, dt):
        self.see_enemy = False
        self.previous_signature_position = self.signature_position
        self.signature_position = (x, y)

        signature_distance = math.hypot(x - self.ship.center[0], y - self.ship.center[1])

        self.previous_target = self.current_target
        self.current_target = contact

        if self.laser_locked and self.previous_target != self.current_target:
            self.laser_locked = False
            self.tracking_lost = True
            self.see_enemy = False

        if self.previous_signature_position == self.signature_position:
            self.dwell_timer = 0
            return "STATIC", signature_distance
        else:
            if contact.kind == 'ship' and self._dwell(dt):
                return "ENEMY SHIP", signature_distance
            else:
                return "MOVING", signature_distance

    def aim_at_mouse(self, ui):
        if not self.on or not pygame.mouse.get_focused() or not pygame.mouse.get_pressed()[0]:
            return
        pos = pygame.mouse.get_pos()
        if ui.buttons.is_over_button(pos):
            return
        # The camera keeps our ship in the middle of the screen
        width, height = ui.view_size()
        dx, dy = pos[0] - width / 2, pos[1] - height / 2
        if dx == 0 and dy == 0:
            return
        self.direction = math.degrees(math.atan2(dy, dx)) % 360
        self.laser_locked = False

    # PRIVATE
    # ------------------------------------------------------------------------

    def _dwell(self, dt):
        self.dwell_timer += dt
        if self.dwell_timer > LASER_DWELL_TIME:
            self.see_enemy = True
            return True
        else:
            self.see_enemy = False
            return False

    def _change_direction(self, left, right, dt):
        if left:
            self.direction -= 40 * dt
            self.laser_locked = False
        if right:
            self.direction += 40 * dt
            self.laser_locked = False

    def _lock_laser(self):
        if self.current_target is None or not self.laser_locked:
            return

        target_x, target_y = self.current_target.center
        origin_x, origin_y = self.ship.center

        angle = math.atan2(target_y - origin_y, target_x - origin_x)
        self.direction = (math.degrees(angle) + 360) % 360

    # DRAW
    # -------------------------------------------------------------------------------------

    def status_line(self):
        return f"BEAM LASER  [{'ACT' if self.on else 'OFF'}]", self.on

    def draw_panel(self, ui):
        ui.draw_laser_targeting_info(self.target_type, self, self.on)

    def draw_overlay(self, ui, camera_x, camera_y):
        ui.draw_laser(self, self.endpoint, camera_x, camera_y, self.on)
