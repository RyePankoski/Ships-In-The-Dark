import unittest

from radio.channel import Channel, Reading
from radio.signal import RADAR_SWEEP, EmissionLog, attenuate, distance_between
from utility.constants import SIGNAL_REFERENCE_DISTANCE as D0


class AttenuateTests(unittest.TestCase):
    def test_full_power_inside_reference_distance(self):
        self.assertEqual(attenuate(1.0, 0), 1.0)
        self.assertEqual(attenuate(1.0, D0), 1.0)

    def test_inverse_square(self):
        self.assertAlmostEqual(attenuate(1.0, 2 * D0), 0.25)
        self.assertAlmostEqual(attenuate(1.0, 4 * D0), 1 / 16)

    def test_scales_with_power(self):
        self.assertAlmostEqual(attenuate(4.0, 2 * D0), 1.0)


class EmissionLogTests(unittest.TestCase):
    def test_publish_and_recent(self):
        log = EmissionLog(lifetime=5)
        log.publish(1, 0, 0, RADAR_SWEEP, 1.0, timestamp=10)
        log.publish(2, 0, 0, 'other', 1.0, timestamp=12)
        self.assertEqual(len(log.recent(now=13)), 2)
        self.assertEqual([e.source_id for e in log.recent(13, types={RADAR_SWEEP})], [1])
        self.assertEqual([e.source_id for e in log.recent(13, within=2)], [2])

    def test_prune_forgets_old(self):
        log = EmissionLog(lifetime=5)
        log.publish(1, 0, 0, RADAR_SWEEP, 1.0, timestamp=0)
        log.prune(now=10)
        self.assertEqual(log.recent(now=10), [])


class FakeRadarChannel(Channel):
    accepts = frozenset({RADAR_SWEEP})

    def _read(self, x, y, emissions, now):
        if not emissions:
            return None
        return Reading(max(attenuate(e.power, distance_between(e, x, y)) for e in emissions))


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.log = EmissionLog()
        self.channel = FakeRadarChannel()

    def read(self, listener_id=9, x=0, y=0):
        return self.channel.read(listener_id, x, y, self.log.recent(now=1), now=1)

    def test_nothing_to_hear(self):
        self.assertIsNone(self.read())

    def test_hears_sweep_weaker_with_distance(self):
        self.log.publish(1, 2 * D0, 0, RADAR_SWEEP, 1.0, timestamp=0)
        near = self.read(x=D0).strength
        far = self.read(x=-2 * D0).strength
        self.assertGreater(near, far)

    def test_ignores_unaccepted_types_and_own_emissions(self):
        self.log.publish(1, 0, 0, 'engine', 1.0, timestamp=0)
        self.log.publish(9, 0, 0, RADAR_SWEEP, 1.0, timestamp=0)
        self.assertIsNone(self.read(listener_id=9))


if __name__ == '__main__':
    unittest.main()
