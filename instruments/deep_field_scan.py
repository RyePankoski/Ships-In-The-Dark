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

        # Last scan's results: (range, kind, is_moving, confidence, object), nearest first
        self.detections = []
        self._bearing_changed = False

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
        return [("DFS ALERT", 'toggle_dfs_alert', dict(lit=self.alert_on, states=("ON", "OFF")))]

    def toggle_alert(self):
        self.alert_on = not self.alert_on
        self.ctx.sfx('keyboard_clack')
        self.ctx.start_cooldown()

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
        self.ctx.start_cooldown()
        self.detections = []

    def scan(self):
        if self.on:
            self.detections = self.run_scan()
            self.ctx.sfx('dfs_scan')
            self.ctx.start_cooldown()
            # Ships caught in the sweep are told they were scanned (the world routes it to them)
            ships = [getattr(c[4], 'player_id', None) for c in self.detections if c[1] == 'ship']
            ships = [pid for pid in ships if pid is not None]
            if ships:
                self.ctx.send_action({'type': 'dfs_scan', 'targets': ships})

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

        if self.scanned and self.warning.update(dt):
            self.scanned = False

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
