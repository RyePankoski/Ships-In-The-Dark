from instruments.instrument import Instrument
from config.ui_constants import RANGE_BAND_COUNT, RADAR_SCALE

# Contacts worth lighting a band for, when they are moving
WATCHED_KINDS = ('ship', 'missile', 'pirate', 'drone')


def band_index(distance, ring_count, max_range):
    """Which radar ring band `distance` falls in: 1 (innermost) to ring_count, or None
    at or beyond max_range. A distance exactly on a ring belongs to the outer band."""
    if distance < 0 or distance >= max_range:
        return None
    return int(distance * ring_count // max_range) + 1


class RangeBands(Instrument):
    """Lights the radar's distance bands that hold something moving. It says how far
    away movement is, not where."""

    def __init__(self, shared_references):
        super().__init__(shared_references)
        self.on = False
        self.hot = set()  # band numbers (1..RANGE_BAND_COUNT) with a mover in them

    # --- Instrument ---------------------------------------------------------
    def toggle(self):
        self.on = not self.on
        self.shared_references.sfx('keyboard_clack')
        self.hot = set()

    def update(self, dt, held_button):
        if not self.on:
            return
        hot = set()
        x, y = self.ship.center
        for contact in self.contacts.all(exclude=self.ship):
            if contact.kind not in WATCHED_KINDS or not contact.moving:
                continue
            cx, cy = contact.center
            band = band_index(((cx - x) ** 2 + (cy - y) ** 2) ** 0.5, RANGE_BAND_COUNT, RADAR_SCALE)
            if band is not None:
                hot.add(band)
        self.hot = hot

    def console_buttons(self):
        return [("RANGE BANDS", 'toggle_range_bands', dict(key="L", lit=self.on, states=("ON", "OFF"), sub="DISTANCE RINGS ON RADAR"))]

    def status_line(self):
        return f"RANGE BANDS [{'ON' if self.on else 'OFF'}]", self.on

    def draw_panel(self, ui):
        if self.on:
            ui.draw_range_bands(self.hot, RANGE_BAND_COUNT)
