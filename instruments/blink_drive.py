from config.constants import BLINK_FUEL_THRESHOLD
from instruments.instrument import Instrument
from utility.timer import Timer


class BlinkDrive(Instrument):
    """Short-range jump: charge for a few seconds, then the world moves the ship.

    The charge meter and the exit flash are drawn by draw_effects, which the scene
    calls with the world (under the cockpit panels). The BLINK button sits in the
    HELM bank of the control banks and reads `busy`.
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        self.charge = Timer(5.5)  # charge time (was 3): 2.5 seconds longer
        self.arrival = Timer(2)

    @property
    def charging(self):
        return self.charge.running

    def interrupt(self):
        if self.charging:
            self.ctx.sfx('blink_denied')
            self.ctx.stop_sfx('blink')
            self.charge.stop()

    @property
    def arriving(self):
        return self.arrival.running

    @property
    def busy(self):
        return self.charging or self.arriving

    def actions(self):
        return {'blink': self.press}

    def press(self):
        if not self.charging and self.ship.fuel > BLINK_FUEL_THRESHOLD:
            self.charge.start()
            self.ship.drop_lock = True  # a blink breaks any lock on us
            self.ctx.sfx('blink')

        if self.ship.fuel <= BLINK_FUEL_THRESHOLD:
            self.ctx.sfx('blink_denied')

    def update(self, dt, held_button):
        if self.charge.update(dt):
            self.arrival.start()
            # The world does the actual jump (on the server, in multiplayer)
            self.ctx.send_action({'type': 'blink'})
        self.arrival.update(dt)

        if self.arriving:
            self.ctx.sfx('blink_arrival')
        else:
            self.ctx.stop_sfx('blink_arrival')

    def draw_effects(self, draw_game, camera_x, camera_y):
        if self.charging:
            draw_game.draw_charge_animation(True, self.charge.elapsed, self.charge.duration)
        if self.arriving:
            draw_game.draw_blink_arrival(self.ship.rect.center, self.arrival.elapsed,
                                         camera_x, camera_y, self.arrival.duration)
