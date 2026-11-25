import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from objects.asteroid import Asteroid
from simulation.world import World

pygame.display.init()  # Ship reads the desktop size on construction


def _world_with_ai_crossing_rock():
    """An AI ship heading straight east for a destination, with a rock dead on its path."""
    world = World(seed=1, with_npcs=False)
    world.asteroids.clear()
    world.spawn_ship(2, is_ai=True, x=500, y=500)
    ai = world.ai_list[0]
    rock = Asteroid(800, 500, 60)
    world.asteroids.add_to_grid(rock)
    ai.destination = (1200, 500)
    return world, ai, rock


def test_ai_run_does_not_move_its_ship():
    # The world moves every ship in _step_ships; AI.run must only steer, or the ship moves twice a frame.
    world, ai, rock = _world_with_ai_crossing_rock()
    ship = ai.ship
    start = (ship.pos_x, ship.pos_y)

    ai.run(0.016, world.ships, world.asteroids, world.drones, world.bullets, world.lasers)

    assert (ship.pos_x, ship.pos_y) == start


def test_ai_steers_around_rock_on_its_path():
    world, ai, rock = _world_with_ai_crossing_rock()
    ship = ai.ship

    closest = math.inf
    for _ in range(600):
        world.step({}, 0.016)
        if not ship.alive:
            break
        closest = min(closest, math.dist((ship.pos_x, ship.pos_y), (rock.pos_x, rock.pos_y)))

    assert ship.alive is True
    assert closest > rock.size


def test_ai_with_clear_path_flies_straight():
    world = World(seed=1, with_npcs=False)
    world.asteroids.clear()
    world.spawn_ship(2, is_ai=True, x=500, y=500)
    ai = world.ai_list[0]
    ai.destination = (1200, 500)

    for _ in range(20):
        world.step({}, 0.016)

    assert ai.avoid_x == 0.0
    assert abs(ai.ship.dir_y) < 1e-9
