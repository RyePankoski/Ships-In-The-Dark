from radio.signal import RADAR_SWEEP
from utility.constants import RADAR_SWEEP_POWER


class FakeSweepEmitter:
    """A stand-in for a player's radar: pings from a fixed spot every `interval` seconds."""

    def __init__(self, log, x, y, interval=3.0, source_id=1):
        self.log, self.x, self.y = log, x, y
        self.interval = interval
        self.source_id = source_id
        self.next_ping = 0.0

    def update(self, now):
        while now >= self.next_ping:
            self.log.publish(self.source_id, self.x, self.y, RADAR_SWEEP,
                             RADAR_SWEEP_POWER, self.next_ping)
            self.next_ping += self.interval
