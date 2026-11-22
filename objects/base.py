import math

from utility.constants import CORRECTION_RATE


class WorldObject:
    """What every thing in the world has in common.

    Naming used everywhere (objects, snapshots, instruments):
        pos_x, pos_y     where it is (a Ship's is its rect's top-left; use `center`)
        speed            how fast it is going: one number, world units per second
        dir_x, dir_y     which way it is going, as a unit-ish direction. Only things
                         that steer by direction have these (Ship, Decoy, Bullet).
        vel_x, vel_y     the real velocity in units per second. Missiles, drones and
                         the mining vessel store these; for the direction-steered
                         things they are worked out as dir * speed.
        heading          degrees, for drawing
        radar_cross_section   how big it looks to a sensor
        painted          somebody's laser is on it
        alive            False once it should be removed

    Sensors read `kind`, `center`, `vel_x`, `vel_y`, `radar_cross_section` and
    `painted` off any object, so they never need to know what class it is.
    """

    kind = 'object'              # what a sensor would call it: 'ship', 'asteroid', ...
    radar_cross_section = 50
    net_id = None

    pos_x = 0
    pos_y = 0
    vel_x = 0.0
    vel_y = 0.0
    speed = 0
    alive = True
    painted = False

    @property
    def center(self):
        return self.pos_x, self.pos_y

    # Client-side only: how far we still are from where the last snapshot said we
    # should be. It is eased out a little each frame instead of jumping.
    err_x = 0.0
    err_y = 0.0

    def ease_correction(self, dt):
        if self.err_x == 0.0 and self.err_y == 0.0:
            return
        k = 1 - math.exp(-CORRECTION_RATE * dt)
        dx, dy = self.err_x * k, self.err_y * k
        self.pos_x += dx
        self.pos_y += dy
        self.err_x -= dx
        self.err_y -= dy

    @property
    def moving(self):
        return abs(self.vel_x) > 0.1 or abs(self.vel_y) > 0.1

    def on_radar_ping(self, angle):
        """A radar pulse bounced off this object, arriving from `angle` (radians)."""


class DirectionSteered(WorldObject):
    """A thing that moves along (dir_x, dir_y) at `speed`: Ship, Decoy, Bullet."""

    dir_x = 0
    dir_y = 0

    @property
    def vel_x(self):
        return self.dir_x * self.speed

    @property
    def vel_y(self):
        return self.dir_y * self.speed
