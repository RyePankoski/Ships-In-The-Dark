import pygame

from ai.player_ship_ai import PlayerShipAI
from asset_handlers.draw_game import DrawGame
from asset_handlers.draw_ui import DrawUI
from core.cockpit import Cockpit
from instruments.close_range_scan import CloseRangeScan
from instruments.deep_field_scan import DeepFieldScan
from instruments.laser_assessor import LaserAssessor
from instruments.radar_system import RadarSystem
from simulation.world import MOVE_KEYS, empty_command
from utility.util import *


class MainScene:
    """One player's view of a World: instruments, UI, camera and sound.

    local=True:  single-player. This scene owns the World and steps it.
    local=False: multiplayer. The World is a copy kept up to date by the client
                 from server snapshots; this scene only reads it and produces
                 `self.command` for the client to send to the server.
    The scene never moves world objects itself; it asks via a command.
    """

    def __init__(self, screen, audio_manager, world, my_id, local=True):
        # Classes
        self.player_ship_ai = PlayerShipAI()
        self.audio_manager = audio_manager
        self.draw_game = DrawGame(screen)
        self.draw_ui = DrawUI(screen)

        # World + who we are in it
        self.world = world
        self.my_id = my_id
        self.local = local
        self.player_ship = world.get_ship(my_id)
        self.player_ship.player = True
        self.cockpit = Cockpit()

        # What we asked the world to do this frame (the client sends it in multiplayer)
        self.command = empty_command()
        self.pending_actions = []
        self.laser_hit_id = None

        # Purely visual
        self.explosions = []
        self.previous_missiles = {}
        self.p_field = {}
        self.init_p_field()

        self.dict_objects = {}
        self.list_objects = {}

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
        self.p_field_open = False
        self.esc_screen = False
        self.control_screen = False

        # input timer
        self.input_timer_cooldown = 0.2
        self.input_cooling_down = False
        self.input_timer = 0
        self.dfs_warning_cooldown = 3
        self.dfs_warning_timer = 0

        # Control
        self.lock_inputs = False
        self.quit_requested = False  # set by QUIT TO MENU; the client acts on it
        self._command_actions = []   # this frame's command['actions'], for perform()

        # Fun cinematic type stuff
        self.ftl_traveling = True
        self.ftl_travel_timer = 0
        self.ftl_travel_cooldown = 5

        self.ftl_arriving = False
        self.ftl_arrival_timer = 0
        self.ftl_arrival_cooldown = 2

        self.blink_arriving = False
        self.blink_arrival_timer = 0
        self.blink_arrival_cooldown = 2

        self.sys_analyzing = False
        self.sys_analyzing_timer = 0
        self.sys_analyzing_cooldown = 2

        self.blinking = False
        self.blinking_timer = 0
        self.blinking_cooldown = 3
        self.has_blinked = False

        self.asteroid_laser_on = True
        self.asteroid_laser_timer = 0
        self.asteroid_laser_cooldown = 4

        # Counts down from missile_contact_duration after any missile hit
        self.missile_contact_timer = 0
        self.missile_contact_duration = 1.5

    @property
    def enemy_ships(self):
        return [ship for ship in self.world.ships if ship is not self.player_ship]

    def run(self, inputs, dt, events=()):
        # Buttons drawn last frame are what this frame's clicks land on
        buttons = self.draw_ui.buttons
        clicks = buttons.clicked_actions(events)
        held = buttons.held_action()
        if held:
            inputs = dict(inputs)
            inputs[held] = True

        if not self.player_ship.alive:
            self.end_screen("SIGNAL LOST", "SYNCHRONIZATION LOST. DEBUG:42*1a2", 'death_screen', clicks)
            return

        # In single-player the AI enemy dying is not the end of the game (yet).
        if not self.local and self.enemy_ships and not any(ship.alive for ship in self.enemy_ships):
            self.end_screen("TARGET DESTROYED", "HOSTILE SIGNAL TERMINATED", 'retro_beep', clicks)
            return

        self.build_object_dicts()

        self.command = self.handle_inputs(inputs, dt, clicks)
        if self.local:
            self.world.step({self.my_id: self.command}, dt)
            self.handle_world_events(self.world.events)

        for ship in self.world.ships:
            ship.player = ship is self.player_ship

        self.update_threats()
        self.track_explosions()

        if self.cockpit.close_range_scanning:
            self.close_range_scan.update(self.dict_objects, self.list_objects)

        self.timers(dt)

        self.handle_radar()
        self.handle_p_field(dt)
        self.handle_laser_assessor(inputs, dt)

        self.handle_general_sound_effects()
        self.draw_scene()

        self.explosions = []

    def handle_p_field(self, dt):
        for cell in self.p_field.values():
            if len(cell) == 0:
                continue

            entries_to_remove = []
            for i, entry in enumerate(cell):
                strength = entry[0] - dt
                if strength <= 0:
                    entries_to_remove.append(entry)
                    continue
                cell[i] = [strength, entry[1], entry[2]]

            for entry in entries_to_remove:
                cell.remove(entry)

    # Key -> action, in the order they're checked. Console buttons produce the
    # same action names (see asset_handlers/buttons.py), so a click and a key
    # press both go through perform().
    KEY_ACTIONS = (
        ('right_alt', 'decoy'),
        ('q', 'toggle_prox_scan'),
        ('p', 'fire_missile'),
        ('l', 'toggle_autopilot'),
        ('x', 'debug_enemy_fire'),
        ('r', 'radar_sweep'),
        ('i', 'toggle_laser'),
        ('k', 'toggle_dfs'),
        ('m', 'toggle_map'),
        ('t', 'blink'),
        ('esc', 'escape'),
        ('n', 'toggle_p_field'),
        ('o', 'dfs_scan'),
        ('arrow_key_up', 'dfs_bearing_cw'),
        ('arrow_key_down', 'dfs_bearing_ccw'),
        ('space', 'laser_lock'),
    )
    # While the operator console is up, these keys mean something else
    CONSOLE_KEY_ACTIONS = {'q': 'quit_to_menu', 'c': 'open_controls'}

    def handle_inputs(self, inputs, dt, clicks=()):
        """Turn this frame's keys and clicks into cockpit changes + a command for the world."""
        command = empty_command()
        command['actions'] = self.pending_actions
        command['laser_target'] = self.laser_hit_id
        self.pending_actions = []
        self._command_actions = command['actions']

        if self.lock_inputs:
            return command

        cockpit = self.cockpit

        if cockpit.laser_on:
            if inputs['arrow_key_left'] or inputs['arrow_key_right']:
                self.audio_manager.play_sfx('laser_dir_change')
            else:
                self.audio_manager.stop_sfx('laser_dir_change')

        if cockpit.manual_control:
            if inputs['up'] or inputs['left'] or inputs['down'] or inputs['right']:
                self.audio_manager.play_sfx('thrust')
                update_p_field(self.player_ship, self.p_field, 1, 'movement')
            else:
                self.audio_manager.stop_sfx('thrust')

        if cockpit.manual_control:
            command['move'] = {key: bool(inputs[key]) for key in MOVE_KEYS}
        elif self.local:
            self.player_ship_ai.run(self.player_ship)

        # Held keys repeat every frame, so they wait out the cooldown. A click
        # is a single press and always goes through.
        actions = []
        keys_live = not self.input_cooling_down
        if keys_live:
            if self.esc_screen:
                actions += [action for key, action in self.CONSOLE_KEY_ACTIONS.items() if inputs[key]]
            for key, action in self.KEY_ACTIONS:
                if inputs[key] and not (self.esc_screen and key in self.CONSOLE_KEY_ACTIONS):
                    actions.append(action)
        actions += clicks

        for action in actions:
            self.perform(action)

        # The bearing-change sound is cut once the bearing stops changing
        if keys_live and cockpit.dfs_on and not any(a.startswith('dfs_bearing') for a in actions):
            self.audio_manager.stop_sfx('dfs_dir_change')

        return command

    def perform(self, action):
        """Do one cockpit action, whether it came from a key or a button."""
        cockpit = self.cockpit
        sfx = self.audio_manager.play_sfx

        if action == 'decoy':
            self._command_actions.append({'type': 'decoy'})
            self.input_cooling_down = True
            sfx('deploy_decoy')
        elif action == 'toggle_prox_scan':
            cockpit.close_range_scanning = not cockpit.close_range_scanning
            sfx('close_range_toggle')
            self.input_cooling_down = True
        elif action == 'fire_missile':
            target_id = getattr(cockpit.target, 'net_id', None)
            if self.player_ship.can_fire() and target_id is not None:
                cockpit.laser_on = False
                self._command_actions.append({'type': 'fire', 'target': target_id})
                self.input_cooling_down = True
                sfx('fire_missile')
                update_p_field(self.player_ship, self.p_field, 20, 'movement')
        # Autopilot and the debug "enemy fires at me" key only exist in single-player
        elif action == 'toggle_autopilot':
            if self.local:
                cockpit.manual_control = not cockpit.manual_control
                sfx('retro_beep')
                self.input_cooling_down = True
        elif action == 'debug_enemy_fire':
            if self.local and self.enemy_ships:
                enemy = self.enemy_ships[0]
                enemy.fire()
                self.world.fire_missile(enemy, self.player_ship)
                self.input_cooling_down = True
        elif action == 'radar_sweep':
            sfx('radar')
            cockpit.unconfirmed_signatures = []
            self.radar_system.begin_scan(self.player_ship, self.dict_objects, self.list_objects)
            self.input_cooling_down = True
            update_p_field(self.player_ship, self.p_field, 5, 'movement')
        elif action == 'toggle_laser':
            cockpit.laser_on = not cockpit.laser_on
            self.laser_assessor.laser_locked = False
            self.laser_assessor.set_direction(self.player_ship.heading)
            sfx('laser')
            self.input_cooling_down = True
        elif action == 'toggle_dfs':
            cockpit.dfs_on = not cockpit.dfs_on
            sfx('dfs_toggle')
            self.input_cooling_down = True
            cockpit.deep_field_contacts = []
        elif action == 'toggle_map':
            self.is_map_open = not self.is_map_open
            self.input_cooling_down = True
            sfx('map_open' if self.is_map_open else 'map_close')
        elif action == 'blink':
            if not self.blinking:
                self.blinking = True
                sfx('blink')
                update_p_field(self.player_ship, self.p_field, 40, 'movement')
        elif action == 'escape':
            if self.control_screen:
                self.control_screen = False

            if self.esc_screen:
                self.esc_screen = False
            elif self.is_map_open is False and self.p_field_open is False:
                self.esc_screen = True

            if self.is_map_open:
                self.is_map_open = False
            if self.p_field_open:
                self.p_field_open = False

            self.input_cooling_down = True
        elif action == 'toggle_p_field':
            sfx('p_field_close' if self.p_field_open else 'p_field_open')
            self.input_cooling_down = True
            self.p_field_open = not self.p_field_open
            if self.is_map_open:
                self.is_map_open = False
        elif action == 'dfs_scan':
            if cockpit.dfs_on:
                cockpit.deep_field_contacts = self.deep_field_scan.run_scan(self.dict_objects, self.list_objects)
                sfx('dfs_scan')
                self.input_cooling_down = True
                update_p_field(self.player_ship, self.p_field, 8, 'movement')
        elif action in ('dfs_bearing_cw', 'dfs_bearing_ccw'):
            if cockpit.dfs_on:
                step = 1 if action == 'dfs_bearing_cw' else -1
                self.deep_field_scan.direction_index = (self.deep_field_scan.direction_index + step) % 8
                sfx('dfs_dir_change')
                cockpit.deep_field_contacts = []
                self.input_cooling_down = True
        elif action == 'laser_lock':
            if cockpit.laser_on:
                self.input_cooling_down = True
                if self.laser_assessor.laser_locked:
                    sfx('laser_turn_off')
                    self.laser_assessor.laser_locked = False
                elif self.laser_assessor.current_target is not None:
                    sfx('laser_locked')
                    self.laser_assessor.laser_locked = True
        # Operator console
        elif action == 'open_console':
            self.esc_screen = True
            self.input_cooling_down = True
        elif action == 'open_controls':
            self.control_screen = True
            self.input_cooling_down = True
        elif action == 'close_controls':
            self.control_screen = False
            self.input_cooling_down = True
        elif action in ('quit_to_menu', 'return_to_menu'):
            self.quit_requested = True

    def update_threats(self):
        """Work out the missile warnings from the missiles in the world."""
        cockpit = self.cockpit
        cockpit.enemy_has_missile_solution = False
        cockpit.catastrophic_warning = False

        for missile in self.world.missiles:
            if missile.owner == self.my_id or missile.contact is not self.player_ship:
                continue
            cockpit.enemy_has_missile_solution = True
            distance, in_range = squared_distance(self.player_ship.rect.center, (missile.pos_x, missile.pos_y), 800)
            if in_range:
                cockpit.catastrophic_warning = True

        if cockpit.catastrophic_warning:
            self.audio_manager.play_sfx('catastrophic_warning')

    def track_explosions(self):
        """A missile that was there last frame and isn't now has exploded."""
        current = {missile.net_id: (missile.pos_x, missile.pos_y) for missile in self.world.missiles}
        for missile_id, position in self.previous_missiles.items():
            if missile_id not in current:
                self.explosions.append(position)
        self.previous_missiles = current

    def handle_radar(self):
        if self.radar_system.scanning:
            self.cockpit.unconfirmed_signatures.extend(self.radar_system.continue_scan())

    def handle_laser_assessor(self, inputs, dt):
        cockpit = self.cockpit
        if self.laser_assessor.laser_locked:
            cockpit.target = self.laser_assessor.current_target
        cockpit.has_missile_solution = self.laser_assessor.laser_locked and cockpit.target is not None

        if cockpit.laser_on:
            self.laser_endpoint, self.laser_target_type = self.laser_assessor.shine_laser(self.dict_objects, self.list_objects)
            self.laser_assessor.change_direction(inputs, dt)
            self.unpainted_all = False
        elif not self.unpainted_all:
            self.unpaint_all()

        # Tell the world what our laser is touching, so the other player gets painted
        touching = cockpit.laser_on and self.laser_target_type != "NOTHING"
        self.laser_hit_id = getattr(self.laser_assessor.current_target, 'net_id', None) if touching else None

    def handle_general_sound_effects(self):
        if self.cockpit.enemy_has_missile_solution:
            self.audio_manager.play_sfx('enemy_missile_lock')
        else:
            self.audio_manager.stop_sfx('enemy_missile_lock')
        if self.player_ship.painted:
            self.audio_manager.play_sfx('laser_warning')
        else:
            self.audio_manager.stop_sfx('laser_warning')
        if self.cockpit.dfs_scanned:
            self.audio_manager.play_sfx('dfs_scan_warning')
        else:
            self.audio_manager.stop_sfx('dfs_scan_warning')
        if self.laser_assessor.tracking_lost:
            self.audio_manager.play_sfx('laser_lock_lost')
            self.laser_assessor.tracking_lost = False
        if self.player_ship.mining_vessel_sees_you:
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

        if self.blink_arriving:
            self.audio_manager.play_sfx('blink_arrival')
        else:
            self.audio_manager.stop_sfx('blink_arrival')

    def build_object_dicts(self):
        self.dict_objects = {
            'asteroids': self.world.asteroids,
            'drones': self.world.drones,
            'pirates': self.world.pirates,
        }

        self.list_objects = {
            'ships': self.world.ships,
            'missiles': self.world.missiles,
            'decoys': self.world.decoys,
        }

    def handle_world_events(self, events):
        """React (sound/UI) to things the world reported.

        Single-player: straight from world.events after each step.
        Multiplayer: relayed from the server by the client (see NetClient.take_events).
        """
        for kind, *data in events:
            if kind == 'damage':
                if data[0] == self.my_id:
                    self.audio_manager.play_sfx('damage_taken')
            elif kind == 'missile_contact':
                self.audio_manager.play_sfx('missile_contact', force=True)
                self.missile_contact_timer = self.missile_contact_duration

    def timers(self, dt):
        if self.missile_contact_timer > 0:
            self.missile_contact_timer = max(0, self.missile_contact_timer - dt)

        if self.input_cooling_down:
            self.input_timer += dt
            if self.input_timer > self.input_timer_cooldown:
                self.input_timer = 0
                self.input_cooling_down = False

        if self.cockpit.dfs_scanned:
            self.dfs_warning_timer += dt
            if self.dfs_warning_timer > self.dfs_warning_cooldown:
                self.cockpit.dfs_scanned = False
                self.dfs_warning_timer = 0

        if self.ftl_traveling:
            self.lock_inputs = True
            self.ftl_travel_timer += dt
            if self.ftl_travel_timer > self.ftl_travel_cooldown:
                self.ftl_traveling = False
                self.ftl_arriving = True
                self.lock_inputs = False

        if self.ftl_arriving:
            self.ftl_arrival_timer += dt
            if self.ftl_arrival_timer > self.ftl_arrival_cooldown:
                self.ftl_arriving = False
                self.ftl_arrival_timer = 0

        if self.blinking:
            self.blinking_timer += dt
            if self.blinking_timer > self.blinking_cooldown:
                self.blinking = False
                self.blink_arriving = True
                self.blinking_timer = 0
                # The world does the actual jump (on the server, in multiplayer)
                self.pending_actions.append({'type': 'blink'})

        if self.blink_arriving:
            self.blink_arrival_timer += dt
            if self.blink_arrival_timer > self.blink_arrival_cooldown:
                self.blink_arriving = False
                self.blink_arrival_timer = 0

        if self.sys_analyzing:
            self.sys_analyzing_timer += dt
            if self.sys_analyzing_timer > self.sys_analyzing_cooldown:
                self.sys_analyzing = False
                self.sys_analyzing_timer = 0

        if self.asteroid_laser_on:
            self.asteroid_laser_timer += dt
            if self.asteroid_laser_timer > self.asteroid_laser_cooldown:
                self.asteroid_laser_on = False
                self.asteroid_laser_timer = 0

    def end_screen(self, message, subtitle, sound, clicks=()):
        if 'return_to_menu' in clicks:
            self.quit_requested = True
        self.draw_game.start_blit()
        self.draw_game.draw_end_game(message, subtitle)
        self.draw_ui.buttons.begin_frame()
        self.draw_ui.draw_end_screen_button()
        self.draw_ui.buttons.end_frame()
        end_blit()
        if not self.end_tripped:
            self.audio_manager.stop_all()
            self.audio_manager.play_sfx(sound)
            self.end_tripped = True

    def draw_scene(self):
        world = self.world
        cockpit = self.cockpit

        self.draw_game.start_blit()
        self.draw_ui.buttons.begin_frame()

        camera_x, camera_y = self.find_camera()

        if self.ftl_traveling:
            self.draw_game.draw_ftl_jump_tunnel(self.ftl_traveling)
        else:
            self.draw_game.draw_stars(camera_x, camera_y)
            self.draw_game.draw_asteroids(world.asteroids, camera_x, camera_y)
            self.draw_game.draw_ships(world.ships, camera_x, camera_y)
            self.draw_game.draw_drones(world.drones, camera_x, camera_y)
            self.draw_game.draw_pirates(world.pirates, camera_x, camera_y)
            self.draw_game.draw_decoys(world.decoys, camera_x, camera_y)
            self.draw_game.draw_bullets(world.bullets, camera_x, camera_y)
            self.draw_game.draw_missiles(world.missiles, camera_x, camera_y)
            self.draw_game.draw_explosions(self.explosions, camera_x, camera_y)

        self.draw_game.draw_laser(world.lasers, (camera_x, camera_y))

        if self.ftl_arriving:
            self.draw_game.draw_ftl_arrival(self.player_ship.rect.center, self.ftl_arrival_timer, camera_x, camera_y, self.ftl_arrival_cooldown)
        if self.sys_analyzing:
            self.draw_game.draw_ship_analysis((self.player_ship.rect.center[0], self.player_ship.rect.center[1]), self.sys_analyzing_timer, camera_x, camera_y, self.sys_analyzing_cooldown)
        if self.blinking:
            self.draw_game.draw_charge_animation(self.blinking, self.blinking_timer, 2)
        if self.blink_arriving:
            self.draw_game.draw_blink_arrival((self.player_ship.rect.center[0], self.player_ship.rect.center[1]), self.blink_arrival_timer, camera_x, camera_y, self.ftl_arrival_cooldown)

        self.draw_ui.draw_world_grid(camera_x, camera_y, self.grid_on)
        self.draw_ui.draw_ui_layout()
        self.draw_ui.draw_laser_painted_warning(self.player_ship.painted)
        self.draw_ui.draw_ship_info(self.player_ship, cockpit)
        self.draw_ui.draw_control_banks(self.player_ship, cockpit, local=self.local,
                                        map_open=self.is_map_open, p_field_open=self.p_field_open,
                                        blink_busy=self.blinking or self.blink_arriving)
        self.draw_ui.draw_missile_lock_warning(cockpit.enemy_has_missile_solution)
        self.draw_ui.draw_missile_vectors(self.my_id, world.missiles, camera_x, camera_y)
        self.draw_ui.draw_radar(self.player_ship, cockpit.unconfirmed_signatures, self.radar_system.scanning)
        self.draw_ui.draw_laser_targeting_info(self.laser_target_type, self.laser_assessor, cockpit.laser_on)
        self.draw_ui.draw_deep_field_panel(cockpit.deep_field_contacts, self.deep_field_scan.direction_index, cockpit.dfs_on)
        self.draw_ui.draw_catastrophe_warning(cockpit.catastrophic_warning)
        self.draw_ui.draw_dfs_warning(cockpit.dfs_scanned, self.dfs_warning_timer)
        self.draw_ui.draw_missile_contact(self.missile_contact_timer, self.missile_contact_duration)
        self.draw_ui.draw_dfs_corridor(self.player_ship, self.deep_field_scan.direction_index, camera_x, camera_y, cockpit.dfs_on)
        self.draw_ui.draw_laser(self.laser_assessor, self.laser_endpoint, camera_x, camera_y, cockpit.laser_on)
        self.draw_ui.draw_radar_controls(self.radar_system.scanning)
        self.draw_ui.draw_tactical_map(self.is_map_open, self.player_ship, self.close_range_scan.get_contacts())
        self.draw_ui.draw_corpo_miner_fire_warning(self.player_ship.mining_vessel_sees_you)
        self.draw_ui.draw_bullet_damage_glitch(self.player_ship.took_damage)
        self.draw_ui.draw_low_health_warning(self.player_ship.health_low)
        self.draw_ui.draw_p_field_scanner(self.p_field, self.player_ship.rect.center[0], self.player_ship.rect.center[1], self.p_field_open)

        # Last, so the console sits on top of everything else
        self.draw_ui.draw_pause_screen(self.esc_screen)
        self.draw_ui.draw_controls_screen(self.control_screen)

        self.draw_ui.buttons.end_frame()
        end_blit()

    def unpaint_all(self):
        # Visual "my laser is on it" flags only. Our own ship's `painted` comes
        # from the world (someone else's laser), so leave it alone.
        for cell in self.world.asteroids.values():
            for asteroid in cell:
                asteroid.painted = False
        for cell in self.world.drones.values():
            for drone in cell:
                drone.is_painted = False
        for ship in self.world.ships:
            if ship is not self.player_ship:
                ship.painted = False

        self.unpainted_all = True

    def find_camera(self):
        camera_x = self.player_ship.rect.center[0] - self.draw_game.screen.get_width() / 2
        camera_y = self.player_ship.rect.center[1] - self.draw_game.screen.get_height() / 2
        return camera_x, camera_y

    def init_p_field(self):
        i = WORLD_WIDTH // GRID_SIZE
        j = WORLD_HEIGHT // GRID_SIZE
        for x in range(i):
            for z in range(j):
                cell = (x, z)
                self.p_field[cell] = []
