import json
import random

from draw import Draw
from ship import Ship
from missile import Missile
from false_contact import FalseContact
from decoy import Decoy

from util import end_blit


class MainScene:
    def __init__(self, connected):
        self.connected = connected
        self.my_player_id = None  # Track which player_id is ours

        self.draw = Draw()

        self.player_ship = Ship(100, 100, is_player=True)

        self.enemy_ship = Ship(1000, 1000, is_player=False)
        self.enemy_ship.vel_x = 1 / 5
        self.enemy_ship.vel_y = -2 / 5
        
        self.enemy_ship.dampening = False

        self.ships = []
        self.ships.append(self.player_ship)
        self.ships.append(self.enemy_ship)

        self.missiles = []
        self.explosions = []

    def run(self, inputs, dt):
        if not self.connected:
            # Local single-player mode
            self.handle_inputs(inputs, dt)
            self.handle_ships(dt)
            self.handle_missiles(dt)

            if random.random() < 0.005:
                self.missiles.append(Missile(self.enemy_ship.pos_x, self.enemy_ship.pos_y, 0, 0, self.player_ship))

        # Always render
        self.draw_scene(inputs)

    def handle_inputs(self, inputs, dt):
        self.player_ship.apply_inputs(inputs, dt)

        if inputs["p"] and self.player_ship.total_velocity < 0.1:
            self.fire_missile()

    def fire_missile(self):
        missile = Missile(self.player_ship.pos_x, self.player_ship.pos_y, 0, 0, self.enemy_ship)
        self.missiles.append(missile)

    def handle_ships(self, dt):
        for ship in self.ships:
            ship.run(dt)

    def handle_missiles(self, dt):
        missiles_to_remove = []
        for missile in self.missiles:
            missile.run(dt)
            if missile.alive is False:
                missiles_to_remove.append(missile)

        for missile in missiles_to_remove:
            self.explosions.append(missile.rect.center)
            self.missiles.remove(missile)

    def draw_scene(self, inputs):
        self.draw.start_blit()
        self.draw.draw_ships(self.ships)
        self.draw.draw_missiles(self.missiles)
        self.draw.draw_explosions(self.explosions)
        self.explosions = []
        end_blit()

    def inject_server_data(self, message):
        message_dict = json.loads(message)

        # Store our player_id so we know which ship is ours
        self.my_player_id = message_dict.get('your_player_id')

        ship_dicts = message_dict['player_ships']

        # Reconstruct ships from server data
        self.ships = []
        for ship_dict in ship_dicts:
            # Determine if this is our ship
            is_player = (ship_dict['player_id'] == self.my_player_id)

            ship = Ship(
                x=ship_dict['pos_x'],
                y=ship_dict['pos_y'],
                is_player=is_player,
                player_id=ship_dict['player_id']
            )
            ship.vel_x = ship_dict['vel_x']
            ship.vel_y = ship_dict['vel_y']
            ship.heading = ship_dict['heading']
            self.ships.append(ship)