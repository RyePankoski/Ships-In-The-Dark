import math
import random

from utility import theme

# Per hit type: (phosphor colour, debris speed in px/s).
# Everything is drawn as plain vector lines in one colour, like a military display.
DEFAULT_STYLE = (theme.GREEN, 140)
STYLES = {
    'Ship': (theme.AMBER, 180),
    'Asteroid': (theme.GREY, 70),
    'Drone': (theme.GREEN, 130),
}
PLAYER_COLOUR = theme.RED_BRIGHT  # a human pilot going down reads as a red alert

PHOSPHOR_STEPS = 5  # brightness drops in steps, like a tube losing its charge


def phosphor_color(color, fade):
    """Brightness in discrete steps down to black, instead of a smooth fade."""
    if fade <= 0:
        return (0, 0, 0)
    step = math.ceil(fade * PHOSPHOR_STEPS) / PHOSPHOR_STEPS
    return tuple(int(channel * step) for channel in color)


FLASH_COLOR = theme.WHITE
FLASH_DURATION = 0.04  # seconds; about two frames, so the flash reads as a hit
BASE_RADIUS = 100  # the flash, and the outer ring at full size
BIG_RADIUS = 420
BASE_LIFETIME = 0.9  # seconds the rings take to expand and fade
BIG_LIFETIME = 1.8
RING_STAGGER = 0.08  # seconds between the rings of a player kill
BASE_DEBRIS_LIFETIME = 6.0  # seconds the debris takes to fade; outlasts the rings
BIG_DEBRIS_LIFETIME = 9.0
DRAG = 1.0  # debris slows down as it drifts; higher = stops sooner
TAIL = 0.12  # seconds of trail behind each debris line


class Explosion:
    """One burst: a flash, expanding vector rings, and debris lines that drift away and fade.

    big is for killing a human pilot. Drawing reads the state here; nothing is drawn in this class.
    """

    def __init__(self, x, y, kind=None, big=False, rng=random):
        self.x = x
        self.y = y
        self.kind = kind
        self.big = big
        self.age = 0.0
        self.lifetime = BIG_LIFETIME if big else BASE_LIFETIME
        self.debris_lifetime = BIG_DEBRIS_LIFETIME if big else BASE_DEBRIS_LIFETIME
        self.max_radius = BIG_RADIUS if big else BASE_RADIUS
        self.ring_count = 3 if big else 1

        style_colour, speed = STYLES.get(kind, DEFAULT_STYLE)
        self.colour = PLAYER_COLOUR if big else style_colour

        count = 40 if big else 14
        self.debris = []
        for _ in range(count):
            angle = rng.uniform(0, 2 * math.pi)
            push = speed * rng.uniform(0.4, 1.0) * (1.6 if big else 1.0)
            self.debris.append({'vx': math.cos(angle) * push, 'vy': math.sin(angle) * push})

    def update(self, dt):
        self.age += dt

    @property
    def finished(self):
        return self.age >= self.debris_lifetime

    @property
    def fade(self):
        """Ring brightness: 1.0 when the burst starts, 0.0 when the rings are gone."""
        return max(0.0, 1.0 - self.age / self.lifetime)

    @property
    def debris_fade(self):
        """Debris brightness: 1.0 when launched, 0.0 when it is gone."""
        return max(0.0, 1.0 - self.age / self.debris_lifetime)

    def flash_radius(self):
        """A solid flash for a couple of frames, then gone."""
        return self.max_radius if self.age < FLASH_DURATION else 0

    def ring_radii(self):
        """Radius of each expanding ring. They start together and spread out in time."""
        radii = []
        for i in range(self.ring_count):
            ring_age = self.age - i * RING_STAGGER
            if ring_age < 0:
                continue
            t = min(1.0, ring_age / self.lifetime)
            radii.append(self.max_radius * (1 - (1 - t) ** 2))  # quick start, slowing down
        return radii

    def debris_points(self):
        """(x, y, tail_x, tail_y, fade) per debris line, in world coordinates.

        Each piece moves at its launch speed and slows under drag, so it drifts away and stops.
        The line trails back along its path.
        """
        drift = (1 - math.exp(-DRAG * self.age)) / DRAG
        points = []
        for piece in self.debris:
            x = self.x + piece['vx'] * drift
            y = self.y + piece['vy'] * drift
            tail_x = x - piece['vx'] * TAIL
            tail_y = y - piece['vy'] * TAIL
            points.append((x, y, tail_x, tail_y, self.debris_fade))
        return points
