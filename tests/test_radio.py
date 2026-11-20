import unittest

from radio.radio import Radio
from radio.signal import EmissionLog
from tests.fakes import FakeSweepEmitter
from utility.constants import (
    RADIO_DIAL_SIZE, RADIO_GAIN_DEFAULT, RADIO_GAIN_MAX, RADIO_GAIN_MIN,
)

ME = 9


class RadioTests(unittest.TestCase):
    def setUp(self):
        self.log = EmissionLog()
        self.emitter = FakeSweepEmitter(self.log, 0, 0, interval=3.0)
        self.radio = Radio()

    def listen(self, now, distance=1000):
        self.emitter.update(now)
        return self.radio.update(ME, distance, 0, self.log, now)

    def test_ping_is_new_once(self):
        first = self.listen(0.0)
        again = self.listen(0.1)
        self.assertTrue(first.new)
        self.assertFalse(again.new)
        self.assertTrue(self.listen(3.0).new)

    def test_silence_between_pings(self):
        self.listen(0.0)
        self.assertIsNone(self.listen(1.5))

    def test_off_hears_nothing(self):
        self.radio.toggle()
        self.assertIsNone(self.listen(0.0))
        self.radio.toggle()
        self.assertIsNotNone(self.listen(0.0))

    def test_unused_positions_are_static(self):
        self.radio.tune(1)
        heard = self.listen(0.0)
        self.assertTrue(heard.static)
        self.assertFalse(heard.new)

    def test_static_hiss_is_continuous(self):
        self.radio.tune(1)
        self.assertIsNotNone(self.listen(1.0))
        self.assertIsNotNone(self.listen(2.0))

    def test_dial_wraps(self):
        self.radio.tune(-1)
        self.assertEqual(self.radio.index, RADIO_DIAL_SIZE - 1)
        self.radio.tune(1)
        self.assertEqual(self.radio.index, 0)

    def test_gain_clamps(self):
        self.radio.adjust_gain(100)
        self.assertEqual(self.radio.gain, RADIO_GAIN_MAX)
        self.radio.adjust_gain(-100)
        self.assertEqual(self.radio.gain, RADIO_GAIN_MIN)

    def test_gain_reaches_far_sweeps(self):
        self.assertIsNone(self.listen(0.0, distance=8000))
        self.radio.adjust_gain(7)  # ~4.8x
        self.assertIsNotNone(self.listen(0.0, distance=8000))

    def test_default_gain(self):
        self.assertEqual(self.radio.gain, RADIO_GAIN_DEFAULT)


if __name__ == '__main__':
    unittest.main()
