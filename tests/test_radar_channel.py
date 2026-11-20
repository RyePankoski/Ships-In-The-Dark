import unittest

from radio.radar_channel import RadarChannel
from radio.receiver import receive
from radio.signal import EmissionLog
from tests.fakes import FakeSweepEmitter
from utility.constants import RADAR_PING_WINDOW

LISTENER = 9


class RadarChannelTests(unittest.TestCase):
    def setUp(self):
        self.log = EmissionLog()
        self.emitter = FakeSweepEmitter(self.log, 0, 0, interval=3.0)
        self.channel = RadarChannel()

    def hear(self, now, distance, gain=1.0):
        self.emitter.update(now)
        reading = self.channel.read(LISTENER, distance, 0, self.log.recent(now), now)
        return None if reading is None else (receive(reading.strength, gain), reading.timestamp)

    def test_heard_when_sweep_fires_then_goes_quiet(self):
        self.assertIsNotNone(self.hear(0.0, 1000)[0])
        self.assertIsNone(self.hear(RADAR_PING_WINDOW + 0.1, 1000))

    def test_repeats_every_interval_with_new_timestamp(self):
        first = self.hear(0.0, 1000)
        second = self.hear(3.0, 1000)
        self.assertEqual((first[1], second[1]), (0.0, 3.0))

    def test_weaker_with_distance(self):
        self.assertGreater(self.hear(0.0, 1000)[0], self.hear(0.0, 3000)[0])

    def test_far_sweep_needs_gain(self):
        self.assertIsNone(self.hear(0.0, 8000, gain=1.0)[0])
        self.assertIsNotNone(self.hear(0.0, 8000, gain=4.0)[0])

    def test_own_sweep_not_heard(self):
        self.emitter.update(0.0)
        self.assertIsNone(self.channel.read(self.emitter.source_id, 0, 0, self.log.recent(0.0), 0.0))


if __name__ == '__main__':
    unittest.main()
