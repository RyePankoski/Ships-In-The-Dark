import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from simulation.world import World

pygame.display.init()  # Ship reads the desktop size on construction


def test_single_player_sets_both_callsigns():
    world = World(seed=1, with_npcs=False)
    world.setup_single_player("MAVERICK", player_id=1, enemy_id=2, enemy_callsign="BANDIT")

    assert world.callsigns == {1: "MAVERICK", 2: "BANDIT"}


def test_single_player_blank_callsign_falls_back_to_pilot_id():
    world = World(seed=1, with_npcs=False)
    world.setup_single_player("", player_id=1, enemy_id=2)

    assert world.callsigns[1] == "PILOT-1"
    assert world.callsigns[2] == "UNKNOWN"
