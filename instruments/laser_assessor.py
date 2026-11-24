import math

from instruments.instrument import Instrument
from config.constants import LASER_RANGE, LASER_STEP, GRID_SIZE


class LaserAssessor(Instrument):
    """The targeting laser: sweep it onto something, lock it, and that's a missile solution.
    Whatever it touches is 'painted', which the other player's ship will notice."""

    keys = (
        ('i', 'toggle_laser'),
        ('space', 'laser_lock'),
    )

    def __init__(self, ctx):
        super().__init__(ctx)
        self.on = False
        self.painted = False
        self.direction = 0

        self.signature_position = (0, 0)
        self.previous_signature_position = (0, 0)

        self.current_target = None
        self.previous_target = None
        self.laser_locked = False
        self.tracking_lost = False

        self.endpoint = (0, 0)  # where the beam ended last frame
        self.target_type = "Nothing"  # what it ended on
        self.hit_id = None  # net_id of what it is touching: sent to the world as the command's laser_target
        self._unpainted = False
        self.target_distance = 0

    # --- Instrument ---------------------------------------------------------
    def actions(self):
        return {'toggle_laser': self.toggle, 'laser_lock': self.lock}

    def toggle(self):
        self.on = not self.on
        self.laser_locked = False
        self.ctx.sfx('laser')
        self.ctx.start_cooldown()

    def lock(self):
        if not self.on:
            return
        self.ctx.start_cooldown()
        if self.laser_locked:
            self.ctx.sfx('laser_turn_off')
            self.laser_locked = False
        elif self.current_target is not None:
            self.ctx.sfx('laser_locked')
            self.laser_locked = True

    def update(self, dt, inputs):
        cockpit = self.ctx.cockpit

        if self.on:
            if inputs['arrow_key_left'] or inputs['arrow_key_right']:
                self.ctx.sfx('laser_dir_change')
            else:
                self.ctx.stop_sfx('laser_dir_change')

            self.endpoint, self.target_type = self.shine_laser()
            self.change_direction(inputs, dt)
            self._unpainted = False
        elif not self._unpainted:
            # Our own ship's `painted` comes from the world (someone else's laser), so leave it alone
            self.contacts.clear_painted(exclude=self.ship)
            self._unpainted = True

        # Tell the world what our laser is touching, so the other player gets painted
        touching = self.on and self.target_type != "NOTHING"
        self.hit_id = getattr(self.current_target, 'net_id', None) if touching else None

        # Missiles (and anything else that needs a target) follow what the beam is touching.
        # The lock only keeps the beam on it; it is not required.
        cockpit.target = self.current_target if touching and self.current_target is not None else None
        cockpit.has_missile_solution = cockpit.target is not None

        if self.tracking_lost:
            self.ctx.sfx('laser_lock_lost')
            self.tracking_lost = False

    def status_line(self):
        return f"BEAM LASER  [{'ACT' if self.on else 'OFF'}]", self.on

    def draw_panel(self, ui):
        ui.draw_laser_targeting_info(self.target_type, self, self.on)

    def draw_overlay(self, ui, camera_x, camera_y):
        ui.draw_laser(self, self.endpoint, camera_x, camera_y, self.on)

    # --- The beam -----------------------------------------------------------
    def shine_laser(self):
        if self.laser_locked:
            self.lock_laser()

        target_type = "NOTHING"
        self.contacts.clear_painted(exclude=self.ship)

        rad = math.radians(self.direction)
        dx, dy = math.cos(rad), math.sin(rad)

        ray_x, ray_y = self.ship.center
        travelled = 0.0
        # Neighbour cells to look in, based on the laser's step size
        reach = math.ceil(LASER_STEP / GRID_SIZE)

        while (0 < ray_x < self.world.width and 0 < ray_y < self.world.height
               and travelled < LASER_RANGE):
            travelled += LASER_STEP
            ray_x += dx * LASER_STEP
            ray_y += dy * LASER_STEP

            for contact in self.contacts.near(ray_x, ray_y, reach, exclude=self.ship):
                if not contact.alive:
                    continue
                c_x, c_y = contact.center
                if (c_x - ray_x) ** 2 + (c_y - ray_y) ** 2 < contact.radar_cross_section ** 2:
                    target_type, distance = self.assess_target(c_x, c_y, contact)
                    self.target_distance = distance
                    contact.painted = True
                    self.current_target = contact
                    return (ray_x, ray_y), target_type

        return (ray_x, ray_y), target_type

    def lock_laser(self):
        if self.current_target is None or not self.laser_locked:
            return

        target_x, target_y = self.current_target.center
        origin_x, origin_y = self.ship.center

        angle = math.atan2(target_y - origin_y, target_x - origin_x)
        self.direction = (math.degrees(angle) + 360) % 360

    def assess_target(self, x, y, contact):
        self.previous_signature_position = self.signature_position
        self.signature_position = (x, y)

        signature_distance = math.hypot(x - self.ship.center[0], y - self.ship.center[1])

        self.previous_target = self.current_target
        self.current_target = contact

        if self.laser_locked and self.previous_target != self.current_target:
            self.laser_locked = False
            self.tracking_lost = True

        if self.previous_signature_position == self.signature_position:
            return "STATIC", signature_distance
        else:
            return "MOVING", signature_distance

    def change_direction(self, inputs, dt):
        if inputs['arrow_key_left']:
            self.direction -= 40 * dt
            self.laser_locked = False
        if inputs['arrow_key_right']:
            self.direction += 40 * dt
            self.laser_locked = False

    def set_direction(self, direction):
        self.direction = direction
