from asset_handlers.crt import crt
from asset_handlers.draw_game import DrawGame
from asset_handlers.draw_ui import DrawUI
from core.cockpit import Cockpit
from core.pause_menu import PauseMenu
from instruments.close_range_scan import CloseRangeScan
from instruments.deep_field_scan import DeepFieldScan
from instruments.instrument import InstrumentContext
from instruments.laser_assessor import LaserAssessor
from instruments.mining_laser import MiningLaser
from instruments.material_assessor import MaterialAssessor
from instruments.radar_system import RadarSystem
from simulation.world import MOVE_KEYS, POWER_FLAGS, empty_command
from utility.common import *



class MainScene:
    """One player's view of a World: instruments, UI, camera and sound.

    local=True:  single-player. This scene owns the World and steps it.
    local=False: multiplayer. The World is a copy kept up to date by the client
                 from server snapshots; this scene only reads it and produces
                 `self.command` for the client to send to the server.
    The scene never moves world objects itself; it asks via a command.
    """

    SHUTDOWN_WAIT = 2  # seconds of black screen so the shutdown sound can play

    def __init__(self, screen, audio_manager, world, my_id, local=True):
        # Classes
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
        self.material_assessor = MaterialAssessor(self.instrument_context, self.laser_assessor)
        self.mining_laser = MiningLaser(self.instrument_context, self.laser_assessor)
        self.close_range_scan = CloseRangeScan(self.instrument_context)
        self.instruments = [self.radar_system, self.deep_field_scan, self.laser_assessor,
                            self.material_assessor, self.mining_laser, self.close_range_scan]

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
        self.vectors_on = False  # heading / velocity overlay on the ship (H / VECTORS button)
        self.pause = PauseMenu()  # the operator console (Esc)

        # input timer
        self.input_timer_cooldown = 0.2
        self.input_cooling_down = False
        self.input_timer = 0
        self.dfs_warning_cooldown = 3
        self.dfs_warning_timer = 0

        # Control
        self.lock_inputs = False
        self.quit_requested = False  # set by QUIT TO MENU; the client acts on it
        self.shutdown_timer = None  # counts down after QUIT TO MENU, then quit_requested is set
        self._command_actions = []  # this frame's command['actions'], for perform()

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
        self.impact_seen = 0
        self.impact_timer = None

        # Counts down from missile_contact_duration after any missile hit
        self.missile_contact_timer = 0
        self.missile_contact_duration = 1.5

    @property
    def enemy_ships(self):
        return [ship for ship in self.world.ships if ship is not self.player_ship]

    def run(self, inputs, dt, events=()):
        if self.shutdown_timer is not None:
            self.run_shutdown(dt)
            return

        crt.set_damage(self.player_ship.health_low)
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

        cockpit_keys = not self.pause.is_open
        if not cockpit_keys:
            clicks = self.handle_pause(inputs, clicks)

        self.command = self.handle_inputs(inputs, dt, clicks, cockpit_keys=cockpit_keys)
        if self.local:
            self.world.step({self.my_id: self.command}, dt)
            self.handle_world_events(self.world.events)
        else:
            self.world.predict(self.my_id, self.command, dt)

        for ship in self.world.ships:
            ship.player = ship is self.player_ship

        self.update_threats()
        self.track_explosions()

        self.timers(dt)

        for instrument in self.instruments:
            instrument.update(dt, inputs)

        self.update_ship_power_use()
        self.handle_general_sound_effects()
        self.draw_scene()

        self.explosions = []

    def update_ship_power_use(self):
        self.player_ship.laser_on = self.laser_assessor.on
        self.player_ship.prox_scan_on = self.close_range_scan.on
        self.player_ship.blinking = self.blinking
        self.player_ship.deep_field_on = self.deep_field_scan.on
        self.player_ship.radar_scan_on = self.radar_system.scanning
        self.player_ship.material_assessor_on = self.material_assessor.scanning is not None

    def start_input_cooldown(self):
        self.input_cooling_down = True

    def open_pause(self):
        self.pause.open()
        self.audio_manager.play_sfx('pause')
        self.input_cooling_down = True

    def handle_pause(self, inputs, clicks):
        """While the operator console is open it takes this frame's clicks and keys.

        Returns the clicks left for the cockpit, which is none.
        """
        if clicks:
            self.audio_manager.play_sfx('keyboard_clack')
        keys_live = not self.input_cooling_down
        if clicks or (keys_live and any(inputs.get(key) for key in PauseMenu.KEYS)):
            self.input_cooling_down = True

        outcome = self.pause.handle(inputs, clicks, keys_live)
        if outcome == 'resume':
            self.audio_manager.play_sfx('resume')
        elif outcome == 'quit':
            self.audio_manager.play_sfx('shutdown')
            self.shutdown_timer = self.SHUTDOWN_WAIT

        return ()

    def run_shutdown(self, dt):
        """Black screen behind the console while the shutdown sound plays, then leave."""
        self.shutdown_timer -= dt
        if self.shutdown_timer <= 0:
            self.quit_requested = True
            return

        self.draw_game.start_blit()
        self.draw_ui.screen.fill((0, 0, 0))
        self.draw_ui.buttons.begin_frame()
        self.pause.draw(self.draw_ui.screen, self.draw_ui.buttons, underlay=False)
        self.draw_ui.buttons.end_frame()
        end_blit()

    # Key -> action, in the order they're checked. Console buttons produce the
    # same action names (see asset_handlers/buttons.py), so a click and a key
    # press both go through perform().
    # The instruments add their own keys to this (see Instrument.keys).
    KEY_ACTIONS = (
        ('right_alt', 'decoy'),
        ('p', 'fire_missile'),
        ('x', 'debug_enemy_fire'),
        ('m', 'toggle_map'),
        ('t', 'blink'),
        ('g', 'toggle_dampening'),
        ('h', 'toggle_vectors'),
        ('esc', 'escape'),
    )
    def handle_inputs(self, inputs, dt, clicks=(), cockpit_keys=True):
        """Turn this frame's keys and clicks into cockpit changes + a command for the world."""
        command = empty_command()
        command['actions'] = self.pending_actions
        command['laser_target'] = self.laser_assessor.hit_id
        self.pending_actions = []
        self._command_actions = command['actions']

        if self.lock_inputs:
            return command

        if inputs['up'] or inputs['left'] or inputs['down'] or inputs['right']:
            self.audio_manager.play_sfx('thrust')
        else:
            self.audio_manager.stop_sfx('thrust')

        command['move'] = {key: bool(inputs[key]) for key in MOVE_KEYS}

        # Held keys repeat every frame, so they wait out the cooldown. A click
        # is a single press and always goes through.
        actions = []
        keys_live = not self.input_cooling_down
        self.instrument_context.keys_live = keys_live
        if keys_live and cockpit_keys:
            for key, action in self.key_actions:
                if inputs[key]:
                    actions.append(action)
        actions += clicks

        for action in actions:
            self.perform(action)

        # Read after the actions, so a switch flipped this frame (e.g. dampening) is the one sent
        command['power'] = {name: getattr(self.player_ship, name) for name in POWER_FLAGS}
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
        # The debug "enemy fires at me" key only exists in single-player
        elif action == 'debug_enemy_fire':
            if self.local and self.enemy_ships:
                enemy = self.enemy_ships[0]
                enemy.fire()
                self.world.fire_missile(enemy, self.player_ship)
                self.input_cooling_down = True
        elif action == 'toggle_dampening':
            self.player_ship.dampening = not self.player_ship.dampening
            sfx('inertial_dampener')
            self.input_cooling_down = True
        elif action == 'fuel_acknowledge':
            self.player_ship.fuel_acknowledge = not self.player_ship.fuel_acknowledge
            sfx('fuel_fault_acknowledge')
        elif action == 'toggle_vectors':
            self.vectors_on = not self.vectors_on
            sfx('map_open' if self.vectors_on else 'map_close')
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
            if not self.blinking and self.player_ship.fuel > BLINK_FUEL_THRESHOLD:
                self.blinking = True
                sfx('blink')

            if self.player_ship.fuel <= BLINK_FUEL_THRESHOLD:
                self.audio_manager.play_sfx('blink_denied')


        elif action == 'escape' and self.marker_mode is not None:
            # Esc backs out of marker placement before it closes anything
            self.marker_mode = None
            self.input_cooling_down = True

        elif action == 'escape':
            # Esc closes the map first; with the map shut it opens the console
            if self.is_map_open:
                self.is_map_open = False
            else:
                self.open_pause()
            self.input_cooling_down = True
        elif action == 'open_console':
            self.open_pause()
        elif action == 'return_to_menu':
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
        # The beam hums while it has a rock locked. The world drops the lock when the
        # rock is mined out or the beam is switched off, so the hum stops with it.
        if self.player_ship.mining_target is not None:
            self.audio_manager.play_sfx('mining_laser', loops=-1)
        else:
            self.audio_manager.stop_sfx('mining_laser')

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

        if self.player_ship.low_fuel and not self.player_ship.fuel_acknowledge:
            self.audio_manager.play_sfx('low_fuel')

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
            if kind == 'bullet_damage':
                if data[0] == self.my_id:
                    self.audio_manager.play_sfx('damage_taken')
            elif kind == 'asteroid_damage':
                if data[0] == self.my_id:
                    self.audio_manager.play_sfx('asteroid_damage')
            elif kind == 'missile_contact':
                self.audio_manager.play_sfx('missile_contact', force=True)
                self.missile_contact_timer = self.missile_contact_duration
            elif kind == 'mined':
                if data[0] == self.my_id:
                    self.audio_manager.play_sfx('material_scan_complete')

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

        # Non-fatal asteroid bumps: restart the failure effect on each contact
        if self.player_ship.impact_count != self.impact_seen:
            self.impact_seen = self.player_ship.impact_count
            self.impact_timer = 0.0
        if self.impact_timer is not None:
            self.impact_timer += dt
            if self.impact_timer >= self.draw_ui.IMPACT_DURATION:
                self.impact_timer = None

    def end_screen(self, message, subtitle, sound, clicks=()):
        if 'return_to_menu' in clicks:
            self.quit_requested = True
        self.draw_ui.draw_debrief_screen(message, subtitle, 'return_to_menu', "RETURN TO MENU")
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
        self.draw_ui.draw_power_readout(self.player_ship)
        self.draw_ui.draw_laser_painted_warning(self.player_ship.painted)
        self.draw_ui.draw_ship_info(self.player_ship, cockpit,
                                    [line for line in (i.status_line() for i in self.instruments) if line])
        if self.vectors_on:
            self.draw_ui.draw_ship_vectors(self.player_ship, camera_x, camera_y)
        self.draw_ui.draw_control_banks(self.player_ship, cockpit,map_open=self.is_map_open,blink_busy=self.blinking or self.blink_arriving,vectors_on=self.vectors_on,sensor_buttons=[b for i in self.instruments for b in i.console_buttons()])
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
        if self.impact_timer is not None:
            strength = 1 - self.impact_timer / self.draw_ui.IMPACT_DURATION
            self.draw_ui.draw_impact_failure(strength, self.impact_timer)
        self.draw_ui.draw_low_health_warning(self.player_ship.health_low)
        self.draw_ui.draw_out_of_fuel_warning(self.player_ship.fuel <= 0)

        # Last, so the console sits on top of everything else
        self.pause.draw(self.draw_ui.screen, self.draw_ui.buttons)

        self.draw_ui.buttons.end_frame()
        end_blit()

    def find_camera(self):
        camera_x = self.player_ship.rect.center[0] - self.draw_game.screen.get_width() / 2
        camera_y = self.player_ship.rect.center[1] - self.draw_game.screen.get_height() / 2
        return camera_x, camera_y
