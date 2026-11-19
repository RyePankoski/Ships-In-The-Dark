"""The shape every sensor and ship system fits into.

To add one:
  1. Subclass Instrument, say what it answers to (`keys`, `actions()`), what it does
     each frame (`update`), and what it draws (`draw_panel`, `draw_overlay`,
     `draw_controls`). Everything is optional.
  2. Add it to the list in MainScene.__init__.
That's all: keys, clicks, per-frame updates, drawing, the console button and the
telemetry line are all picked up from the list.

An instrument asks the world what is out there through `self.contacts` (see
simulation/contacts.py), and keeps its own switch and readouts. The cockpit only
keeps what several things share (the locked target, threat warnings).
"""


class InstrumentContext:
    """What an instrument is allowed to touch. MainScene builds one and hands it out."""

    def __init__(self, ship, contacts, cockpit, audio, make_noise, start_cooldown):
        self.ship = ship
        self.contacts = contacts
        self.cockpit = cockpit
        self.audio = audio
        self._make_noise = make_noise
        self._start_cooldown = start_cooldown
        # True on frames when held keys may repeat an action (not mid-cooldown)
        self.keys_live = True

    def sfx(self, name, **kwargs):
        self.audio.play_sfx(name, **kwargs)

    def stop_sfx(self, name):
        self.audio.stop_sfx(name)

    def noise(self, strength):
        """Something just made a racket: it shows on the P-field."""
        self._make_noise(strength)

    def start_cooldown(self):
        """Hold the pilot's keys off for a moment so one press is one action."""
        self._start_cooldown()


class Instrument:
    # (key, action) pairs: which keys trigger which of this instrument's actions
    keys = ()

    def __init__(self, ctx):
        self.ctx = ctx
        self.ship = ctx.ship
        self.contacts = ctx.contacts

    def actions(self):
        """{action name: handler}. A key or a button producing that name calls the handler."""
        return {}

    def update(self, dt, inputs):
        """Once per frame, after the world has stepped."""

    def console_buttons(self):
        """Buttons for the console's SENSORS // DISPLAYS bank: (label, action, style) each.
        Leave empty if the instrument draws its own buttons on its own panel."""
        return []

    def status_line(self):
        """(text, is_on) for the SUBSYSTEMS column of the ship telemetry, or None."""
        return None

    # Drawing comes in three passes so the stacking stays right: panels first, then
    # overlays on the viewport (and over the radar), then buttons that must sit on top.
    def draw_panel(self, ui):
        pass

    def draw_overlay(self, ui, camera_x, camera_y):
        pass

    def draw_controls(self, ui):
        pass
