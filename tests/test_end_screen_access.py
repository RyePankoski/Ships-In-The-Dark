import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from asset_handlers.draw_ui import DrawUI
from core.main_scene import MainScene
from simulation.world import World

pygame.init()  # Ship reads the desktop size; DrawUI loads fonts


class _SilentAudio:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def _multiplayer_scene(alive_by_id):
    screen = pygame.display.set_mode((1600, 900))
    world = World(seed=3, with_npcs=False)
    for player_id, alive in alive_by_id.items():
        world.spawn_ship(player_id, is_ai=False, x=500 + player_id * 200, y=500)
        world.get_ship(player_id).alive = alive
    world.outcome = 'dead'
    config = SimpleNamespace(my_id=1, local=False, is_host=False)
    return MainScene(screen, _SilentAudio(), world, config, DrawUI(screen))


def test_dead_pilot_spectates_while_two_others_fly():
    scene = _multiplayer_scene({1: False, 2: True, 3: True})
    scene.update(0.016, [])
    assert scene.view == 'spectate'


def test_dead_pilot_gets_end_screen_when_one_other_is_left():
    scene = _multiplayer_scene({1: False, 2: False, 3: True})
    scene.update(0.016, [])
    assert scene.view == 'end'


def test_replay_option_is_on_the_end_screen_for_a_dead_pilot():
    scene = _multiplayer_scene({1: False, 2: False, 3: False})
    scene.update(0.016, [])
    scene.draw()
    scene.update_end(clicks=('replay',), events=[])
    assert scene.replay is not None
