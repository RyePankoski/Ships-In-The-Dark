import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from objects.ship import Ship
from simulation.world import World

pygame.display.init()  # Ship reads the desktop size on construction


def _world_with_pilots(*player_ids):
    world = World(seed=1, with_npcs=False)
    world.asteroids = {}
    for player_id in player_ids:
        world.ships.append(Ship(500, 500, player_id=player_id))
    return world


def test_playing_while_me_and_an_enemy_are_alive():
    world = _world_with_pilots(1, 2)

    assert world.outcome_for(1) == 'playing'


def test_dead_when_my_ship_is_gone():
    world = _world_with_pilots(1, 2)
    world.get_ship(1).alive = False

    assert world.outcome_for(1) == 'dead'


def test_won_when_every_other_pilot_is_gone():
    world = _world_with_pilots(1, 2, 3)
    world.get_ship(2).alive = False
    world.get_ship(3).alive = False

    assert world.outcome_for(1) == 'won'


def test_lone_pilot_is_not_won():
    # Nobody to beat yet: the game goes on
    world = _world_with_pilots(1)

    assert world.outcome_for(1) == 'playing'


def test_dead_takes_priority_over_won():
    world = _world_with_pilots(1, 2)
    world.get_ship(1).alive = False
    world.get_ship(2).alive = False

    assert world.outcome_for(1) == 'dead'


def test_each_pilot_gets_their_own_outcome():
    world = _world_with_pilots(1, 2)
    world.get_ship(2).alive = False

    assert world.outcome_for(1) == 'won'
    assert world.outcome_for(2) == 'dead'
