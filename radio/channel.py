"""The channel interface: one kind of signal a radio can be tuned to.

To add a channel (engines, comms, ...) subclass Channel, say which emission types
it accepts, and write `_read`. The radio itself never changes.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Reading:
    """What a channel hears this frame. More fields (bearing, source id) can be
    added later without touching existing channels. `timestamp` is when the heard
    emission was sent, so the radio can tell a new ping from one it already played."""
    strength: float
    timestamp: float = None


class Channel:
    accepts = frozenset()  # emission types this channel hears
    name = ''              # what the dial shows

    def read(self, listener_id, x, y, emissions, now):
        """The listener's reading this frame, or None if there is nothing to hear.

        `emissions` is whatever the log holds (EmissionLog.recent); this filters
        to what the channel accepts and drops the listener's own transmissions.
        """
        heard = [e for e in emissions if e.type in self.accepts and e.source_id != listener_id]
        return self._read(x, y, heard, now)

    def _read(self, x, y, emissions, now):
        raise NotImplementedError
