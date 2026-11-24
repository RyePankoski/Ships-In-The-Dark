import math
from instruments.instrument import Instrument
from config.constants import CORRIDOR_WIDTH, CORRIDOR_DEPTH
from utility.geometry import in_sector
from utility.timer import Timer

# What the DFS makes of each kind of contact: (label it reports, confidence).
# Drones read as 'unknown': this scanner can't tell them apart from anything else.
DFS_CLASSES = {
    'ship': ('ship', 0.8),
    'decoy': ('decoy', 0.6),
    'missile': ('missile', 0.7),
    'asteroid': ('asteroid', 0.7),
    'drone': ('unknown', 0.6),
    'pirate': ('pirate', 0.65),
}
DEFAULT_CLASS = ('unknown', 0.5)


class DeepFieldScan(Instrument):
    """Long, narrow-ish cone in one of eight directions. Slow to point, hears everything in it."""

    keys = (
        ('k', 'toggle_dfs'),
        ('o', 'dfs_scan'),
        ('arrow_key_up', 'dfs_bearing_cw'),
        ('arrow_key_down', 'dfs_bearing_ccw'),
    )

    def __init__(self, ctx):
        super().__init__(ctx)
        self.on = False
        self.direction_index = 0  # 0-7 representing 0°, 45°, 90°, etc.
        self.directions = [0, 45, 90, 135, 180, 225, 270, 315]
        self.corridor_width = CORRIDOR_WIDTH
        self.corridor_depth = CORRIDOR_DEPTH

        # Last scan's results: (range, kind, is_moving, confidence, object), nearest first
        self.detections = []
        self._bearing_changed = False

        # Set when this scanner has been used on us; the warning shows until the timer runs out
        self.scanned = False
        self.warning = Timer(3)

    # --- Instrument ---------------------------------------------------------
    def actions(self):
        return {
            'toggle_dfs': self.toggle,
            'dfs_scan': self.scan,
            'dfs_bearing_cw': lambda: self.turn(1),
            'dfs_bearing_ccw': lambda: self.turn(-1),
        }

    def toggle(self):
        self.on = not self.on
        self.ctx.sfx('dfs_toggle')
        self.ctx.start_cooldown()
        self.detections = []

    def scan(self):
        if self.on:
            self.detections = self.run_scan()
            self.ctx.sfx('dfs_scan')
            self.ctx.start_cooldown()

    def turn(self, step):
        if self.on:
            self.direction_index = (self.direction_index + step) % 8
            self._bearing_changed = True
            self.ctx.sfx('dfs_dir_change')
            self.detections = []
            self.ctx.start_cooldown()

    def update(self, dt, inputs):
        # The turning sound is cut once the bearing stops changing
        if self.on and self.ctx.keys_live and not self._bearing_changed:
            self.ctx.stop_sfx('dfs_dir_change')
        self._bearing_changed = False

        if self.scanned:
            self.warning.arm()
            if self.warning.update(dt):
                self.scanned = False

    def mark_scanned(self):
        """Something has scanned us: show the warning for a few seconds."""
        self.scanned = True
        self.warning.arm()

    def draw_panel(self, ui):
        ui.draw_deep_field_panel(self.detections, self.direction_index, self.on)

    def draw_overlay(self, ui, camera_x, camera_y):
        ui.draw_dfs_corridor(self.ship, self.direction_index, camera_x, camera_y, self.on)

    # --- The scan -----------------------------------------------------------
    def run_scan(self):
        direction_deg = self.directions[self.direction_index]
        player_x, player_y = self.ship.center
        found = []

        for contact in self.contacts.all(exclude=self.ship):
            position = contact.center
            # cardinals scan a half-plane, diagonals a quadrant
            half_width = 90 if direction_deg % 90 == 0 else 45
            if in_sector(player_x, player_y, direction_deg, position, half_width):
                kind, confidence = DFS_CLASSES.get(contact.kind, DEFAULT_CLASS)
                found.append((math.dist((player_x, player_y), position),
                              kind, contact.moving, confidence, contact))

        return sorted(found, key=lambda c: c[0])
