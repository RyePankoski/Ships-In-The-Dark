import unittest

from radio.receiver import hearing_range, is_saturated, receive
from radio.signal import attenuate
from utility.constants import RADAR_SWEEP_POWER as P, RADIO_NOISE_FLOOR, RADIO_SATURATION


class ReceiveTests(unittest.TestCase):
    def test_below_noise_floor_is_lost(self):
        self.assertIsNone(receive(RADIO_NOISE_FLOOR / 2, gain=1))

    def test_gain_lifts_weak_signal_over_floor(self):
        weak = RADIO_NOISE_FLOOR / 2
        self.assertIsNone(receive(weak, 1))
        self.assertIsNotNone(receive(weak, 4))

    def test_saturation_clips(self):
        self.assertEqual(receive(1.0, gain=8), RADIO_SATURATION)
        self.assertTrue(is_saturated(1.0, 8))
        self.assertFalse(is_saturated(0.1, 1))

    def test_more_gain_hears_farther(self):
        self.assertGreater(hearing_range(P, 4), hearing_range(P, 1))

    def test_hearing_range_matches_attenuate(self):
        r = hearing_range(P, 2)
        self.assertAlmostEqual(receive(attenuate(P, r * 0.99), 2) is not None, True)
        self.assertIsNone(receive(attenuate(P, r * 1.01), 2))


if __name__ == '__main__':
    unittest.main()
