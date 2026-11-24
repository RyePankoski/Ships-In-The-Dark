import math

from instruments.instrument import Instrument
from config.constants import LASER_RANGE

SCAN_TIME_NEAR = 0.2   # seconds for something right under the ship
SCAN_TIME_FAR = 8   # seconds for something at the laser's full range


def scan_time(distance):
    """How long an assessment takes: near is almost instant, far takes most of a dozen seconds."""
    fraction = min(1.0, distance / LASER_RANGE)
    return SCAN_TIME_NEAR + (SCAN_TIME_FAR - SCAN_TIME_NEAR) * fraction


class MaterialAssessor(Instrument):
    """Assesses the material of whatever the beam laser is currently touching.
    The scan runs for a while (longer the farther away the target is). Moving the
    laser off the target, or switching it off, cancels the scan."""

    keys = (('n', 'material_scan'),)

    def __init__(self, ctx, laser):
        super().__init__(ctx)
        self.laser = laser          # the LaserAssessor whose beam we read
        self.scanning = None        # contact being assessed right now
        self.scan_total = 0.0       # how long the current scan takes
        self.scan_left = 0.0        # seconds remaining on the current scan
        self.result = None

    # --- Instrument ---------------------------------------------------------
    def actions(self):
        return {'material_scan': self.start_scan}

    def draw_panel(self, ui):
        ui.draw_material_assessment(self)

    def draw_controls(self, ui):
        ui.draw_material_scan_button(self)

    def update(self, dt, inputs):
        if self.scanning is None:
            return

        # The scan only holds while the beam stays on the same thing
        if self.laser_target() is not self.scanning:
            self.scanning = None
            self.ctx.sfx('scan_interrupt')
            self.ctx.stop_sfx('material_scan')
            return

        self.scan_left -= dt
        if self.scan_left <= 0:
            if getattr(self.scanning, 'kind', None) == 'ship':
                # A ship's hull isn't a material to report: just say what it is
                found = "[ENEMY SHIP]"
            else:
                found = getattr(self.scanning, 'material', 'matter')
            self.result = (self.scanning, found)
            self.scanning = None
            self.ctx.stop_sfx('material_scan')
            self.ctx.sfx('material_scan_complete')

    # --- The scan -----------------------------------------------------------
    def laser_target(self):
        """What the beam is touching right now, or None if it is off or hitting nothing."""
        if not self.laser.on or self.laser.target_type == "NOTHING":
            return None
        return self.laser.current_target

    def start_scan(self):
        if self.scanning is not None:
            return

        target = self.laser_target()
        if target is None:
            return

        dx, dy = target.center[0] - self.ship.center[0], target.center[1] - self.ship.center[1]
        self.ctx.sfx('material_scan')
        self.scanning = target
        self.scan_total = scan_time(math.hypot(dx, dy))
        self.scan_left = self.scan_total
        self.result = None

        print('playing sound')
        self.ctx.start_cooldown()

    def scan_progress(self):
        """0.0 when no scan is running, rising to 1.0 as it completes. For drawing later."""
        if self.scanning is None or self.scan_total <= 0:
            return 0.0


        return 1.0 - self.scan_left / self.scan_total
