from config.constants import BLINK_FUEL_THRESHOLD
from instruments.instrument import Instrument
from utility.timer import Timer


class BlinkDrive(Instrument):
    """Short-range jump: charge for a few seconds, then the world moves the ship.

    The charge meter and the exit flash are drawn by draw_effects, which the scene
    calls with the world (under the cockpit panels). The BLINK button sits in the
    HELM bank of the control banks and reads `busy`.
    """

    CHARGE_SECONDS = 5.5  # was 3: 2.5 seconds longer
    ARRIVAL_SECONDS = 2

    def __init__(self, shared_references):
        super().__init__(shared_references)
        self.charge = Timer()
        self.arrival = Timer()

    @property
    def charging(self):
        return self.charge.running

    def interrupt(self):
        if self.charging:
            self.shared_references.sfx('blink_denied')
            self.shared_references.stop_sfx('blink')
            self.charge.stop()

    @property
    def arriving(self):
        return self.arrival.running

    @property
    def busy(self):
        return self.charging or self.arriving

    def press(self):
        if not self.charging and self.ship.fuel > BLINK_FUEL_THRESHOLD:
            self.charge.start(self.CHARGE_SECONDS)  # start() with no duration would reset it to 0
            self.ship.drop_lock = True  # a blink breaks any lock on us
            self.shared_references.sfx('blink')

        if self.ship.fuel <= BLINK_FUEL_THRESHOLD:
            self.shared_references.sfx('blink_denied')

    def update(self, dt, held_button):
        if self.charge.update(dt):
            self.arrival.start(self.ARRIVAL_SECONDS)
            # The world does the actual jump (on the server, in multiplayer)
            self.shared_references.outbox.append({'type': 'blink'})
        self.arrival.update(dt)

        if self.arriving:
            self.shared_references.sfx('blink_arrival')
        else:
            self.shared_references.stop_sfx('blink_arrival')

    def draw_effects(self, draw_game, camera_x, camera_y):
        if self.charging:
            draw_game.draw_charge_animation(True, self.charge.elapsed, self.charge.duration)
        if self.arriving:
            draw_game.draw_blink_arrival(self.ship.rect.center, self.arrival.elapsed,
                                         camera_x, camera_y, self.arrival.duration)
