import math
import os
import random
from collections import Counter

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from simulation.world import World

pygame.display.init()

TRIPS = 100
MAX_FRAMES = 12000  # enough for a full-world trip at top speed (about 3 minutes of game time)
STUCK_SPEED = 1.0


def _run_trip(seed):
    rng = random.Random(seed)
    world = World(seed=seed, with_npcs=False)
    world.spawn_ship(2, is_ai=True)
    ai = world.ai_list[0]
    ship = ai.ship
    target = (rng.randint(200, world.width - 200), rng.randint(200, world.height - 200))
    ai.ultimate_destination = target
    ai.current_destination = target

    closest = float("inf")
    for _ in range(MAX_FRAMES):
        world.step({}, 0.016)
        if not ship.alive:
            return "destroyed", closest
        closest = min(closest, math.dist((ship.pos_x, ship.pos_y), target))
        if ai.ultimate_destination is None:
            return "arrived", closest

    if ship.speed < STUCK_SPEED:
        return "stuck", closest
    return "timeout", closest


def test_ai_navigation_outcomes():
    outcomes = Counter()
    closest_gaps = []
    for seed in range(TRIPS):
        outcome, closest = _run_trip(seed)
        outcomes[outcome] += 1
        if outcome != "arrived":
            closest_gaps.append(closest)

    print("\nAI trips:", TRIPS)
    for name in ("arrived", "destroyed", "stuck", "timeout"):
        print(f"  {name:10s} {outcomes[name]:3d}")
    if closest_gaps:
        closest_gaps.sort()
        print(f"  closest approach of the unarrived trips: median {closest_gaps[len(closest_gaps) // 2]:.0f}, "
              f"best {closest_gaps[0]:.0f}, worst {closest_gaps[-1]:.0f}")

    assert sum(outcomes.values()) == TRIPS
