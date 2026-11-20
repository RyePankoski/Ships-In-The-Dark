"""The radar channel: hears other ships' radar sweeps.

A sweep is an omnidirectional ping. This channel reports the strongest sweep sent
in the last RADAR_PING_WINDOW seconds, or None if there was none. It does not apply
gain or the noise floor; the radio does that (radio/receiver.py).
"""
from radio.channel import Channel, Reading
from radio.signal import RADAR_SWEEP, attenuate, distance_between
from utility.constants import RADAR_PING_WINDOW


class RadarChannel(Channel):
    accepts = frozenset({RADAR_SWEEP})
    name = 'RADAR PING'

    def _read(self, x, y, emissions, now):
        best = None
        for emission in emissions:
            if now - emission.timestamp > RADAR_PING_WINDOW:
                continue
            strength = attenuate(emission.power, distance_between(emission, x, y))
            if best is None or strength > best.strength:
                best = Reading(strength, emission.timestamp)
        return best
