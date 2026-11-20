"""The listener's side of the signal model: gain, noise floor and saturation.

Pure functions, no state. Turning gain up reaches farther (a weak signal climbs
over the noise floor) but near, strong signals clip at the saturation ceiling.
"""
from utility.constants import RADIO_NOISE_FLOOR, RADIO_SATURATION, SIGNAL_REFERENCE_DISTANCE


def receive(strength, gain):
    """What the listener actually gets from a raw `strength`: None if it is lost in
    the noise, else the amplified strength clipped to the saturation ceiling."""
    amplified = strength * gain
    if amplified < RADIO_NOISE_FLOOR:
        return None
    return min(amplified, RADIO_SATURATION)


def is_saturated(strength, gain):
    return strength * gain >= RADIO_SATURATION


def hearing_range(power, gain):
    """Distance at which a source of `power` falls to the noise floor, for tuning
    and for checking the range tradeoff. Inverse of radio.signal.attenuate."""
    return SIGNAL_REFERENCE_DISTANCE * (power * gain / RADIO_NOISE_FLOOR) ** 0.5
