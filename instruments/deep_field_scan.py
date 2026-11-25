import math
import random

from instruments.instrument import Instrument
from config.constants import CORRIDOR_WIDTH, CORRIDOR_DEPTH
from utility.geometry import in_sector
from utility.timer import Timer

# Contacts the DFS reports when moving: enemy ships and their decoys, nothing else
REPORTED_KINDS = ('ship', 'decoy')
# The reported range is off by up to this fraction of the true range, either way
RANGE_ERROR = 0.4


class DeepFieldScan(Instrument):
    """Long, narrow-ish cone in one of eight directions. Slow to point, hears everything in it."""

    # The sound played while we are being swept. None until one is added: put its name
    # in audio_manager's sound list (or use an existing one, e.g. 'dfs_scan_warning').
    SCANNED_WARNING_SECONDS = 2

    def __init__(self, ctx):
        super().__init__(ctx)
        self.on = False
        self.direction_index = 0  # 0-7 representing 0°, 45°, 90°, etc.
        self.directions = [0, 45, 90, 135, 180, 225, 270, 315]
        self.corridor_width = CORRIDOR_WIDTH
        self.corridor_depth = CORRIDOR_DEPTH

        # Last scan's result: has_result once a scan has run, reported_range is the
        # (fuzzed) distance to the nearest mover, or None if nothing moved
        self.has_result = False
        self.reported_range = None
        self.turn_sound = Timer(0.2)  # how long the turning sound lasts after a turn

        # Being swept: set by a 'dfs_scanned' event, cleared when the warning timer runs out
        self.scanned = False
        self.warning = Timer(self.SCANNED_WARNING_SECONDS)
        # The pilot's choice: off means no warning sound and a gray navcom element
        self.alert_on = True

    # --- Instrument ---------------------------------------------------------
    def actions(self):
        return {
            'toggle_dfs': self.toggle,
            'dfs_scan': self.scan,
            'dfs_bearing_cw': lambda: self.turn(1),
            'dfs_bearing_ccw': lambda: self.turn(-1),
            'toggle_dfs_alert': self.toggle_alert,
        }

    def console_buttons(self):
        return [("DFS ALERT", 'toggle_dfs_alert', dict(lit=self.alert_on, states=("ON", "OFF"), sub="WARN WHEN SWEPT BY A DFS"))]

    def toggle_alert(self):
        self.alert_on = not self.alert_on
        self.ctx.sfx('keyboard_clack')

    def warning_state(self):
        """'off' if the pilot turned the alert off, 'active' while we are being swept, else 'idle'."""
        if not self.alert_on:
            return 'off'
        return 'active' if self.scanned else 'idle'

    def mark_scanned(self):
        """We are being swept: show the warning for a while (a repeat scan restarts it).
        The sound plays once per scan, and only while the alert is on."""
        self.scanned = True
        self.warning.start()
        if self.alert_on:
            self.ctx.sfx('dfs_scanned_warning', force=True)

    def toggle(self):
        self.on = not self.on
        self.ctx.sfx('dfs_toggle')
        self.clear_result()

    def clear_result(self):
        self.has_result = False
        self.reported_range = None

    def scan(self):
        if self.on:
            in_sweep = self.contacts_in_sweep()
            self.reported_range = self.nearest_mover_range(in_sweep)
            self.has_result = True
            self.ctx.sfx('dfs_scan')
            # Ships caught in the sweep are told they were scanned (the world routes it to them)
            ships = [getattr(c, 'player_id', None) for _, c in in_sweep if c.kind == 'ship']
            ships = [pid for pid in ships if pid is not None]
            if ships:
                self.ctx.send_action({'type': 'dfs_scan', 'targets': ships})

    def turn(self, step):
        if self.on:
            self.direction_index = (self.direction_index + step) % 8
            self.turn_sound.start()
            self.ctx.sfx('dfs_dir_change')
            self.clear_result()

    def update(self, dt, held_button):
        # The turning sound is cut once the bearing stops changing
        if self.turn_sound.update(dt):
            self.ctx.stop_sfx('dfs_dir_change')

        if self.scanned and self.warning.update(dt):
            self.scanned = False

    def draw_panel(self, ui):
        ui.draw_deep_field_panel(self.has_result, self.reported_range, self.direction_index, self.on)

    def draw_overlay(self, ui, camera_x, camera_y):
        ui.draw_dfs_corridor(self.ship, self.direction_index, camera_x, camera_y, self.on)

    # --- The scan -----------------------------------------------------------
    def contacts_in_sweep(self):
        """(distance, contact) for everything in the pointed sector, nearest first."""
        direction_deg = self.directions[self.direction_index]
        player_x, player_y = self.ship.center
        # cardinals scan a half-plane, diagonals a quadrant
        half_width = 90 if direction_deg % 90 == 0 else 45
        found = [(math.dist((player_x, player_y), c.center), c)
                 for c in self.contacts.all(exclude=self.ship)
                 if in_sector(player_x, player_y, direction_deg, c.center, half_width)]
        return sorted(found, key=lambda f: f[0])

    @staticmethod
    def nearest_mover_range(in_sweep):
        """The distance to the nearest moving enemy or decoy, off by up to RANGE_ERROR
        either way. None if nothing of that sort is moving."""
        for distance, contact in in_sweep:
            if contact.kind in REPORTED_KINDS and contact.moving:
                return distance * (1 + random.uniform(-RANGE_ERROR, RANGE_ERROR))
        return None
