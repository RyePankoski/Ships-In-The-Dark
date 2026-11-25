from instruments.instrument import Instrument
from config.constants import CLOSE_RANGE_SCAN_RANGE


class CloseRangeScan(Instrument):
    """Always-on short-range sensor. Remembers what it has seen and lets the
    confidence in it fade once it is out of range."""

    def __init__(self, ctx):
        super().__init__(ctx)
        self.on = True
        self.scan_range = CLOSE_RANGE_SCAN_RANGE
        self.confirmed_contacts = []  # [x, y, kind, (vel_x, vel_y), confidence, age, object]
        self.in_range_now = []  # objects the latest scan detected, for the radar's moving dots

        self.confidence_decay = 0.999  # Per frame multiplier
        self.confirmation_time = 60  # Frames to reach full confidence (1.0)

    # --- Instrument ---------------------------------------------------------
    def actions(self):
        return {'toggle_prox_scan': self.toggle}

    def toggle(self):
        self.on = not self.on
        self.ctx.sfx('close_range_toggle')

    def update(self, dt, held_button):
        if self.on:
            self.scan()

    def console_buttons(self):
        return [("PROX SCAN", 'toggle_prox_scan', dict(key="Q", lit=self.on, sub="LOW-POWER NEARBY SCAN"))]

    # --- The scan -----------------------------------------------------------
    def scan(self):
        """Updates contacts and decays confidence over time."""
        x, y = self.ship.center
        detections = {obj: obj for obj in self.contacts.within(x, y, self.scan_range, exclude=self.ship)}
        self.in_range_now = list(detections)

        known = {c[6] for c in self.confirmed_contacts}
        for obj in detections:
            if obj not in known:
                cx, cy = obj.center
                self.confirmed_contacts.append([cx, cy, obj.kind.upper(), (obj.vel_x, obj.vel_y), 1.0, 0, obj])

        kept = []
        for contact in self.confirmed_contacts:
            obj, confidence = contact[6], contact[4]

            if obj in detections:
                # In range: update position and boost confidence
                contact[0], contact[1] = obj.center
                contact[3] = (obj.vel_x, obj.vel_y)
                contact[5] += 1
                if confidence < 1.0:
                    contact[4] = min(1.0, confidence + (1.0 / self.confirmation_time))
            else:
                # Out of range: decay confidence
                contact[4] *= self.confidence_decay
                contact[5] += 1

            if contact[4] > 0.05:
                kept.append(contact)

        self.confirmed_contacts = kept

    def get_contacts(self):
        """Confirmed contacts formatted for display: (x, y, kind, (vel_x, vel_y), confidence)."""
        return [(c[0], c[1], c[2], c[3], c[4]) for c in self.confirmed_contacts]

    def moving_now(self):
        """(x, y) of each thing the scan is detecting this frame that is moving. Empty while the scan is off."""
        if not self.on:
            return []
        return [obj.center for obj in self.in_range_now if obj.moving]
