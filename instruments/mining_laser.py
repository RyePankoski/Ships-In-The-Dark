import math

from instruments.instrument import Instrument
from config.constants import MINING_RANGE, MINING_YIELD


class MiningLaser(Instrument):
    """Designate a rock with the assessor beam, then switch the mining laser on and it
    burns that rock. Switching it on takes the assessor beam off. The switch lives on the
    server: this sends 'mine' and 'mine_off' and shows whatever the ship says (see
    simulation/world.py: _start_mining, _step_mining). It also draws the beam."""

    keys = (('e', 'toggle_mining'),)

    def __init__(self, ctx, laser):
        super().__init__(ctx)
        self.laser = laser  # the LaserAssessor whose beam designates the rock

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
            rock = self._designatable_rock()
            if rock is None:
                self.ctx.sfx('cancel')
                return
            self.laser.on = False
            self.laser.laser_locked = False
            self.ctx.send_action({'type': 'mine', 'target': rock.net_id})
        self.ctx.start_cooldown()

    def console_buttons(self):
        return [("MINING LASER", 'toggle_mining', dict(key="E", lit=self.on))]

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
    def _designatable_rock(self):
        """The asteroid the assessor beam is on now, if it can be mined from here.
        The world checks again when the action arrives."""
        if not self.laser.on or self.laser.target_type == "NOTHING":
            return None
        rock = self.laser.current_target
        if getattr(rock, 'kind', None) != 'asteroid' or rock.material not in MINING_YIELD:
            return None
        cx, cy = self.ship.center
        if math.hypot(rock.pos_x - cx, rock.pos_y - cy) > MINING_RANGE:
            return None
        return rock
