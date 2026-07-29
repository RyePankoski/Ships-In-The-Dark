import json
import random

from constants import WORLD_HEIGHT, WORLD_WIDTH
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
        self.enemy_ship = Ship(random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT), is_player=False)
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
            self.handle_inputs(inputs, dt)
            self.handle_missiles(dt)
            self.handle_ships(dt)
            if random.random() < 0.005:
                self.missiles.append(Missile(self.enemy_ship.pos_x, self.enemy_ship.pos_y, 0, 0, self.player_ship))

        self.draw_scene(inputs)

    def handle_inputs(self, inputs, dt):
        self.player_ship.apply_inputs(inputs, dt)
        if inputs["p"] and self.player_ship.can_fire():
            self.fire_missile()
            self.player_ship.fire()
            print(self.player_ship.total_missiles)

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

        # Find player ship and calculate camera position
        player_ship = next((ship for ship in self.ships if ship.player), None)
        if player_ship:
            camera_x = player_ship.rect.center[0] - self.draw.screen.get_width() / 2
            camera_y = player_ship.rect.center[1] - self.draw.screen.get_height() / 2
        else:
            camera_x = 0
            camera_y = 0

        # Draw starfield first (background)
        self.draw.draw_stars(camera_x, camera_y)

        # Then draw game objects on top
        self.draw.draw_ships(self.ships, camera_x, camera_y)
        self.draw.draw_missiles(self.missiles, camera_x, camera_y)
        self.draw.draw_explosions(self.explosions, camera_x, camera_y)
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
            ship.heading = ship_dict['heading']
            ship.vel_x = ship_dict['vel_x']
            ship.vel_y = ship_dict['vel_y']
            self.ships.append(ship)

        # Reconstruct missiles from server data
        missile_dicts = message_dict.get('missiles', [])
        self.missiles = []
        for missile_dict in missile_dicts:
            missile = Missile(
                x=missile_dict['pos_x'],
                y=missile_dict['pos_y'],
                vx=0,
                vy=0,
                contact=None  # Server handles targeting
            )
            missile.heading = missile_dict['heading']
            missile.velocity = missile_dict['velocity']
            missile.fuel = missile_dict['fuel']
            missile.alive = missile_dict['alive']
            self.missiles.append(missile)
