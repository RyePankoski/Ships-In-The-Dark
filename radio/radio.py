"""The radio: a dial, a gain knob and a power switch in front of the channels.

State only, no drawing or sound. Each frame `update` asks the tuned channel what it
hears, runs that through gain / noise floor / saturation, and returns what the
output layer should play. Unused dial positions are static, so the dial is full from
day one. Adding a real channel means putting its class on the dial; nothing else changes.
"""
from dataclasses import dataclass

from radio.channel import Channel, Reading
from radio.radar_channel import RadarChannel
from radio.receiver import receive
from utility.constants import (
    RADIO_DIAL_SIZE, RADIO_GAIN_DEFAULT, RADIO_GAIN_MAX, RADIO_GAIN_MIN,
    RADIO_GAIN_STEP, RADIO_STATIC_LEVEL,
)


class StaticChannel(Channel):
    """An unused dial position: a steady hiss."""
    is_static = True
    name = 'NO SIGNAL'

    def _read(self, x, y, emissions, now):
        return Reading(RADIO_STATIC_LEVEL)


@dataclass(frozen=True)
class Heard:
    """What the output layer gets this frame.
    strength: 0..saturation, after gain.
    static:   True for hiss (continuous); False for a real signal.
    new:      True on the first frame a given ping is heard (play the blip once)."""
    strength: float
    static: bool
    new: bool


def default_dial():
    return [RadarChannel()] + [StaticChannel() for _ in range(RADIO_DIAL_SIZE - 1)]


class Radio:
    def __init__(self, dial=None):
        self.dial = dial or default_dial()
        self.index = 0
        self.gain = RADIO_GAIN_DEFAULT
        self.on = True
        self._last_ping = None  # timestamp of the last ping we reported as new

    @property
    def channel(self):
        return self.dial[self.index]

    def toggle(self):
        self.on = not self.on

    def tune(self, steps):
        """Turn the dial by `steps` (negative = down), wrapping around."""
        self.index = (self.index + steps) % len(self.dial)

    def adjust_gain(self, clicks):
        """Turn the gain knob by `clicks` (negative = down), clamped to its range."""
        self.gain = min(RADIO_GAIN_MAX, max(RADIO_GAIN_MIN, self.gain * RADIO_GAIN_STEP ** clicks))

    def update(self, listener_id, x, y, log, now):
        """What the listener hears this frame, or None (radio off, or silence)."""
        if not self.on:
            return None
        channel = self.channel
        reading = channel.read(listener_id, x, y, log.recent(now), now)
        if reading is None:
            return None
        strength = receive(reading.strength, self.gain)
        if strength is None:
            return None

        static = getattr(channel, 'is_static', False)
        new = False
        if not static and reading.timestamp != self._last_ping:
            self._last_ping = reading.timestamp
            new = True
        return Heard(strength, static, new)
