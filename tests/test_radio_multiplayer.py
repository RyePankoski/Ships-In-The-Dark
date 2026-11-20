import os
import time
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame

from netcode.net_client import NetClient
from netcode.server import TICK_DT, Server
from radio.radio import Radio
from simulation.snapshot import apply_snapshot
from simulation.world import World, empty_command
from utility.constants import RADAR_SWEEP_MIN_INTERVAL

PORT = 27999

pygame.display.init()
pygame.display.set_mode((1280, 720))  # Ship reads the screen size


def pump(server, clients, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        server.run(0.02)
        for c in clients:
            c.update(0.02)
        time.sleep(0.02)


class RadioMultiplayerTests(unittest.TestCase):
    def setUp(self):
        self.server = Server(port=PORT)
        self.addCleanup(self.server.close)
        self.a = NetClient('127.0.0.1', 'AAA', port=PORT)
        self.b = NetClient('127.0.0.1', 'BBB', port=PORT)
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)
        pump(self.server, [self.a, self.b], 0.5)
        self.server.launch()
        pump(self.server, [self.a, self.b], 0.3)

    def test_sweep_reaches_other_players_log(self):
        self.assertTrue(self.a.welcomed and self.b.welcomed)
        command = empty_command()
        command['actions'] = [{'type': 'radar_sweep'}]
        self.a.send_command(command)
        pump(self.server, [self.a, self.b], 0.4)

        events = [e for e in self.b.take_events() if e[0] == 'radar_sweep']
        self.assertEqual(len(events), 1)
        kind, source_id, x, y, timestamp = events[0]
        self.assertEqual(source_id, self.a.player_id)
        # The server's own log has it too, stamped with its clock
        self.assertEqual(len(self.server.world.emissions.recent(self.server.world.time)), 1)

    def test_server_ignores_sweep_spam(self):
        world = self.server.world
        ship = world.get_ship(self.a.player_id)
        for _ in range(3):
            world.do_action(ship, {'type': 'radar_sweep'})
        self.assertEqual(len(world.emissions.recent(world.time)), 1)
        world.time += RADAR_SWEEP_MIN_INTERVAL + 0.1
        world.do_action(ship, {'type': 'radar_sweep'})
        self.assertEqual(len(world.emissions.recent(world.time)), 2)


if __name__ == '__main__':
    unittest.main()
