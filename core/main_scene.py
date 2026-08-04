import json
import random

from instruments.laser_assessor import LaserAssessor
from utility.constants import WORLD_HEIGHT, WORLD_WIDTH, GRID_SIZE
from asset_handlers.draw_game import DrawGame
from asset_handlers.draw_ui import DrawUI
from objects.ship import Ship
from objects.missile import Missile
from ai.player_ship_ai import PlayerShipAI
from objects.asteroid import Asteroid
from instruments.radar_system import RadarSystem
from instruments.deep_field_scan import DeepFieldScan
from instruments.close_range_scan import CloseRangeScan
from objects.drone import Drone

from utility.util import end_blit


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
        self.drones = {}
        self.asteroids = {}

        # Create player ship and enemy ship
        if not self.connected:
            self.player_ship = Ship(random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT), is_player=True, player_id=1)
            self.enemy_ship = Ship(random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT), is_player=False, is_painted=False, is_ai=True)

            self.enemy_ship.vel_x = 50
            self.enemy_ship.vel_y = 60
            self.enemy_ship.dampening = False
            self.ships.append(self.enemy_ship)

            for i in range(100):
                pos_x = random.randint(0, WORLD_WIDTH)
                pos_y = random.randint(0, WORLD_HEIGHT)

                grid_x = int(pos_x // GRID_SIZE)
                grid_y = int(pos_y // GRID_SIZE)
                cell = (grid_x, grid_y)

                if cell not in self.asteroids:
                    self.asteroids[cell] = []

                asteroid = Asteroid(pos_x, pos_y, random.randint(50, 100))
                self.asteroids[cell].append(asteroid)

            for i in range(8):
                pos_x = random.randint(0, WORLD_WIDTH)
                pos_y = random.randint(0, WORLD_HEIGHT)

                grid_x = int(pos_x // GRID_SIZE)
                grid_y = int(pos_y // GRID_SIZE)
                cell = (grid_x, grid_y)

                if cell not in self.drones:
                    self.drones[cell] = []

                drone = Drone(pos_x, pos_y, 40)
                self.drones[cell].append(drone)
        else:
            self.player_ship = Ship(100, 100, is_player=True)

        # Laser system
        self.ships.append(self.player_ship)
        self.laser_assessor = LaserAssessor(self.player_ship)
        self.close_range_scan = CloseRangeScan(self.player_ship)

        self.laser_endpoint = (0, 0)
        self.unpainted_all = False
        self.target_type = "Nothing"

        # Deep field scan
        self.deep_field_scan = DeepFieldScan(self.player_ship)

        # Weapons systems

        # Map Screen
        self.is_map_open = False

        # UI stuff
        self.grid_on = True
        self.end_tripped = False

        # input timer
        self.input_timer = 0
        self.input_timer_cooldown = 0.2
        self.input_cooling_down = False

    def enemy_ai(self):
        pass

    def run(self, inputs, dt):
        if not self.player_ship.alive:
            if not self.end_tripped:
                self.audio_manager.stop_all()
                self.audio_manager.play_sfx('death_screen')
                self.end_tripped = True
            return

        # Let the server handle inputs and simulation
        if not self.connected:
            self.handle_inputs(inputs, dt)
            self.handle_missiles(dt)
            self.handle_ships(dt)
            self.handle_drones(dt)

        self.close_range_scan.update(self.ships, self.asteroids, self.drones)

        self.handle_radar()
        self.handle_laser(inputs)
        self.handle_general_sound_effects()
        self.draw_scene()

    def handle_inputs(self, inputs, dt):
        if self.player_ship.laser_on:
            if inputs['arrow_key_left'] or inputs['arrow_key_right']:
                self.audio_manager.play_sfx('laser_dir_change')
            else:
                self.audio_manager.stop_sfx('laser_dir_change')

        if self.player_ship.manual_control:
            if inputs['up'] or inputs['left'] or inputs['down'] or inputs['right']:
                self.audio_manager.play_sfx('thrust')
            else:
                self.audio_manager.stop_sfx('thrust')

        if self.player_ship.manual_control:
            self.player_ship.apply_inputs(inputs, dt)
        else:
            self.player_ship_ai.run_ship_ai(self.player_ship)

        if self.input_cooling_down:
            self.input_timer += dt
            if self.input_timer > self.input_timer_cooldown:
                self.input_timer = 0
                self.input_cooling_down = False

        if not self.input_cooling_down:
            if inputs["p"] and self.player_ship.can_fire() and self.player_ship.has_missile_solution:
                self.fire_missile()
                self.player_ship.fire()
                self.input_cooling_down = True
                self.audio_manager.play_sfx('fire_missile')
            if inputs["l"]:
                self.player_ship.manual_control = not self.player_ship.manual_control
                self.audio_manager.play_sfx('retro_beep')
                self.input_cooling_down = True
            if inputs["x"]:
                self.enemy_ship.fire()
                self.missiles.append(Missile(self.enemy_ship.pos_x, self.enemy_ship.pos_y, 0, 0, self.player_ship, self.enemy_ship.player_id))

                self.input_cooling_down = True
            if inputs['r']:
                self.audio_manager.play_sfx('radar')
                self.player_ship.unconfirmed_signatures = []
                self.radar_system.begin_scan(self.player_ship, self.ships, self.asteroids, self.drones)
                self.input_cooling_down = True
            if inputs['i']:
                self.player_ship.laser_on = not self.player_ship.laser_on
                self.laser_assessor.set_direction(self.player_ship.heading)
                self.audio_manager.play_sfx('laser')
                self.input_cooling_down = True

            if inputs['k']:
                self.player_ship.dfs_on = not self.player_ship.dfs_on
                self.audio_manager.play_sfx('dfs_toggle')
                self.input_cooling_down = True
                self.player_ship.deep_field_contacts = []

            if inputs['m']:
                self.is_map_open = not self.is_map_open
                self.input_cooling_down = True

                if self.is_map_open:
                    self.audio_manager.play_sfx('map_open')
                else:
                    self.audio_manager.play_sfx('map_close')

            if self.player_ship.dfs_on:
                if inputs['o']:
                    self.player_ship.deep_field_contacts = self.deep_field_scan.run_scan(self.ships, self.asteroids, self.drones)

                    self.audio_manager.play_sfx('dfs_scan')
                    self.input_cooling_down = True

                if inputs['arrow_key_up'] or inputs['arrow_key_down']:
                    self.deep_field_scan.change_direction(inputs)
                    self.audio_manager.play_sfx('dfs_dir_change')
                    self.player_ship.deep_field_contacts = []
                    self.input_cooling_down = True
                else:
                    self.audio_manager.stop_sfx('dfs_dir_change')

    def handle_radar(self):
        if self.radar_system.scanning:
            self.player_ship.unconfirmed_signatures.extend(self.radar_system.continue_scan())

    def handle_laser(self, inputs):
        if self.player_ship.laser_on:
            self.laser_endpoint, self.target_type = self.laser_assessor.shine_laser(self.ships, self.asteroids, self.drones)

            self.laser_assessor.change_direction(inputs)
            self.unpainted_all = False
        elif not self.unpainted_all:
            self.unpainted_all = True
            for cell in self.asteroids.values():
                for asteroid in cell:
                    asteroid.painted = False
            for ship in self.ships:
                ship.painted = False
            for cell in self.drones.values():
                for drone in cell:
                    drone.is_painted = False

    def handle_general_sound_effects(self):
        if self.player_ship.enemy_has_missile_solution:
            self.audio_manager.play_sfx('enemy_missile_lock')
        else:
            self.audio_manager.stop_sfx('enemy_missile_lock')

    def handle_drones(self, dt):
        for cell in list(self.drones.keys()):
            for drone in list(self.drones[cell]):
                drone.run_drone(self.asteroids, dt)

                # Only update the grid if the cell changed
                new_cell = (int(drone.pos_x // GRID_SIZE), int(drone.pos_y // GRID_SIZE))
                if new_cell != drone.cell:
                    self.drones[drone.cell].remove(drone)
                    if not self.drones[drone.cell]:
                        del self.drones[drone.cell]

                    if new_cell not in self.drones:
                        self.drones[new_cell] = []
                    self.drones[new_cell].append(drone)
                    drone.cell = new_cell

    def handle_ships(self, dt):
        for ship in self.ships:
            ship.run(dt)

            ship_grid_x = int(ship.rect.center[0] // GRID_SIZE)
            ship_grid_y = int(ship.rect.center[1] // GRID_SIZE)

            if (ship_grid_x, ship_grid_y) in self.asteroids:
                for asteroid in self.asteroids[(ship_grid_x, ship_grid_y)]:
                    distance = (ship.rect.center[0] - asteroid.pos_x) ** 2 + (ship.rect.center[1] - asteroid.pos_y) ** 2
                    if distance < asteroid.size ** 2:
                        ship.vel_x *= -1.5
                        ship.vel_y *= -1.5

    def handle_missiles(self, dt):
        if not self.missiles:
            self.player_ship.enemy_has_missile_solution = False

        for missile in self.missiles:
            if missile.owner == self.player_ship.player_id:
                continue
            if missile.contact == self.player_ship:
                self.player_ship.enemy_has_missile_solution = True

        missiles_to_remove = []
        for missile in self.missiles:
            missile.run(dt, self.asteroids)
            if missile.alive is False:
                missiles_to_remove.append(missile)

        for missile in missiles_to_remove:
            self.explosions.append(missile.rect.center)
            self.missiles.remove(missile)

    def fire_missile(self):
        missile = Missile(self.player_ship.pos_x, self.player_ship.pos_y, 0, 0, self.enemy_ship,
                          self.player_ship.player_id)
        self.missiles.append(missile)

    def draw_scene(self):
        self.draw_game.start_blit()

        if not self.player_ship.alive:
            self.draw_game.draw_signal_lost()
            end_blit()
            return

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
        self.draw_game.draw_missiles(self.missiles, camera_x, camera_y)
        self.draw_game.draw_explosions(self.explosions, camera_x, camera_y)
        self.draw_game.draw_asteroids(self.asteroids, camera_x, camera_y)
        self.draw_game.draw_drones(self.drones, camera_x, camera_y)
        self.draw_game.draw_ships(self.ships, camera_x, camera_y)

        self.explosions = []

        # UI elements and crt effect
        self.draw_ui.draw_ui_layout()
        self.draw_ui.draw_world_grid(camera_x, camera_y, self.grid_on)
        self.draw_ui.draw_manual_control_indicator(self.player_ship.manual_control)
        self.draw_ui.draw_ship_info(self.player_ship)
        self.draw_ui.draw_missile_lock_warning(self.player_ship.enemy_has_missile_solution)
        self.draw_ui.draw_missile_vectors(self.player_ship.player_id, self.missiles, camera_x, camera_y)
        self.draw_ui.draw_radar(self.player_ship, self.player_ship.unconfirmed_signatures, self.radar_system.scanning)
        self.draw_ui.draw_laser_targeting_info(self.target_type, self.player_ship.laser_on)
        self.draw_ui.draw_deep_field_panel(self.player_ship.deep_field_contacts, self.deep_field_scan.direction_index, self.player_ship.dfs_on)
        self.draw_ui.draw_tactical_map(self.is_map_open, self.player_ship, self.close_range_scan.get_contacts())

        # Context dependent
        if self.player_ship.dfs_on:
            self.draw_ui.draw_dfs_corridor(self.player_ship, self.deep_field_scan.direction_index, camera_x, camera_y)
        if self.player_ship.laser_on:
            self.draw_ui.draw_laser(self.laser_assessor, self.laser_endpoint, camera_x, camera_y)

        # End
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
