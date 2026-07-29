import random
from ship import Ship
from missile import Missile
from constants import *


class ServerScene:
    def __init__(self, connected_players=None):
        self.connected_players = []
        self.player_ships = []
        self.missiles = []
        self.game_state = {
            'player_ships': [],
            'missiles': [],
        }

    def create_player_ships(self, address):
        ship = Ship(random.randint(0, 1000), random.randint(0, 1000), player_id=address)
        self.player_ships.append(ship)

    def step(self, messages, dt):

        for message in messages:
            player_id = message.get('player_id')
            input_data = message.get('input_data')

            player_ship = None
            for ship in self.player_ships:
                if ship.player_id == player_id:
                    ship.apply_inputs(input_data, dt)
                    player_ship = ship
                    break

            other_ship = None
            for ship in self.player_ships:
                if ship.player_id != player_id:
                    other_ship = ship
                    break

            if input_data['p'] and player_ship is not None:
                if player_ship.can_fire():
                    print(f"[SERVER] Player {player_id} fired")
                    missile = Missile(player_ship.pos_x, player_ship.pos_y, 0, 0, other_ship)
                    self.missiles.append(missile)
                    player_ship.fire()

        self.handle_ships(dt)
        self.handle_missiles(dt)

        self.game_state = {
            'player_ships': self.player_ships,
            'missiles': self.missiles,
        }

    def handle_ships(self, dt):
        for ship in self.player_ships:
            ship.run(dt)

    def handle_missiles(self, dt):
        for missile in self.missiles:
            missile.run(dt)

        missiles_to_remove = []
        for missile in self.missiles:
            missile.run(dt)
            if missile.alive is False:
                missiles_to_remove.append(missile)

        for missile in missiles_to_remove:
            self.missiles.remove(missile)

    def get_state(self):
        return self.game_state
