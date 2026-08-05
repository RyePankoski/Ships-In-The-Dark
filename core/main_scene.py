import random
import json

from objects.decoy import Decoy
from utility.constants import WORLD_HEIGHT, WORLD_WIDTH, GRID_SIZE
from utility.util import end_blit

from asset_handlers.draw_game import DrawGame
from asset_handlers.draw_ui import DrawUI

from ai.player_ship_ai import PlayerShipAI

from objects.asteroid import Asteroid
from objects.missile import Missile
from objects.pirate import Pirate
from objects.drone import Drone
from objects.ship import Ship

from instruments.close_range_scan import CloseRangeScan
from instruments.deep_field_scan import DeepFieldScan
from instruments.laser_assessor import LaserAssessor
from instruments.radar_system import RadarSystem


class MainScene:
    def __init__(self, connected, screen, audio_manager):
        # Classes
        self.player_ship_ai = PlayerShipAI()
        self.audio_manager = audio_manager
        self.draw_game = DrawGame(screen)
        self.draw_ui = DrawUI(screen)

        # Netcode stuff
        self.connected = connected
        self.my_player_id = None

        # Lists
        self.explosions = []
        self.missiles = []

        self.bullets = []
        self.decoys = []
        self.ships = []

        self.asteroids = {}
        self.pirates = {}
        self.drones = {}

        self.dict_objects = {}
        self.list_objects = {}

        # Create player ship and enemy ship
        if not self.connected:
            self.enemy_ship = Ship(random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT), is_player=False, is_ai=True)
            self.player_ship = Ship(random.randint(0, WORLD_WIDTH), random.randint(0, WORLD_HEIGHT), is_player=True, player_id=1)
            self.ships.append(self.player_ship)
            self.ships.append(self.enemy_ship)
            self.init_asteroids_and_drones()

        # Subsystems
        self.close_range_scan = CloseRangeScan(self.player_ship)
        self.deep_field_scan = DeepFieldScan(self.player_ship)
        self.laser_assessor = LaserAssessor(self.player_ship)
        self.radar_system = RadarSystem()

        self.laser_endpoint = (0, 0)
        self.unpainted_all = False
        self.laser_target_type = "Nothing"

        # UI stuff
        self.is_map_open = False
        self.end_tripped = False
        self.grid_on = True

        # input timer
        self.input_timer_cooldown = 0.2
        self.input_cooling_down = False
        self.input_timer = 0
        self.dfs_warning_cooldown = 3
        self.dfs_warning_timer = 0

        # Fun cinematic type stuff
        self.ftl_traveling = True
        self.ftl_travel_timer = 0
        self.ftl_travel_cooldown = 5

        self.ftl_arriving = False
        self.ftl_arrival_timer = 0
        self.ftl_arrival_cooldown = 2

        self.sys_analyzing = False
        self.sys_analyzing_timer = 0
        self.sys_analyzing_cooldown = 2

    def run(self, inputs, dt):
        # Handle end game scenario
        if not self.player_ship.alive:
            if not self.end_tripped:
                self.audio_manager.stop_all()
                self.audio_manager.play_sfx('death_screen')
                self.end_tripped = True
            self.draw_death()
            return

        # Let the server handle inputs and simulation
        if not self.connected:
            self.handle_inputs(inputs, dt)
            self.handle_alive_things(dt)

        if self.player_ship.close_range_scanning:
            self.close_range_scan.update(self.dict_objects, self.list_objects)

        self.timers(dt)
        self.handle_radar()
        self.handle_laser(inputs, dt)
        self.handle_general_sound_effects()
        self.build_object_dicts()
        self.draw_scene()
        self.explosions = []

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
            self.player_ship_ai.run(self.player_ship)

        if not self.input_cooling_down:
            if inputs['right_alt']:
                self.build_decoy()
                self.input_cooling_down = True
                self.audio_manager.play_sfx('deploy_decoy')

            if inputs['space'] and self.player_ship.laser_on:
                if self.laser_assessor.laser_locked:
                    self.audio_manager.play_sfx('laser_turn_off')
                    self.laser_assessor.laser_locked = False
                elif self.laser_assessor.current_target is not None:
                    self.audio_manager.play_sfx('laser_locked')
                    self.laser_assessor.laser_locked = True
                self.input_cooling_down = True
            if inputs['q']:
                self.player_ship.close_range_scanning = not self.player_ship.close_range_scanning
                self.audio_manager.play_sfx('close_range_toggle')
                self.input_cooling_down = True
            if inputs["p"] and self.player_ship.can_fire() and self.player_ship.has_missile_solution:
                self.player_ship.laser_on = False
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
                self.radar_system.begin_scan(self.player_ship, self.dict_objects, self.list_objects)
                self.input_cooling_down = True
            if inputs['i']:
                self.player_ship.laser_on = not self.player_ship.laser_on
                self.laser_assessor.laser_locked = False
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
                    self.player_ship.deep_field_contacts = self.deep_field_scan.run_scan(self.dict_objects, self.list_objects)
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

    def handle_laser(self, inputs, dt):
        if self.laser_assessor.laser_locked:
            self.player_ship.target = self.laser_assessor.current_target

        if self.player_ship.laser_on:
            self.laser_endpoint, self.laser_target_type = self.laser_assessor.shine_laser(self.dict_objects, self.list_objects)
            self.laser_assessor.change_direction(inputs, dt)
            self.unpainted_all = False
        elif not self.unpainted_all:
            self.unpaint_all()

    def handle_general_sound_effects(self):
        if self.player_ship.enemy_has_missile_solution:
            self.audio_manager.play_sfx('enemy_missile_lock')
        else:
            self.audio_manager.stop_sfx('enemy_missile_lock')
        if self.player_ship.painted:
            self.audio_manager.play_sfx('laser_warning')
        else:
            self.audio_manager.stop_sfx('laser_warning')
        if self.player_ship.dfs_scanned:
            self.audio_manager.play_sfx('dfs_scan_warning')
        else:
            self.audio_manager.stop_sfx('dfs_scan_warning')
        if self.laser_assessor.tracking_lost:
            self.audio_manager.play_sfx('laser_lock_lost')
            self.laser_assessor.tracking_lost = False
        if self.player_ship.pirate_sees_you:
            self.audio_manager.play_sfx('pirate_warning')
        else:
            self.audio_manager.stop_sfx('pirate_warning')
        if self.player_ship.health_low:
            self.audio_manager.play_sfx('low_health')
        else:
            self.audio_manager.stop_sfx('low_health')
        if self.ftl_traveling:
            self.audio_manager.play_sfx('ftl_jumping')
        else:
            self.audio_manager.stop_sfx('ftl_jumping')
        if self.ftl_arriving:
            self.audio_manager.play_sfx('ftl_arrival')
        else:
            self.audio_manager.stop_sfx('ftl_arrival')

    def build_object_dicts(self):
        self.dict_objects = {
            'asteroids': self.asteroids,
            'drones': self.drones,
            'pirates': self.pirates,
        }

        self.list_objects = {
            'ships': self.ships,
            'missiles': self.missiles,
            'decoys': self.decoys,
        }

    def handle_alive_things(self, dt):
        # Ships
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

        # Missiles
        if not self.missiles:
            self.player_ship.enemy_has_missile_solution = False

        for missile in self.missiles:
            if missile.owner == self.player_ship.player_id:
                continue
            if missile.contact == self.player_ship:
                self.player_ship.enemy_has_missile_solution = True
                distance = (missile.pos_x - self.player_ship.rect.center[0]) ** 2 + (missile.pos_y - self.player_ship.rect.center[1]) ** 2
                if distance < 1000 ** 2:
                    self.player_ship.catastrophic_warning = True
                    self.audio_manager.play_sfx('catastrophic_warning')
                else:
                    self.player_ship.catastrophic_warning = False

        missiles_to_remove = []
        for missile in self.missiles:
            missile.run(dt, self.asteroids)
            if missile.alive is False:
                missiles_to_remove.append(missile)

        for missile in missiles_to_remove:
            self.explosions.append((missile.pos_x, missile.pos_y))
            self.missiles.remove(missile)

        # Decoys
        decoys_to_remove = []
        for decoy in self.decoys:
            decoy.run(dt)
            if decoy.alive is False:
                decoys_to_remove.append(decoy)

        for decoy in decoys_to_remove:
            self.decoys.remove(decoy)

        # Drones
        drones_to_remove = []
        for cell in list(self.drones.keys()):
            for drone in list(self.drones[cell]):
                drone.run_drone(self.asteroids, dt)

                if drone.alive is False:
                    drones_to_remove.append(drone)

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

        for drone in drones_to_remove:
            self.drones[drone.cell].remove(drone)
            if not self.drones[drone.cell]:
                del self.drones[drone.cell]

        # Pirates
        for cell in list(self.pirates.keys()):
            for pirate in list(self.pirates[cell]):
                pirate.run(self.ships, self.bullets, dt)

                new_cell = (int(pirate.pos_x // GRID_SIZE), int(pirate.pos_y // GRID_SIZE))
                if new_cell != cell:
                    # Remove from old cell
                    self.pirates[cell].remove(pirate)
                    if not self.pirates[cell]:
                        del self.pirates[cell]

                    if new_cell not in self.pirates:
                        self.pirates[new_cell] = []
                    self.pirates[new_cell].append(pirate)

        bullets_to_remove = []
        for bullet in self.bullets:
            bullet.run(dt)

            for ship in self.ships:
                distance = (bullet.pos_x - ship.rect.center[0]) ** 2 + (bullet.pos_y - ship.rect.center[1]) ** 2
                if distance < 25 ** 2:
                    ship.health -= 2
                    ship.took_damage = True
                    self.audio_manager.play_sfx('damage_taken')

            if bullet.alive is False:
                bullets_to_remove.append(bullet)

        for bullet in bullets_to_remove:
            self.bullets.remove(bullet)

    def build_decoy(self):
        dx = random.randint(-1, 1)
        dy = random.randint(-1, 1)
        v = random.randint(20, 25)
        decoy = Decoy(self.player_ship.rect.center[0], self.player_ship.rect.center[1], dx, dy, v)
        self.decoys.append(decoy)

    def timers(self, dt):
        if self.input_cooling_down:
            self.input_timer += dt
            if self.input_timer > self.input_timer_cooldown:
                self.input_timer = 0
                self.input_cooling_down = False
        if self.player_ship.dfs_scanned:
            self.dfs_warning_timer += dt
            if self.dfs_warning_timer > self.dfs_warning_cooldown:
                self.player_ship.dfs_scanned = False
                self.dfs_warning_timer = 0

        if self.ftl_traveling:
            self.ftl_travel_timer += dt
            if self.ftl_travel_timer > self.ftl_travel_cooldown:
                self.ftl_traveling = False
                self.ftl_arriving = True

        if self.ftl_arriving:
            self.ftl_arrival_timer += dt
            if self.ftl_arrival_timer > self.ftl_arrival_cooldown:
                self.ftl_arriving = False
                self.sys_analyzing = True

        if self.sys_analyzing:
            self.sys_analyzing_timer += dt
            if self.sys_analyzing_timer > self.sys_analyzing_cooldown:
                self.sys_analyzing = False

    def fire_missile(self):
        missile = Missile(self.player_ship.rect.center[0], self.player_ship.rect.center[1], 0, 0, self.player_ship.target, self.player_ship.player_id)
        self.missiles.append(missile)

    def draw_death(self):
        self.draw_game.start_blit()
        self.draw_game.draw_end_game()
        end_blit()

    def draw_scene(self):
        self.draw_game.start_blit()
        camera_x, camera_y = self.find_camera()

        if self.ftl_traveling:
            self.draw_game.draw_ftl_jump_tunnel(self.ftl_traveling)
        else:
            self.draw_game.draw_stars(camera_x, camera_y)
            self.draw_game.draw_asteroids(self.asteroids, camera_x, camera_y)

        if self.ftl_arriving:
            self.draw_game.draw_ship_arrival((self.player_ship.rect.center[0], self.player_ship.rect.center[1]), self.ftl_arrival_timer, camera_x, camera_y, self.ftl_arrival_cooldown)

        if self.sys_analyzing:
            self.draw_game.draw_ship_analysis((self.player_ship.rect.center[0], self.player_ship.rect.center[1]), self.sys_analyzing_timer, camera_x, camera_y, self.sys_analyzing_cooldown)


        self.draw_game.draw_ships(self.ships, camera_x, camera_y)
        self.draw_game.draw_missiles(self.missiles, camera_x, camera_y)
        self.draw_game.draw_explosions(self.explosions, camera_x, camera_y)

        self.draw_game.draw_drones(self.drones, camera_x, camera_y)
        self.draw_game.draw_ships(self.ships, camera_x, camera_y)
        self.draw_game.draw_pirates(self.pirates, camera_x, camera_y)
        self.draw_game.draw_decoys(self.decoys, camera_x, camera_y)
        self.draw_game.draw_bullets(self.bullets, camera_x, camera_y)

        self.draw_ui.draw_ui_layout()
        self.draw_ui.draw_world_grid(camera_x, camera_y, self.grid_on)
        self.draw_ui.draw_laser_painted_warning(self.player_ship.painted)
        self.draw_ui.draw_ship_info(self.player_ship)
        self.draw_ui.draw_missile_lock_warning(self.player_ship.enemy_has_missile_solution)
        self.draw_ui.draw_missile_vectors(self.player_ship.player_id, self.missiles, camera_x, camera_y)
        self.draw_ui.draw_radar(self.player_ship, self.player_ship.unconfirmed_signatures, self.radar_system.scanning)
        self.draw_ui.draw_laser_targeting_info(self.laser_target_type, self.laser_assessor, self.player_ship.laser_on)
        self.draw_ui.draw_deep_field_panel(self.player_ship.deep_field_contacts, self.deep_field_scan.direction_index, self.player_ship.dfs_on)
        self.draw_ui.draw_catastrophe_warning(self.player_ship.catastrophic_warning)
        self.draw_ui.draw_dfs_warning(self.player_ship.dfs_scanned, self.dfs_warning_timer)
        self.draw_ui.draw_dfs_corridor(self.player_ship, self.deep_field_scan.direction_index, camera_x, camera_y, self.player_ship.dfs_on)
        self.draw_ui.draw_laser(self.laser_assessor, self.laser_endpoint, camera_x, camera_y, self.player_ship.laser_on)
        self.draw_ui.draw_tactical_map(self.is_map_open, self.player_ship, self.close_range_scan.get_contacts())
        self.draw_ui.draw_pirate_fire_warning(self.player_ship.pirate_sees_you)
        self.draw_ui.draw_bullet_damage_glitch(self.player_ship.took_damage)
        self.draw_ui.draw_low_health_warning(self.player_ship.health_low)
        self.draw_ui.draw_scanlines()

        end_blit()

    def unpaint_all(self):
        for cell in self.asteroids.values():
            for asteroid in cell:
                asteroid.painted = False
        for cell in self.drones.values():
            for drone in cell:
                drone.is_painted = False
        for ship in self.ships:
            ship.painted = False

        self.unpainted_all = True

    def find_camera(self):
        player_ship = next((ship for ship in self.ships if ship.player), None)

        if player_ship:
            camera_x = player_ship.rect.center[0] - self.draw_game.screen.get_width() / 2
            camera_y = player_ship.rect.center[1] - self.draw_game.screen.get_height() / 2
        else:
            camera_x = 0
            camera_y = 0

        return camera_x, camera_y

    def init_asteroids_and_drones(self):
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

            drone = Drone(pos_x, pos_y)
            self.drones[cell].append(drone)

        for i in range(1):
            # pos_x = random.randint(0, WORLD_WIDTH)
            # pos_y = random.randint(0, WORLD_HEIGHT)
            pos_x = 100
            pos_y = 100

            grid_x = int(pos_x // GRID_SIZE)
            grid_y = int(pos_y // GRID_SIZE)
            cell = (grid_x, grid_y)

            if cell not in self.pirates:
                self.pirates[cell] = []

            pirate = Pirate(pos_x, pos_y, v=40)
            self.pirates[cell].append(pirate)

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
