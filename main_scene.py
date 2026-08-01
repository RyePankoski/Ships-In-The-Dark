import json
import random

from constants import WORLD_HEIGHT, WORLD_WIDTH, GRID_SIZE
from draw_game import DrawGame
from draw_ui import DrawUI
from ship import Ship
from missile import Missile
from player_ship_ai import PlayerShipAI
from asteroid import Asteroid
from radar_system import RadarSystem

from util import end_blit


class MainScene:
    def __init__(self, connected, screen, audio_manager):
        # Classes
        self.audio_manager = audio_manager
        self.draw_game = DrawGame(screen)
        self.draw_ui = DrawUI(screen)
        self.player_ship_ai = PlayerShipAI()
        self.radar_system = RadarSystem()

        # Netcode stuff
        self.connected = connected
        self.my_player_id = None

        # Lists
        self.ships = []
        self.explosions = []
        self.missiles = []
        self.asteroids = {}
        self.signatures = []

        # Create player ship and enemy ship
        if not self.connected:
            self.player_ship = Ship(random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT), is_player=True,
                                    player_id=1)
            self.enemy_ship = Ship(random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT), is_player=False)
            self.enemy_ship.vel_x = 50
            self.enemy_ship.vel_y = 60
            self.enemy_ship.dampening = False
            self.ships.append(self.enemy_ship)

            for i in range(200):
                pos_x = random.randint(0, WORLD_WIDTH)
                pos_y = random.randint(0, WORLD_HEIGHT)

                grid_x = int(pos_x // GRID_SIZE)
                grid_y = int(pos_y // GRID_SIZE)
                cell = (grid_x, grid_y)

                if cell not in self.asteroids:
                    self.asteroids[cell] = []

                asteroid = Asteroid(pos_x, pos_y, random.randint(20,100 ))
                self.asteroids[cell].append(asteroid)


        else:
            self.player_ship = Ship(100, 100, is_player=True)

        self.ships.append(self.player_ship)

        # Weapons systems
        self.has_missile_solution = True
        self.enemy_has_missile_solution = False

        # UI stuff
        self.grid_on = True
        self.manual_control = True

    def run(self, inputs, dt):

        if not self.connected:
            self.handle_inputs(inputs, dt)
            self.handle_missiles(dt)
            self.handle_ships(dt)

        if self.radar_system.scanning:
            self.signatures.extend(self.radar_system.continue_scan())

        self.handle_general_sound_effects()
        self.draw_scene()

    def handle_inputs(self, inputs, dt):

        if self.manual_control:
            self.player_ship.apply_inputs(inputs, dt)
        else:
            print("Ai mode")
            self.player_ship_ai.run_ship_ai(self.player_ship)

        self.handle_input_based_sound_effects(inputs)

        if inputs["p"] and self.player_ship.can_fire() and self.has_missile_solution:
            self.fire_missile()
            self.player_ship.fire()

        if inputs["m"]:
            self.manual_control = not self.manual_control

        if inputs["x"]:
            self.enemy_ship.fire()
            self.missiles.append(Missile(self.enemy_ship.pos_x, self.enemy_ship.pos_y, 0, 0, self.player_ship,
                                         self.enemy_ship.player_id))

        if inputs['r']:
            if self.radar_system.scanning:
                return
            self.signatures = []
            self.radar_system.begin_scan(self.player_ship, self.ships, self.asteroids)

    def handle_input_based_sound_effects(self, inputs):
        if self.manual_control:

            if inputs['up'] or inputs['left'] or inputs['down'] or inputs['right']:
                self.audio_manager.play_sfx('thrust')
            else:
                self.audio_manager.stop_sfx('thrust')

        if inputs['m']:
            self.audio_manager.play_sfx('retro_beep')

        if inputs['r']:
            self.audio_manager.play_sfx('radar')

    def handle_general_sound_effects(self):
        if self.enemy_has_missile_solution:
            self.audio_manager.play_sfx('enemy_missile_lock')
        else:
            self.audio_manager.stop_sfx('enemy_missile_lock')

    def fire_missile(self):
        missile = Missile(self.player_ship.pos_x, self.player_ship.pos_y, 0, 0, self.enemy_ship,
                          self.player_ship.player_id)
        self.missiles.append(missile)

    def handle_ships(self, dt):
        for ship in self.ships:
            ship.run(dt)

            ship_grid_x = int(ship.rect.center[0] // GRID_SIZE)
            ship_grid_y = int(ship.rect.center[1] // GRID_SIZE)

            if (ship_grid_x, ship_grid_y) in self.asteroids:
                for asteroid in self.asteroids[(ship_grid_x, ship_grid_y)]:
                    distance = (ship.rect.center[0] - asteroid.pos_x) ** 2 + (ship.rect.center[1] - asteroid.pos_y) ** 2
                    if distance < asteroid.size ** 2:
                        print("Collision")

                        ship.vel_x *= -1.5
                        ship.vel_y *= -1.5

    def handle_missiles(self, dt):
        if not self.missiles:
            self.enemy_has_missile_solution = False

        for missile in self.missiles:
            if missile.owner == self.player_ship.player_id:
                continue
            if missile.contact == self.player_ship:
                self.enemy_has_missile_solution = True

        missiles_to_remove = []
        for missile in self.missiles:
            missile.run(dt, self.asteroids)
            if missile.alive is False:
                missiles_to_remove.append(missile)

        for missile in missiles_to_remove:
            self.explosions.append(missile.rect.center)
            self.missiles.remove(missile)

    def draw_scene(self):
        self.draw_game.start_blit()

        # Find player ship and calculate camera position
        player_ship = next((ship for ship in self.ships if ship.player), None)
        if player_ship:
            camera_x = player_ship.rect.center[0] - self.draw_game.screen.get_width() / 2
            camera_y = player_ship.rect.center[1] - self.draw_game.screen.get_height() / 2
        else:
            camera_x = 0
            camera_y = 0

        # Draw the starfield first (background)
        self.draw_game.draw_stars(camera_x, camera_y)

        # Then draw game objects on top
        self.draw_game.draw_ships(self.ships, camera_x, camera_y)
        self.draw_game.draw_missiles(self.missiles, camera_x, camera_y)
        self.draw_game.draw_explosions(self.explosions, camera_x, camera_y)
        self.draw_game.draw_asteroids(self.asteroids, camera_x, camera_y)
        self.explosions = []

        # UI elements and crt effect
        self.draw_ui.draw_world_grid(camera_x, camera_y, self.grid_on)
        self.draw_ui.draw_ui_layout()
        self.draw_ui.draw_weapon_solution_indicator(self.has_missile_solution)
        self.draw_ui.draw_manual_control_indicator(self.manual_control)
        self.draw_ui.draw_ship_info(self.player_ship)
        self.draw_ui.draw_missile_lock_warning(self.enemy_has_missile_solution)
        self.draw_ui.draw_missile_vectors(self.player_ship.player_id, self.missiles, self.player_ship, camera_x,
                                          camera_y)
        self.draw_ui.draw_radar(self.player_ship, self.signatures)
        self.draw_ui.draw_scanlines()

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
                , owner=1)
            missile.heading = missile_dict['heading']
            missile.velocity = missile_dict['velocity']
            missile.fuel = missile_dict['fuel']
            missile.alive = missile_dict['alive']
            self.missiles.append(missile)
