from instruments.instrument import Instrument
from radio.radio import Radio
from utility.constants import RADIO_SATURATION

PING_VOLUME_MIN = 0.1     # even the faintest heard ping is audible
STATIC_VOLUME_SCALE = 3.0 # static is raw strength * gain, which is small; this makes it a quiet hiss
LEVEL_DECAY = 0.8         # the signal needle falls by this much per second after a ping


class RadioReceiver(Instrument):
    """The radio in the console: a dial, a gain knob and a speaker. All it does with a
    detection is make a sound and move a needle. The signal model is in radio/."""

    keys = (
        ('g', 'toggle_radio'),
        ('1', 'radio_tune_down'),
        ('2', 'radio_tune_up'),
        ('3', 'radio_gain_down'),
        ('4', 'radio_gain_up'),
    )

    def __init__(self, ctx, my_id):
        super().__init__(ctx)
        self.my_id = my_id
        self.radio = Radio()
        self.level = 0.0       # what the signal needle shows
        self.saturated = False
        self.static = False
        self._hissing = False

    # --- Instrument ---------------------------------------------------------
    def actions(self):
        return {
            'toggle_radio': self.toggle,
            'radio_tune_down': lambda: self.tune(-1),
            'radio_tune_up': lambda: self.tune(1),
            'radio_gain_down': lambda: self.gain(-1),
            'radio_gain_up': lambda: self.gain(1),
        }

    def toggle(self):
        self.radio.toggle()
        self.ctx.sfx('radio_click', force=True)
        self.ctx.start_cooldown()

    def tune(self, steps):
        if self.radio.on:
            self.radio.tune(steps)
            self.ctx.sfx('radio_click', force=True)
            self.ctx.start_cooldown()

    def gain(self, clicks):
        if self.radio.on:
            self.radio.adjust_gain(clicks)
            self.ctx.sfx('radio_click', force=True)
            self.ctx.start_cooldown()

    def status_line(self):
        return f"RADIO       [{'ON' if self.radio.on else 'OFF'}]", self.radio.on

    def update(self, dt, inputs):
        x, y = self.ship.center
        heard = self.radio.update(self.my_id, x, y, self.world.emissions, self.world.time)

        self.level = max(0.0, self.level - LEVEL_DECAY * dt)
        self.static = heard is not None and heard.static
        self.saturated = heard is not None and heard.strength >= RADIO_SATURATION

        hiss = self.static
        if heard is not None and heard.static:
            self.level = heard.strength ** 0.5
            volume = min(1.0, heard.strength * STATIC_VOLUME_SCALE)
            if not self._hissing:
                self.ctx.sfx('radio_static', loops=-1, volume=volume)
            else:
                self.ctx.audio.set_sfx_volume('radio_static', volume)
        elif heard is not None and heard.new:
            self.level = heard.strength ** 0.5  # needle and volume use a perceptual (square-root) scale
            self.ctx.sfx('radio_ping', force=True, volume=max(PING_VOLUME_MIN, heard.strength ** 0.2))
        if not hiss and self._hissing:
            self.ctx.stop_sfx('radio_static')
        self._hissing = hiss

    def draw_panel(self, ui):
        ui.draw_radio_panel(self.radio, self.level, self.saturated)

    def draw_controls(self, ui):
        ui.draw_radio_controls(self.radio)
