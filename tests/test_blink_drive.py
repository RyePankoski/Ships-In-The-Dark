from types import SimpleNamespace

from instruments.blink_drive import BlinkDrive
from instruments.instrument import InstrumentContext


class _Silent:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def _drive():
    ship = SimpleNamespace(fuel=500, drop_lock=False)
    sent = []
    ctx = InstrumentContext(ship, None, None, _Silent(), send_action=sent.append)
    return BlinkDrive(ctx), sent


def test_blink_waits_out_the_full_charge_before_jumping():
    drive, sent = _drive()
    drive.press()
    for _ in range(int(BlinkDrive.CHARGE_SECONDS / 0.05) - 2):
        drive.update(0.05, False)
    assert drive.charging and sent == []
    for _ in range(5):
        drive.update(0.05, False)
    assert sent == [{'type': 'blink'}]
    assert not drive.charging
