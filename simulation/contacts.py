"""One way for sensors to ask "what is out there?".

The world keeps its objects in two shapes: flat lists (ships, missiles, decoys) and
grid-keyed dicts (asteroids, drones, pirates; the grid makes ray and range checks
cheap). Every sensor used to walk both shapes by hand and then guess at each
object's attributes. `Contacts` hides the shapes: it hands out the objects, and
every object answers the same questions (kind, center, vel_x, vel_y,
radar_cross_section, painted; see objects/base.py).

It holds the World, not copies of its lists, so it is never stale: whatever the
world holds right now is what you get.
"""
import math


class Contacts:
    def __init__(self, world):
        self.world = world

    def _lists(self):
        return self.world.ships, self.world.missiles, self.world.decoys

    def _grids(self):
        return self.world.asteroids, self.world.drones, self.world.pirates

    def all(self, exclude=None):
        """Every contact. `exclude` is usually your own ship."""
        for group in self._lists():
            for obj in group:
                if obj is not exclude:
                    yield obj
        for grid in self._grids():
            yield from grid

    def within(self, x, y, radius, exclude=None):
        """Contacts whose center is closer than `radius` to (x, y)."""
        for obj in self.all(exclude):
            ox, oy = obj.center
            if math.hypot(ox - x, oy - y) < radius:
                yield obj

    def near(self, x, y, cell_reach=0, exclude=None):
        """What could be at (x, y): all the listed contacts, plus whatever the grid
        holds in that cell and the `cell_reach` cells around it. For ray marching,
        where you test each candidate yourself."""
        for group in self._lists():
            for obj in group:
                if obj is not exclude:
                    yield obj
        for grid in self._grids():
            yield from grid.near(x, y, cell_reach)

    def find(self, net_id):
        for obj in self.all():
            if obj.net_id == net_id:
                return obj
        return None

    def clear_painted(self, exclude=None):
        for obj in self.all(exclude):
            obj.painted = False
