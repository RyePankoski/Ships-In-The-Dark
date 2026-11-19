import math
import random

from utility.constants import *


def make_outline(x, y, size):
    # The shape is seeded from the rock's position (not the world rng), so every
    # client draws the same rock without it being sent, and world generation
    # order is untouched. Radii stay close to `size` so the circular collision
    # still matches what the player sees.
    rng = random.Random(x * 73856093 ^ y * 19349663)
    count = rng.randint(9, 13)
    step = 2 * math.pi / count
    outline = []
    for i in range(count):
        angle = i * step + rng.uniform(-0.3, 0.3) * step
        radius = size * rng.uniform(0.78, 1.05)
        outline.append((math.cos(angle) * radius, math.sin(angle) * radius))
    return outline


from objects.base import WorldObject


class Asteroid(WorldObject):
    kind = 'asteroid'

    def __init__(self, x, y, size):
        self.pos_x = x
        self.pos_y = y
        self.size = size
        self.outline = make_outline(x, y, size)
        self.painted = False
        self.radar_cross_section = self.size
        self.id_for_ui = None

        self.alive = True

        grid_x = int(x // GRID_SIZE)
        grid_y = int(y // GRID_SIZE)
        self.cell = (grid_x, grid_y)