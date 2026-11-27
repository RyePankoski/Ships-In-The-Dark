import math

from instruments.instrument import Instrument
from config import theme
from config.constants import (
    RADAR_PULSE_RANGE, RADAR_PULSE_SPEED,
)
from config.ui_constants import RANGE_BAND_COUNT
from config.precomputed_angles import RADAR_DIRECTIONS

PAINTED_COLOR = theme.AMBER_BRIGHT   # a return off something you've painted with your laser
RETURN_COLOR = theme.GREEN           # an ordinary radar return


class RadarSystem(Instrument):
    """Active sonar-style sweep: rays go out in a circle over many frames and
    each one leaves a blip where it first hits something."""

    def __init__(self, shared_references):
        super().__init__(shared_references)
        self.scanning = False
        self.current_frame = 1
        self.scan_frames = 100
        self.current_ray = 0
        self.scan_resolution = 360
        self.rays_per_frame = None
        self.radar_rays = None

        self.signatures = []  # (x, y, color) blips from the current sweep
        self.prox_scan = None  # set by MainScene: its moving contacts show as red dots

    # --- Instrument ---------------------------------------------------------
    def sweep(self):
        self.shared_references.sfx('radar')
        self.signatures = []
        self.begin_scan()

    def update(self, dt, held_button):
        if self.scanning:
            self.signatures.extend(self.continue_scan())

    def draw_panel(self, ui):
        # The distance rings only show while the range bands are on
        rings = RANGE_BAND_COUNT if self.ship.range_bands_on else 0
        movers = self.prox_scan.moving_now() if self.prox_scan else []
        ui.draw_radar(self.ship, self.signatures, self.scanning, self._sweep_angle(), rings, movers)

    def _sweep_angle(self):
        """Direction of the ray being cast right now, or None when no sweep is running."""
        if not self.scanning or self.radar_rays is None:
            return None
        dx, dy = self.radar_rays[max(0, self.current_ray - 1)]
        return math.atan2(dy, dx)

    def draw_controls(self, ui):
        ui.draw_radar_controls(self.scanning)

    # --- The scan -----------------------------------------------------------
    def begin_scan(self):
        self.scanning = True
        self.current_frame = 1
        self.current_ray = 0

        self.scan_frames = min(100, self.scan_resolution)
        self.radar_rays = RADAR_DIRECTIONS[self.scan_resolution]
        self.rays_per_frame = self.scan_resolution // self.scan_frames

    def continue_scan(self):
        """Continue an ongoing scan. Returns the signatures found this frame."""
        signatures = []

        if self.current_frame >= self.scan_frames:
            self.scanning = False
            target_ray = self.scan_resolution
        else:
            completion_ratio = self.current_frame / self.scan_frames
            target_ray = int(completion_ratio * self.scan_resolution)

        origin_x, origin_y = self.ship.center

        while self.current_ray < target_ray:
            dx, dy = self.radar_rays[self.current_ray]
            self.current_ray += 1

            ray_distance = 0
            ray_x, ray_y = origin_x, origin_y

            while (0 < ray_x < self.world.width and 0 < ray_y < self.world.height
                   and ray_distance < RADAR_PULSE_RANGE):
                ray_distance += RADAR_PULSE_SPEED
                ray_x += dx * RADAR_PULSE_SPEED
                ray_y += dy * RADAR_PULSE_SPEED

                hit = self._first_hit(ray_x, ray_y)
                if hit is not None:
                    c_x, c_y = hit.center
                    hit.on_radar_ping(math.atan2(origin_y - c_y, origin_x - c_x))
                    signatures.append((ray_x, ray_y, PAINTED_COLOR if hit.painted else RETURN_COLOR))
                    break

        self.current_frame += 1
        return signatures

    def _first_hit(self, ray_x, ray_y):
        for contact in self.contacts.near(ray_x, ray_y, exclude=self.ship):
            c_x, c_y = contact.center
            if (c_x - ray_x) ** 2 + (c_y - ray_y) ** 2 < contact.radar_cross_section ** 2:
                return contact
        return None
