"""The shape every sensor and ship system fits into.

To add one:
  1. Subclass Instrument, say what it does each frame (`update`) and what it draws
     (`draw_panel`, `draw_overlay`, `draw_controls`). Everything is optional.
  2. Add it to the list in MainScene.__init__.
  3. Wire its input: keys in MainScene.handle_inputs, buttons in MainScene.perform.
Per-frame updates, drawing, the console button and the telemetry line are picked
up from the list.

An instrument asks the world what is out there through `self.contacts` (see
simulation/contacts.py), and keeps its own switch and readouts.
"""


class SharedInstrumentReferences:
    """What an instrument is allowed to touch. MainScene builds one and hands it out."""

    def __init__(self, ship, contacts, audio, world=None, outbox=None):
        self.ship = ship
        # Requests to the world, e.g. {'type': 'blink'}. In multiplayer the server does them.
        self.outbox = outbox
        self.world = world
        self.contacts = contacts
        self.audio = audio

    def sfx(self, name, **kwargs):  # kwargs: force, loops, volume
        self.audio.play_sfx(name, **kwargs)

    def stop_sfx(self, name):
        self.audio.stop_sfx(name)


class Instrument:
    def __init__(self, shared_references):
        self.shared_references = shared_references
        self.ship = shared_references.ship
        self.contacts = shared_references.contacts
        self.world = shared_references.world

    def update(self, dt, held_button):
        """Once per frame, before the world is stepped. `held_button` is the action of the
        on-screen hold button under the mouse, or None."""

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
