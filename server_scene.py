import random

from ship import Ship
from constants import *


class ServerScene:
    def __init__(self, connected_players=None):
        self.connected_players = []
        self.player_ships = []
        self.game_state = {}

    def create_player_ships(self, address):
        ship = Ship(random.randint(0, 1000), random.randint(0, 1000), player_id=address)
        self.player_ships.append(ship)

    def step(self, messages, dt):

        print(f"[SERVER] I have {len(self.player_ships)} ships")

        for message in messages:
            player_id = message.get('player_id')
            input_data = message.get('input_data')

            for ship in self.player_ships:
                if ship.player_id == player_id:
                    ship.apply_inputs(input_data, dt)
                    break

        for ship in self.player_ships:
            ship.run(dt)

        self.game_state = {
            'player_ships': self.player_ships,
        }

    def get_state(self):
        return self.game_state