import pygame

from ai.player_ship_ai import PlayerShipAI
from asset_handlers.draw_game import DrawGame
from asset_handlers.draw_ui import DrawUI
from core.cockpit import Cockpit
from instruments.close_range_scan import CloseRangeScan
from instruments.deep_field_scan import DeepFieldScan
from instruments.instrument import InstrumentContext
from instruments.laser_assessor import LaserAssessor
from instruments.radar_system import RadarSystem
from instruments.radio_receiver import RadioReceiver
from radio.signal import RADAR_SWEEP
from simulation.world import MOVE_KEYS, empty_command
from utility.constants import RADAR_SWEEP_POWER
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

        # Purely visual
        self.explosions = []
        self.previous_missiles = {}

        # Instruments: add a new sensor or system by adding it to this list
        # (see instruments/instrument.py). The order is the order they draw in.
        self.instrument_context = InstrumentContext(
            self.player_ship, world.contacts, self.cockpit, audio_manager,
            start_cooldown=self.start_input_cooldown, world=world,
            send_action=lambda action: self._command_actions.append(action),
        )
        self.radar_system = RadarSystem(self.instrument_context)
        self.deep_field_scan = DeepFieldScan(self.instrument_context)
        self.laser_assessor = LaserAssessor(self.instrument_context)
        self.close_range_scan = CloseRangeScan(self.instrument_context)
        self.radio_receiver = RadioReceiver(self.instrument_context, my_id)
        self.instruments = [self.radar_system, self.deep_field_scan, self.laser_assessor, self.close_range_scan,
                            self.radio_receiver]

        self.key_actions = self.KEY_ACTIONS + tuple(k for i in self.instruments for k in i.keys)
        self.instrument_actions = {}
        for instrument in self.instruments:
            for name, handler in instrument.actions().items():
                assert name not in self.instrument_actions, f"two instruments answer to {name!r}"
                self.instrument_actions[name] = handler

        # UI stuff
        self.is_map_open = False
        # Tactical-map markers: (shape, world_x, world_y). Local to this client,
        # never sent to the server. marker_mode: None, 'PICK' (choosing a shape)
        # or a shape name (next map click places it).
        self.map_markers = []
        self.marker_mode = None
        self.end_tripped = False
        self.grid_on = True
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
        self.ftl_traveling = False
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

        self.command = self.handle_inputs(inputs, dt, clicks)
        if self.local:
            self.world.step({self.my_id: self.command}, dt)
            self.handle_world_events(self.world.events)

        for ship in self.world.ships:
            ship.player = ship is self.player_ship

        self.update_threats()
        self.track_explosions()

        self.timers(dt)

        for instrument in self.instruments:
            instrument.update(dt, inputs)

        self.handle_general_sound_effects()
        self.draw_scene()

        self.explosions = []

    def start_input_cooldown(self):
        self.input_cooling_down = True

    # Key -> action, in the order they're checked. Console buttons produce the
    # same action names (see asset_handlers/buttons.py), so a click and a key
    # press both go through perform().
    # The instruments add their own keys to this (see Instrument.keys).
    KEY_ACTIONS = (
        ('right_alt', 'decoy'),
        ('p', 'fire_missile'),
        ('l', 'toggle_autopilot'),
        ('x', 'debug_enemy_fire'),
        ('m', 'toggle_map'),
        ('t', 'blink'),
        ('esc', 'escape'),
    )
    # While the operator console is up, these keys mean something else
    CONSOLE_KEY_ACTIONS ={'q': 'quit_to_menu', 'c': 'open_controls'}

    def handle_inputs(self, inputs, dt, clicks=()):
        """Turn this frame's keys and clicks into cockpit changes + a command for the world."""
        command = empty_command()
        command['actions'] = self.pending_actions
        command['laser_target'] = self.laser_assessor.hit_id
        self.pending_actions = []
        self._command_actions = command['actions']

        if self.lock_inputs:
            return command

        cockpit = self.cockpit

        if cockpit.manual_control:
            if inputs['up'] or inputs['left'] or inputs['down'] or inputs['right']:
                self.audio_manager.play_sfx('thrust')
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
        self.instrument_context.keys_live = keys_live
        if keys_live:
            if self.esc_screen:
                actions += [action for key, action in self.CONSOLE_KEY_ACTIONS.items() if inputs[key]]
            for key, action in self.key_actions:
                if inputs[key] and not (self.esc_screen and key in self.CONSOLE_KEY_ACTIONS):
                    actions.append(action)
        actions += clicks

        for action in actions:
            self.perform(action)

        return command

    def perform(self, action):
        """Do one cockpit action, whether it came from a key or a button."""
        cockpit = self.cockpit
        sfx = self.audio_manager.play_sfx

        instrument_action = self.instrument_actions.get(action)
        if instrument_action is not None:
            instrument_action()
        elif action == 'decoy':
            self._command_actions.append({'type': 'decoy'})
            self.input_cooling_down = True
            sfx('deploy_decoy')
        elif action == 'fire_missile':
            target_id = getattr(cockpit.target, 'net_id', None)
            if self.player_ship.can_fire() and target_id is not None and self.laser_assessor.on:
                self.laser_assessor.on = False
                self._command_actions.append({'type': 'fire', 'target': target_id})
                self.input_cooling_down = True
                sfx('fire_missile')
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
        elif action == 'toggle_map':
            self.is_map_open = not self.is_map_open
            self.marker_mode = None
            self.input_cooling_down = True
            sfx('map_open' if self.is_map_open else 'map_close')
        elif action == 'marker_add':
            self.marker_mode = 'PICK'
            sfx('map_marker')
        elif action.startswith('marker_shape_'):
            self.marker_mode = action[len('marker_shape_'):].upper()
            sfx('map_marker')
        elif action == 'marker_place':
            click = self.draw_ui.buttons.last_click_pos
            if self.marker_mode in self.draw_ui.MARKER_SHAPES and click is not None:
                wx, wy = self.draw_ui.map_screen_to_world(click)
                self.map_markers.append((self.marker_mode, wx, wy))
                self.marker_mode = None
                sfx('map_marker_place')
        elif action == 'marker_cancel':
            self.marker_mode = None
            sfx('cancel')
        elif action == 'marker_clear':
            self.map_markers.clear()
            sfx('map_marker_delete')
        elif action == 'blink':
            if not self.blinking:
                self.blinking = True
                sfx('blink')
        elif action == 'escape' and self.marker_mode is not None:
            # Esc backs out of marker placement before it closes anything
            self.marker_mode = None
            self.input_cooling_down = True
        elif action == 'escape':
            if self.control_screen:
                self.control_screen = False

            if self.esc_screen:
                self.esc_screen = False
            elif self.is_map_open is False:
                self.esc_screen = True

            if self.is_map_open:
                self.is_map_open = False

            self.input_cooling_down = True
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
            if missile.owner == self.my_id or missile.target is not self.player_ship:
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

    def handle_world_events(self, events):
        """React (sound/UI) to things the world reported.

        Single-player: straight from world.events after each step.
        Multiplayer: relayed from the server by the client (see NetClient.take_events).
        """
        for kind, *data in events:
            if kind == 'damage':
                if data[0] == self.my_id:
                    self.audio_manager.play_sfx('damage_taken')
            elif kind == 'radar_sweep':
                # Single-player's world already logged it; in multiplayer our copy of the
                # world isn't stepped, so the server's report is how we learn of it
                if not self.local:
                    source_id, x, y, timestamp = data
                    self.world.emissions.publish(source_id, x, y, RADAR_SWEEP, RADAR_SWEEP_POWER, timestamp)
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
        self.draw_ui.draw_callsign_plate(world.callsigns.get(self.my_id), self.my_id,
                                         len(world.callsigns), self.local)
        self.draw_ui.draw_laser_painted_warning(self.player_ship.painted)
        self.draw_ui.draw_ship_info(self.player_ship, cockpit,
                                    [line for line in (i.status_line() for i in self.instruments) if line])
        self.draw_ui.draw_control_banks(self.player_ship, cockpit, local=self.local,
                                        map_open=self.is_map_open,
                                        blink_busy=self.blinking or self.blink_arriving,
                                        sensor_buttons=[b for i in self.instruments for b in i.console_buttons()])
        self.draw_ui.draw_missile_lock_warning(cockpit.enemy_has_missile_solution)
        self.draw_ui.draw_missile_vectors(self.my_id, world.missiles, camera_x, camera_y)
        for instrument in self.instruments:
            instrument.draw_panel(self.draw_ui)
        self.draw_ui.draw_catastrophe_warning(cockpit.catastrophic_warning)
        self.draw_ui.draw_dfs_warning(cockpit.dfs_scanned, self.dfs_warning_timer)
        self.draw_ui.draw_missile_contact(self.missile_contact_timer, self.missile_contact_duration)
        for instrument in self.instruments:
            instrument.draw_overlay(self.draw_ui, camera_x, camera_y)
        for instrument in self.instruments:
            instrument.draw_controls(self.draw_ui)
        self.draw_ui.draw_tactical_map(self.is_map_open, self.player_ship, self.close_range_scan.get_contacts(),
                                       markers=self.map_markers, marker_mode=self.marker_mode)
        self.draw_ui.draw_corpo_miner_fire_warning(self.player_ship.mining_vessel_sees_you)
        self.draw_ui.draw_bullet_damage_glitch(self.player_ship.took_damage)
        self.draw_ui.draw_low_health_warning(self.player_ship.health_low)

        # Last, so the console sits on top of everything else
        self.draw_ui.draw_pause_screen(self.esc_screen)
        self.draw_ui.draw_controls_screen(self.control_screen)

        self.draw_ui.buttons.end_frame()
        end_blit()

    def find_camera(self):
        camera_x = self.player_ship.rect.center[0] - self.draw_game.screen.get_width() / 2
        camera_y = self.player_ship.rect.center[1] - self.draw_game.screen.get_height() / 2
        return camera_x, camera_y
