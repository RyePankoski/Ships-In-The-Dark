import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from asset_handlers.draw_ui import DrawUI
from core.replay import ReplayState, record_flights
from simulation.snapshot import apply_snapshot, make_snapshot
from config.constants import BLINK_RECORD_MARK, POSITION_RECORD_SECONDS
from simulation.world import World, empty_command

pygame.display.init()  # Ship reads the desktop size on construction


def _world(paths):
    ships = [SimpleNamespace(player_id=i, position_record=path) for i, path in enumerate(paths)]
    callsigns = {i: f"PILOT-{i}" for i in range(len(paths))}
    return SimpleNamespace(asteroids=[], width=1000, height=1000, ships=ships, callsigns=callsigns)


def test_last_sample_is_longest_path_minus_one():
    replay = ReplayState(_world([[(0, 0)] * 4, [(0, 0)] * 9]))
    assert replay.last_sample == 8


def test_replay_copies_the_records():
    world = _world([[(0, 0), (10, 10)]])
    replay = ReplayState(world)
    world.ships[0].position_record.append((99, 99))
    assert replay.pilots[0][1] == [(0, 0), (10, 10)]


def test_step_forward_and_back_land_on_whole_samples():
    replay = ReplayState(_world([[(0, 0)] * 5]))
    replay.progress = 1.4
    replay.step_forward()
    assert replay.progress == 2
    replay.step_back()
    assert replay.progress == 1
    replay.step_back()
    replay.step_back()
    assert replay.progress == 0


def test_step_forward_stops_at_the_last_sample():
    replay = ReplayState(_world([[(0, 0)] * 3]))
    for _ in range(10):
        replay.step_forward()
    assert replay.progress == replay.last_sample == 2


def test_play_stops_at_the_end_and_play_again_restarts():
    replay = ReplayState(_world([[(0, 0)] * 3]))
    replay.play_pause()
    replay.update(10.0)
    assert replay.progress == replay.last_sample
    assert replay.playing is False
    replay.play_pause()
    assert replay.progress == 0.0
    assert replay.playing is True


def test_track_runs_interpolates_the_head_between_samples():
    path = [(0, 0), (100, 0), (100, 100)]
    assert DrawUI._track_runs(path, 0.0) == ([[(0, 0)]], [])
    assert DrawUI._track_runs(path, 1.5) == ([[(0, 0), (100, 0), (100, 50)]], [])
    assert DrawUI._track_runs(path, 2.0) == ([[(0, 0), (100, 0), (100, 100)]], [])


def test_blink_mark_splits_the_line_and_pairs_both_sides():
    path = [(0, 0), (100, 0), BLINK_RECORD_MARK, (500, 500), (600, 500)]
    runs, gaps = DrawUI._track_runs(path, 4.0)
    assert runs == [[(0, 0), (100, 0)], [(500, 500), (600, 500)]]
    assert gaps == [((100, 0), (500, 500))]


def test_gap_waits_for_its_far_side_before_pairing():
    path = [(0, 0), (100, 0), BLINK_RECORD_MARK, (500, 500)]
    runs, gaps = DrawUI._track_runs(path, 2.0)
    assert runs == [[(0, 0), (100, 0)]]
    assert gaps == [((100, 0), None)]


def test_no_gap_before_the_mark_is_reached():
    path = [(0, 0), (100, 0), BLINK_RECORD_MARK, (500, 500)]
    assert DrawUI._track_runs(path, 1.5) == ([[(0, 0), (100, 0)]], [])


def test_no_interpolation_across_a_blink_mark():
    path = [(0, 0), BLINK_RECORD_MARK, (500, 500)]
    runs, gaps = DrawUI._track_runs(path, 1.5)
    assert runs == [[(0, 0)]]
    assert gaps == [((0, 0), None)]


def test_record_flights_marks_a_blink_once_when_the_charge_ends():
    world = _world([[(0, 0)]])
    ship = world.ships[0]
    ship.record_position = lambda dt: None
    ship.was_blinking = False
    ship.blinking = True
    for _ in range(5):  # a blink takes several frames to charge
        record_flights(world, 0.05)
    assert ship.position_record == [(0, 0)]
    ship.blinking = False
    record_flights(world, 0.05)
    record_flights(world, 0.05)
    assert ship.position_record == [(0, 0), BLINK_RECORD_MARK]


def test_blink_mark_sits_between_the_pre_jump_and_post_jump_samples():
    # Same frame order as single player: record, then the scene sets the flag and the
    # world applies the jump. Charge is 6 s (120 frames); samples come every 5 s.
    world = World(seed=1, with_npcs=False)
    world.asteroids.clear()
    world.spawn_ship(1, is_ai=False, x=500, y=500)
    ship = world.get_ship(1)
    for frame in range(240):
        record_flights(world, 0.05)
        ship.blinking = frame < 120
        if frame == 120:
            ship.pos_x, ship.pos_y = 3000, 3000  # the jump, as do_action('blink') does it
    record = ship.position_record
    mark = record.index(BLINK_RECORD_MARK)
    assert record[mark - 1] == (500, 500)  # last sample from before the jump
    assert record[mark + 1] == (3000, 3000)  # first sample from after it
    assert (3000, 3000) not in record[:mark]


def test_track_runs_handles_empty_path():
    assert DrawUI._track_runs([], 3.0) == ([], [])


def test_each_blink_gets_its_own_pair():
    path = [(0, 0), BLINK_RECORD_MARK, (10, 10), (20, 20), BLINK_RECORD_MARK, (30, 30)]
    _, gaps = DrawUI._track_runs(path, 5.0)
    assert gaps == [((0, 0), (10, 10)), ((20, 20), (30, 30))]


def test_client_builds_flight_record_from_snapshots():
    server = World(seed=1, with_npcs=False)
    server.asteroids.clear()
    server.spawn_ship(1, is_ai=False, x=500, y=500)
    client = World(seed=1, with_npcs=False)
    client.asteroids.clear()

    for _ in range(int(35 / 0.05)):  # 35 seconds at 20 frames a second
        server.step({1: empty_command()}, 0.05)
        apply_snapshot(client, make_snapshot(server), age=0.0)
        record_flights(client, 0.05)

    samples = len(client.get_ship(1).position_record)
    assert 35 // POSITION_RECORD_SECONDS <= samples <= 35 // POSITION_RECORD_SECONDS + 3
    assert len(server.get_ship(1).position_record) == 1  # the server no longer samples in run_ship
    assert ReplayState(client).last_sample >= 3


def test_client_sees_a_blink_from_the_snapshot():
    server = World(seed=1, with_npcs=False)
    server.asteroids.clear()
    server.spawn_ship(1, is_ai=False, x=500, y=500)
    client = World(seed=1, with_npcs=False)
    client.asteroids.clear()

    for frame in range(60):
        server.get_ship(1).blinking = 10 <= frame < 40  # charging for 30 frames
        server.step({1: empty_command()}, 0.05)
        apply_snapshot(client, make_snapshot(server), age=0.0)
        record_flights(client, 0.05)

    assert client.get_ship(1).position_record.count(BLINK_RECORD_MARK) == 1
