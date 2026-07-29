import random

from ship import Ship
from constants import *

class ServerScene:
    def __init__(self, connected_players=None):
        self.connected_players = connected_players
        self.player_ships = []



    def create_player_ships(self):
        for address in self.connected_players:
            ship = Ship(random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT), player_id=address)
            self.player_ships.append(ship)