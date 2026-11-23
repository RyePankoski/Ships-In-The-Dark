from instruments.instrument import Instrument


class MiningLaser(Instrument):
    """Switch the mining beam on and it locks the nearest icy or metallic rock in
    range, burning it for a while. The world does the work and the reward (see
    simulation/world.py: _step_mining); this just holds the switch and draws the beam."""

    keys = (('e', 'toggle_mining'),)

    def __init__(self, ctx):
        super().__init__(ctx)
        self.on = False

    # --- Instrument ---------------------------------------------------------
    def actions(self):
        return {'toggle_mining': self.toggle}

    def toggle(self):
        self.on = not self.on
        self.ctx.sfx('laser_toggle')
        self.ctx.start_cooldown()

    def console_buttons(self):
        return [("MINING LASER", 'toggle_mining', dict(key="E", lit=self.on))]

    def status_line(self):
        if not self.on:
            return "MINING LASER [OFF]", False
        if self.ship.mining_target is None:
            return "MINING LASER [SEEKING]", True
        return f"MINING LASER [{self.ship.mining_progress * 100:.0f}%]", True

    def draw_overlay(self, ui, camera_x, camera_y):
        if not self.ship.mining_on or self.ship.mining_target is None:
            return
        rock = self.world.find(self.ship.mining_target)
        if rock is not None:
            ui.draw_mining_beam(self.ship, rock, self.ship.mining_progress, camera_x, camera_y)
