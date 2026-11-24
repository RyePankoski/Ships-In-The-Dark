import math

from instruments.instrument import Instrument
from config.constants import MINING_RANGE, MINING_YIELD


class MiningLaser(Instrument):
    """Switch the mining laser on near an asteroid and it burns the nearest one in range.
    No laser paint needed. The switch lives on the server: this sends 'mine' and 'mine_off' and shows whatever the ship says (see
    simulation/world.py: _start_mining, _step_mining). It also draws the beam."""

    keys = (('e', 'toggle_mining'),)

    @property
    def on(self):
        return self.ship.mining_on

    # --- Instrument ---------------------------------------------------------
    def actions(self):
        return {'toggle_mining': self.toggle}

    def toggle(self):
        if self.on:
            self.ctx.send_action({'type': 'mine_off'})
        else:
            rock = self._nearest_mineable_rock()
            if rock is None:
                self.ctx.sfx('cancel')
                return
            self.ctx.send_action({'type': 'mine', 'target': rock.net_id})
        self.ctx.start_cooldown()

    def console_buttons(self):
        return [("MINING LASER", 'toggle_mining', dict(key="E", lit=self.on, sub="CUT ASTEROIDS FOR ORE"))]

    def status_line(self):
        if not self.on:
            return "MINING LASER [OFF]", False
        if self.ship.mining_target is None:
            return "MINING LASER [STANDBY]", True
        return f"MINING LASER [{self.ship.mining_progress * 100:.0f}%]", True

    def draw_overlay(self, ui, camera_x, camera_y):
        if not self.ship.mining_on or self.ship.mining_target is None:
            return
        rock = self.world.find(self.ship.mining_target)
        if rock is not None:
            ui.draw_mining_beam(self.ship, rock, self.ship.mining_progress, camera_x, camera_y)

    # --- Designation --------------------------------------------------------
    def _nearest_mineable_rock(self):
        """The closest asteroid within mining range that pays out something, or None.
        The world checks again when the action arrives."""
        cx, cy = self.ship.center
        rocks = [rock for rock in self.contacts.within(cx, cy, MINING_RANGE, exclude=self.ship)
                 if rock.kind == 'asteroid' and rock.alive and rock.material in MINING_YIELD]
        return min(rocks, key=lambda rock: math.hypot(rock.pos_x - cx, rock.pos_y - cy), default=None)
