"""The signal model: what gets emitted, and how strongly it is received.

No drawing, no sound, no keyboard, no network. Everything here is plain data, so
the World can own an EmissionLog and the server can later send it to clients.

Sources publish an Emission and never know who is listening. Whoever listens (a
radio channel, see radio/channel.py) reads the log and calls `attenuate` to turn
power and distance into received strength.
"""
import math
from dataclasses import dataclass

from utility.constants import EMISSION_LIFETIME, SIGNAL_REFERENCE_DISTANCE

# Emission types. A channel declares which of these it accepts.
RADAR_SWEEP = 'radar_sweep'


@dataclass(frozen=True)
class Emission:
    source_id: int      # net_id / player_id of whoever emitted
    x: float
    y: float
    type: str           # RADAR_SWEEP, ...
    power: float
    timestamp: float    # world time, in seconds


def attenuate(power, distance):
    """Received strength of a one-way signal. The one place range is tuned.

    Full power inside SIGNAL_REFERENCE_DISTANCE, then inverse-square (strength
    falls to a quarter when the distance doubles).
    """
    d = max(distance, SIGNAL_REFERENCE_DISTANCE)
    return power * (SIGNAL_REFERENCE_DISTANCE / d) ** 2


def distance_between(emission, x, y):
    return math.hypot(emission.x - x, emission.y - y)


class EmissionLog:
    """Everything emitted lately. Sources publish; listeners read."""

    def __init__(self, lifetime=EMISSION_LIFETIME):
        self.lifetime = lifetime
        self._emissions = []

    def publish(self, source_id, x, y, type, power, timestamp):
        emission = Emission(source_id, x, y, type, power, timestamp)
        self._emissions.append(emission)
        return emission

    def recent(self, now, within=None, types=None):
        """Emissions up to `within` seconds old (default: the log's lifetime), newest last.
        `types`, if given, limits them to those emission types."""
        within = self.lifetime if within is None else within
        return [e for e in self._emissions
                if now - e.timestamp <= within and (types is None or e.type in types)]

    def prune(self, now):
        """Forget emissions older than the lifetime."""
        self._emissions = [e for e in self._emissions if now - e.timestamp <= self.lifetime]
