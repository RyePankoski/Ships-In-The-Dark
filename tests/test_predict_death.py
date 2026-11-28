import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from objects.asteroid import Asteroid
from objects.ship import Ship
from simulation.world import World, empty_command

pygame.display.init()  # Ship reads the desktop size on construction


def _world_with_fast_ship_in_rock():
    """One player ship at speed, sitting inside an asteroid: a crash by any reckoning."""
    world = World(seed=1, with_npcs=False)
    world.asteroids.clear()  # drop the generated field so only the rock below can hit
    ship = Ship(500, 500, player_id=1)
    ship.set_velocity(150, 0)  # over the 100 crash threshold, under SHIP_MAX_SPEED
    world.ships.append(ship)
    rock = Asteroid(*ship.rect.center, 60)  # centred on the ship
    world.asteroids.add_to_grid(rock)
    return world, ship


def test_predict_does_not_kill_ship_on_asteroid():
    # A client's prediction is motion only; death is the server's call and arrives in a snapshot.
    world, ship = _world_with_fast_ship_in_rock()

    world.predict(1, empty_command(), 0.016)

    assert ship.alive is True


def test_step_kills_same_ship_on_asteroid():
    # Control: the same setup does kill on the server, so the test above is checking something real.
    world, ship = _world_with_fast_ship_in_rock()

    world.step({}, 0.016)

    assert ship.alive is False
