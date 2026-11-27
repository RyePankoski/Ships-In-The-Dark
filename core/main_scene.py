import math
import pygame

from asset_handlers.draw_game import DrawGame
from core.cockpit import Cockpit
from core.pause_menu import PauseMenu
from core.replay import ReplayState
from core.session import MatchConfig
from config.constants import SHUTDOWN_WAIT
from core.tactical_map_state import TacticalMapState
from objects.explosion import Explosion
from instruments.blink_drive import BlinkDrive
from instruments.close_range_scan import CloseRangeScan
from instruments.deep_field_scan import DeepFieldScan
from instruments.instrument import InstrumentContext
from instruments.laser_assessor import LaserAssessor
from instruments.mining_laser import MiningLaser
from instruments.material_assessor import MaterialAssessor
from instruments.radar_system import RadarSystem
from instruments.range_bands import RangeBands
from simulation.world import POWER_FLAGS, empty_command
from utility.geometry import squared_distance
from utility.input import key_pressed
from utility.timer import Timer


class MainScene:

    def __init__(self, screen, audio_manager, world, config: MatchConfig, draw_ui):
        # Classes
        self.audio_manager = audio_manager
        self.draw_game = DrawGame(screen, world.width, world.height)
        draw_ui.set_world(world)
        self.draw_ui = draw_ui

        # World + who we are in it
        self.world = world
        self.my_id = config.my_id
        self.local = config.local
        self.player_ship = world.get_ship(config.my_id)
        self.cockpit = Cockpit()

        # Outgoing actions (blink, instruments, decoy, fire) all queue here. handle_inputs
        # drains it into the command, so there is only one list to track.
        self._outbox = []
        # The command from the last frame that made one. The client resends it on screens
        # that return none (see update).
        self.last_command = empty_command()

        # Purely visual
        self.explosions = []

        # Instruments: add a new sensor or system by adding it to this list
        # (see instruments/instrument.py). The order is the order they draw in.
        self.instrument_context = InstrumentContext(
            self.player_ship, world.contacts, self.cockpit, audio_manager,
            world=world,
            send_action=lambda action: self._outbox.append(action),
        )

        self.radar_system = RadarSystem(self.instrument_context)
        self.range_bands = RangeBands(self.instrument_context)
        self.deep_field_scan = DeepFieldScan(self.instrument_context)
        self.laser_assessor = LaserAssessor(self.instrument_context)
        self.material_assessor = MaterialAssessor(self.instrument_context, self.laser_assessor)
        self.mining_laser = MiningLaser(self.instrument_context)
        self.close_range_scan = CloseRangeScan(self.instrument_context)
        self.radar_system.prox_scan = self.close_range_scan
        self.blink = BlinkDrive(self.instrument_context)
        self.instruments = [self.radar_system, self.range_bands, self.deep_field_scan, self.laser_assessor,
                            self.material_assessor, self.mining_laser, self.close_range_scan,
                            self.blink]

        self.instrument_actions = {}
        for instrument in self.instruments:
            for name, handler in instrument.actions().items():
                assert name not in self.instrument_actions, f"two instruments answer to {name!r}"
                self.instrument_actions[name] = handler

        # Cockpit actions the scene handles itself. Keys and console buttons send the same names.
        self.scene_actions = {
            'decoy': self._decoy,
            'fire_missile': self._fire_missile,
            'debug_enemy_fire': self._debug_enemy_fire,
            'debug_enemy_visibility': self._debug_enemy_visibility,
            'toggle_dampening': self._toggle_dampening,
            'silent': self.set_to_silent,
            'cloak_up': self._cloak_up,
            'cloak_down': self._cloak_down,
            'fuel_acknowledge': self._fuel_acknowledge,
            'toggle_vectors': self._toggle_vectors,
            'toggle_map': self._toggle_map,
            'marker_add': self._marker_add,
            'marker_place': self._marker_place,
            'marker_cancel': self._marker_cancel,
            'marker_clear': self._marker_clear,
            'escape': self._escape,
            'open_console': self.open_pause,
            'return_to_menu': self._return_to_menu,
        }

        # UI stuff
        self.map = TacticalMapState()
        self._end_sound_played = False  # the game over sound plays once, on the first end screen frame
        self.grid_on = True
        self.vectors_on = False  # heading / velocity overlay on the ship (H / VECTORS button)
        self.pause = PauseMenu()  # the operator console (Esc)

        # HUD elements to skip drawing this frame, by name. The tutorial fills this in.
        self.hud_hidden = set()

        # Control
        self.lock_inputs = False
        # Where the pilot leaves this scene, or None while the match is still on screen.
        # 'menu' or 'lobby'. The client (PlayScreen) reads this and nothing else.
        self.outcome = None
        self.view = 'play'  # what draw() shows: play, shutdown, spectate or end
        self.end_message = None
        self.is_host = config.is_host  # the host decides whether the match goes back to the lobby
        self.spectate_id = None  # player_id of the pilot we're watching, once our own ship is gone
        self.shutdown_timer = None  # counts down after QUIT TO MENU, then outcome is set to 'menu'
        self.replay = None  # a ReplayState while the after-action replay is on screen (from the end screen)

        # Fun cinematic type stuff
        self.ftl_traveling = False
        self.ftl_travel_timer = 0
        self.ftl_travel_cooldown = 5

        self.ftl_arriving = False
        self.ftl_arrival_timer = 0
        self.ftl_arrival_cooldown = 2

        self.sys_analyzing = False
        self.sys_analyzing_timer = 0
        self.sys_analyzing_cooldown = 2

        # Runs from the start, then stays off
        self.asteroid_laser = Timer(4)
        self.asteroid_laser.start()

        # Missile contact: starts on any missile hit. Ship destroyed: banner for another pilot's loss.
        self.missile_contact = Timer(1.5)
        self.ship_destroyed = Timer(2.0)
        self.ship_destroyed_name = ""

    @property
    def enemy_ships(self):
        return [ship for ship in self.world.ships if ship is not self.player_ship]

    def update(self, dt, events=()):
        """Advance the cockpit by one frame. Returns the command for the world, or None
        when the world should not be stepped this frame (console shutdown, game over, spectating).

        Nothing here steps the world or draws; PlayScreen does that (session.step, then draw()).
        """
        # A target that starts a blink breaks our lock on it (drop_lock is the server's to clear)
        target = self.laser_assessor.current_target
        if target is not None and target.drop_lock:
            self.laser_assessor.current_target = None

        self.view = 'play'
        if self.shutdown_timer is not None:
            self.view = 'shutdown'
            self.shutdown_timer -= dt
            if self.shutdown_timer <= 0:
                self.outcome = 'menu'
            return None

        self.draw_ui.set_hull_damage(self.player_ship.health)
        buttons = self.draw_ui.buttons
        clicks = buttons.clicked_actions(events)
        held = buttons.held_action()

        # The replay plays over the finished match: the world is not stepped while it runs
        if self.replay is not None:
            self.update_replay(dt, events, clicks)
            return None

        self.update_explosions(dt)

        # The outcome is decided by the World (locally, or by the server's snapshot); here we only show it
        if self.world.outcome == 'dead':
            # Nothing we send matters anymore; stop repeating the last command
            self.last_command = empty_command()
            # Two or more others still flying: watch them instead of the debrief screen.
            # With one left that pilot has won, so the match is over for everyone.
            targets = self.spectate_targets()
            if not self.local and len(targets) > 1:
                self.view = 'spectate'
                self.update_spectate(clicks, targets)
            else:
                self.view = 'end'
                self.end_message = ("SIGNAL LOST", "SYNCHRONIZATION LOST. DEBUG:42*1a2", 'death_screen')
                self.update_end(clicks, events)
            return None

        if self.world.outcome == 'won':
            self.view = 'end'
            self.end_message = ("TARGET DESTROYED", "HOSTILE SIGNAL TERMINATED", 'retro_beep')
            self.update_end(clicks, events)
            return None

        cockpit_keys = not self.pause.is_open
        if not cockpit_keys:
            clicks = self.handle_pause(events, clicks)

        self.handle_inputs(events, clicks, cockpit_keys=cockpit_keys)

        self.update_threats()
        self.timers(dt)

        if cockpit_keys:
            self.aim_laser_at_mouse()

        for instrument in self.instruments:
            instrument.update(dt, held)

        self.update_ship_power_use()
        self.handle_general_sound_effects()
        self.last_command = self.make_command()
        return self.last_command

    def draw(self):
        """Draw this frame's state, after the world has been stepped."""
        if self.view == 'shutdown':
            # Black screen behind the console while the shutdown sound plays
            self.draw_ui.buttons.begin_frame()
            self.draw_ui.draw_pause_console(self.pause, underlay=False)
            self.draw_ui.buttons.end_frame()
        elif self.view == 'spectate':
            self.draw_spectate(self.spectate_targets())
        elif self.view == 'end':
            message, subtitle, _ = self.end_message
            self.draw_ui.draw_debrief_screen(message, subtitle, [('replay', "REPLAY FLIGHT", "R")] + self.end_options())
        elif self.view == 'replay':
            self.draw_replay()
        else:
            self.draw_scene()

    def aim_laser_at_mouse(self):
        laser = self.laser_assessor
        if not laser.on or not pygame.mouse.get_focused() or not pygame.mouse.get_pressed()[0]:
            return
        pos = pygame.mouse.get_pos()
        if self.draw_ui.buttons._top_at(pos) is not None:
            return
        width, height = self.draw_ui.view_size()
        dx, dy = pos[0] - width / 2, pos[1] - height / 2
        if dx == 0 and dy == 0:
            return
        laser.set_direction(math.degrees(math.atan2(dy, dx)) % 360)
        laser.laser_locked = False

    def update_explosions(self, dt):
        for explosion in self.explosions:
            explosion.update(dt)
        self.explosions = [explosion for explosion in self.explosions if not explosion.finished]

    def update_ship_power_use(self):
        self.player_ship.laser_on = self.laser_assessor.on
        self.player_ship.prox_scan_on = self.close_range_scan.on
        self.player_ship.blinking = self.blink.charging
        self.player_ship.deep_field_on = self.deep_field_scan.on
        self.player_ship.radar_scan_on = self.radar_system.scanning
        self.player_ship.material_assessor_on = self.material_assessor.scanning is not None
        self.player_ship.dfs_detector_on = self.deep_field_scan.alert_on
        self.player_ship.range_bands_on = self.range_bands.on

    def open_pause(self):
        self.pause.open()
        self.audio_manager.play_sfx('pause')

    def handle_pause(self, events, clicks):
        if clicks:
            self.audio_manager.play_sfx('keyboard_clack')

        outcome = self.pause.handle(events, clicks)
        if outcome == 'resume':
            self.audio_manager.play_sfx('resume')
        elif outcome == 'quit':
            self.audio_manager.play_sfx('shutdown')
            self.shutdown_timer = SHUTDOWN_WAIT

        return ()

    def handle_inputs(self, events, clicks=(), cockpit_keys=True):
        if self.lock_inputs:
            return

        # One press, one action. Keys only count while the cockpit has them (console closed).
        if cockpit_keys:
            # Scene
            # Cloaking is a fact about the ship, so it is a request to the World (server in MP)
            if key_pressed(events, pygame.K_MINUS):
                self._cloak_down()
            if key_pressed(events, pygame.K_EQUALS):
                self._cloak_up()

            if key_pressed(events, pygame.K_z):
                self.set_to_silent()
            if key_pressed(events, pygame.K_RALT):
                self._decoy()
            if key_pressed(events, pygame.K_SPACE):
                self._fire_missile()
            if key_pressed(events, pygame.K_x):
                self._debug_enemy_fire()
            if key_pressed(events, pygame.K_SLASH):
                self._debug_enemy_visibility()
            if key_pressed(events, pygame.K_m):
                self._toggle_map()
            if key_pressed(events, pygame.K_q):
                self._toggle_dampening()
            if key_pressed(events, pygame.K_h):
                self._toggle_vectors()
            if key_pressed(events, pygame.K_ESCAPE):
                self._escape()
            # Instruments
            if key_pressed(events, pygame.K_e):
                self.laser_assessor.toggle()
            if key_pressed(events, pygame.K_i):
                self.laser_assessor.lock()
            if key_pressed(events, pygame.K_t):
                self.blink.press()
            if key_pressed(events, pygame.K_g):
                self.close_range_scan.toggle()
            if key_pressed(events, pygame.K_n):
                self.material_assessor.start_scan()
            if key_pressed(events, pygame.K_1):
                self.mining_laser.toggle()
            if key_pressed(events, pygame.K_r):
                self.radar_system.sweep()
            if key_pressed(events, pygame.K_l):
                self.range_bands.toggle()
            if key_pressed(events, pygame.K_k):
                self.deep_field_scan.toggle()
            if key_pressed(events, pygame.K_o):
                self.deep_field_scan.scan()
            if key_pressed(events, pygame.K_UP):
                self.deep_field_scan.turn(1)
            if key_pressed(events, pygame.K_DOWN):
                self.deep_field_scan.turn(-1)

        # Clicks on the console buttons
        for action in clicks:
            self.perform(action)

    def set_to_silent(self):
        self.laser_assessor.on = False
        self.close_range_scan.on = False
        self.blink.interrupt()
        self.deep_field_scan.on = False
        self.radar_system.scanning = False
        self.range_bands.on = False
        self.player_ship.dampening = False
        self.deep_field_scan.alert_on = False
        if self.mining_laser:
            self.mining_laser.toggle()

    def make_command(self):
        """Gather this frame's results into the command for the world (and the server).
        This is the only place a command is built."""
        command = empty_command()
        command['laser_target'] = self.laser_assessor.hit_id
        command['move'] = None if self.lock_inputs else self.held_movement()
        command['actions'] = self._drain_outbox()
        command['power'] = {name: getattr(self.player_ship, name) for name in POWER_FLAGS}
        return command

    def held_movement(self):
        """Which movement keys are held right now. Also plays or stops the thrust sound."""
        pressed = pygame.key.get_pressed()
        move = {'up': bool(pressed[pygame.K_w]), 'down': bool(pressed[pygame.K_s]),
                'left': bool(pressed[pygame.K_a]), 'right': bool(pressed[pygame.K_d]),
                'left_shift': bool(pressed[pygame.K_LSHIFT]), 'tab': bool(pressed[pygame.K_TAB])}
        if move['up'] or move['left'] or move['down'] or move['right']:
            self.audio_manager.play_sfx('thrust')
        else:
            self.audio_manager.stop_sfx('thrust')
        return move

    def perform(self, action):
        """Do one cockpit action, whether it came from a key or a button."""
        handler = self.instrument_actions.get(action) or self.scene_actions.get(action)
        if handler is not None:
            handler()
        elif action.startswith('marker_shape_'):
            self.map.choose_shape(action[len('marker_shape_'):])
            self.audio_manager.play_sfx('map_marker')

    def update_threats(self):
        cockpit = self.cockpit
        cockpit.enemy_has_missile_solution = False
        cockpit.catastrophic_warning = False

        for missile in self.world.missiles:
            if missile.owner == self.my_id or missile.target is not self.player_ship:
                continue
            cockpit.enemy_has_missile_solution = True
            if squared_distance(self.player_ship.rect.center, (missile.pos_x, missile.pos_y)) < 800 ** 2:
                cockpit.catastrophic_warning = True

    def sound_states(self):
        ship = self.player_ship
        cockpit = self.cockpit
        return (
            # The beam hums while it has a rock locked. The world drops the lock when the
            # rock is mined out or the beam is switched off, so the hum stops with it.
            ('mining_laser', ship.mining_target is not None, -1, True),
            ('enemy_missile_lock', cockpit.enemy_has_missile_solution, 0, True),
            ('catastrophic_warning', cockpit.catastrophic_warning, 0, True),
            ('laser_warning', ship.painted, 0, True),
            ('pirate_warning', ship.mining_vessel_sees_you, 0, True),
            ('low_health', ship.health_low and ship.alive, 0, True),
            ('low_fuel', ship.low_fuel and not ship.fuel_acknowledge, 0, False),
            ('ftl_jumping', self.ftl_traveling, 0, True),
            ('ftl_arrival', self.ftl_arriving, 0, True),
        )

    def handle_general_sound_effects(self):
        for name, active, loops, stop_when_off in self.sound_states():
            if name is None:  # a sound slot not filled in yet
                continue
            if active:
                self.audio_manager.play_sfx(name, loops=loops)
            elif stop_when_off:
                self.audio_manager.stop_sfx(name)

    def handle_world_events(self, events):
        for kind, *data in events:
            if kind == 'bullet_damage':
                if data[0] == self.my_id:
                    self.audio_manager.play_sfx('damage_taken')
            elif kind == 'asteroid_damage':
                if data[0] == self.my_id:
                    self.audio_manager.play_sfx('asteroid_damage')
                    self.draw_ui.impact_asteroid()
            elif kind == 'missile_damage':
                if data[0] == self.my_id:
                    self.draw_ui.impact_missile()
            elif kind == 'player_hit_by_missile':
                self.audio_manager.play_sfx('player_hit_by_missile')
            elif kind == 'missile_contact':
                self.audio_manager.play_sfx('missile_contact', force=True)
                self.missile_contact.start()
            elif kind == 'ship_destroyed':
                self.audio_manager.play_sfx('enemy_ship_destroyed')
                # Our own loss gets the debrief screen instead
                if data[0] != self.my_id:
                    self.ship_destroyed_name = self.world.callsigns.get(data[0], f"PILOT-{data[0]}")
                    self.ship_destroyed.start()
            elif kind == 'missile_exploded':
                x, y, hit_type, on_player = data
                self.explosions.append(Explosion(x, y, kind=hit_type, big=on_player))
            elif kind == 'mined':
                if data[0] == self.my_id:
                    self.audio_manager.play_sfx('material_scan_complete')
            elif kind == 'dfs_scanned':
                if data[0] == self.my_id:
                    self.deep_field_scan.mark_scanned()

    def timers(self, dt):
        self.missile_contact.update(dt)
        self.ship_destroyed.update(dt)

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

        if self.sys_analyzing:
            self.sys_analyzing_timer += dt
            if self.sys_analyzing_timer > self.sys_analyzing_cooldown:
                self.sys_analyzing = False
                self.sys_analyzing_timer = 0

        self.asteroid_laser.update(dt)

    def lobby_allowed(self):
        return self.is_host and not self.local

    def end_options(self, key_hints=True):
        """What the pilot can do from the game over (or spectate) screen."""
        if self.lobby_allowed:
            options = [('return_to_lobby', "BACK TO LOBBY", "ENTER" if key_hints else None),
                       ('return_to_menu', "BACK TO MENU", "ESC" if key_hints else None)]
        else:
            options = [('return_to_menu', "RETURN TO MENU", "ENTER" if key_hints else None)]
        return options

    def apply_end_clicks(self, clicks):
        if 'return_to_lobby' in clicks and self.lobby_allowed:
            self.outcome = 'lobby'
        elif 'return_to_menu' in clicks:
            self.outcome = 'menu'

    def apply_end_keys(self, events):
        """ENTER: back to the lobby when the host can, otherwise the menu. ESC: the menu."""
        if key_pressed(events, pygame.K_RETURN):
            self.outcome = 'lobby' if self.lobby_allowed else 'menu'
        elif key_pressed(events, pygame.K_ESCAPE):
            self.outcome = 'menu'

    def update_end(self, clicks=(), events=()):
        if 'replay' in clicks or key_pressed(events, pygame.K_r):
            self.replay = ReplayState(self.world)
        self.apply_end_clicks(clicks)
        if self.outcome is None:
            self.apply_end_keys(events)
        if not self._end_sound_played:
            self.audio_manager.stop_all()
            self.audio_manager.play_sfx(self.end_message[2])
            self._end_sound_played = True

    def update_replay(self, dt, events, clicks):
        """Buttons and keys drive the replay; ESC or EXIT REPLAY returns to the end screen."""
        replay = self.replay
        if 'replay_exit' in clicks or key_pressed(events, pygame.K_ESCAPE):
            self.replay = None
            self.view = 'end'
            return
        self.view = 'replay'
        # The client resends last_command every frame; a replay must not repeat old actions
        self.last_command = empty_command()
        if 'replay_play' in clicks or key_pressed(events, pygame.K_SPACE):
            replay.play_pause()
        if 'replay_forward' in clicks or key_pressed(events, pygame.K_RIGHT):
            replay.step_forward()
        if 'replay_back' in clicks or key_pressed(events, pygame.K_LEFT):
            replay.step_back()
        replay.update(dt)

    def draw_replay(self):
        replay = self.replay
        self.draw_ui.buttons.begin_frame()
        self.draw_ui.draw_replay_map(replay.asteroids, replay.pilots, replay.width, replay.height,
                                     replay.progress, replay.playing, replay.last_sample)
        self.draw_ui.buttons.end_frame()

    def spectate_targets(self):
        """Living pilots other than us, in player_id order."""
        return sorted((ship for ship in self.world.ships if ship is not self.player_ship and ship.alive),
                      key=lambda ship: ship.player_id)

    def focus_ship(self):
        """The ship the camera is on: ours, or the pilot we're watching."""
        if self.spectate_id is not None:
            for ship in self.world.ships:
                if ship.player_id == self.spectate_id and ship.alive:
                    return ship
        return self.player_ship

        # for ship in self.world.ships:
        #     if ship.player_id != self.spectate_id and ship.alive:
        #         return ship
        # return None

    def update_spectate(self, clicks, targets):
        """Our ship is gone: follow another living pilot, with PREV / NEXT to switch."""
        self.last_command = empty_command()
        ids = [ship.player_id for ship in targets]
        if self.spectate_id not in ids:
            self.spectate_id = ids[0]
        if 'spectate_next' in clicks:
            self.spectate_id = ids[(ids.index(self.spectate_id) + 1) % len(ids)]
        elif 'spectate_prev' in clicks:
            self.spectate_id = ids[(ids.index(self.spectate_id) - 1) % len(ids)]
        self.apply_end_clicks(clicks)

    def draw_spectate(self, targets):
        world = self.world
        self.draw_ui.buttons.begin_frame()

        camera_x, camera_y = self.find_camera()
        self.draw_world(camera_x, camera_y)
        self.draw_ui.draw_world_grid(camera_x, camera_y, self.grid_on)

        watched = self.focus_ship()
        name = world.callsigns.get(watched.player_id, f"PILOT-{watched.player_id}")
        number = [ship.player_id for ship in targets].index(watched.player_id) + 1
        self.draw_ui.draw_spectate_hud(world.callsigns.get(self.my_id), name, number, len(targets),
                                       self.end_options(key_hints=False))
        self.draw_ui.draw_ship_destroyed(self.ship_destroyed.remaining, self.ship_destroyed.duration, self.ship_destroyed_name)

        self.draw_ui.buttons.end_frame()

    def instrument_hidden(self, instrument):
        if instrument is self.radar_system:
            return 'radar' in self.hud_hidden
        if instrument is self.deep_field_scan:
            return 'dfs' in self.hud_hidden
        if instrument is self.laser_assessor:
            return 'laser' in self.hud_hidden
        if instrument is self.material_assessor:
            return 'material' in self.hud_hidden
        return False

    def draw_scene(self):
        world = self.world
        cockpit = self.cockpit

        self.draw_ui.buttons.begin_frame()

        camera_x, camera_y = self.find_camera()

        self.draw_world(camera_x, camera_y)

        if self.ftl_arriving:
            self.draw_game.draw_ftl_arrival(self.player_ship.rect.center, self.ftl_arrival_timer, camera_x, camera_y, self.ftl_arrival_cooldown)
        if self.sys_analyzing:
            self.draw_game.draw_ship_analysis((self.player_ship.rect.center[0], self.player_ship.rect.center[1]), self.sys_analyzing_timer, camera_x, camera_y, self.sys_analyzing_cooldown)
        self.blink.draw_effects(self.draw_game, camera_x, camera_y)

        self.draw_ui.draw_world_grid(camera_x, camera_y, self.grid_on)
        self.draw_ui.draw_ui_layout()
        self.draw_ui.draw_callsign_plate(world.callsigns.get(self.my_id), self.my_id,
                                         len(world.callsigns), self.local)
        if 'power' not in self.hud_hidden:
            self.draw_ui.draw_power_readout(self.player_ship)
        if 'navcom' not in self.hud_hidden:
            self.draw_ui.draw_navcom(self.player_ship)
        if 'cloaking' not in self.hud_hidden:
            self.draw_ui.draw_cloaking_level(self.player_ship)
        self.draw_ui.draw_laser_painted_warning(self.player_ship.painted)
        if 'ship_info' not in self.hud_hidden:
            self.draw_ui.draw_ship_info(self.player_ship, cockpit,
                                        [line for line in (i.status_line() for i in self.instruments) if line],
                                        dfs_warning=self.deep_field_scan.warning_state())
        if self.vectors_on:
            self.draw_ui.draw_ship_vectors(self.player_ship, camera_x, camera_y)
        if 'control_banks' not in self.hud_hidden:
            self.draw_ui.draw_control_banks(self.player_ship, cockpit, blink_busy=self.blink.busy, vectors_on=self.vectors_on,
                                        hidden_buttons=self.hud_hidden,
                                            sensor_buttons=[b for i in self.instruments for b in i.console_buttons()])
        self.draw_ui.draw_missile_lock_warning(cockpit.enemy_has_missile_solution)

        for instrument in self.instruments:
            if self.instrument_hidden(instrument):
                continue
            instrument.draw_panel(self.draw_ui)
        self.draw_ui.draw_catastrophe_warning(cockpit.catastrophic_warning)

        if 'dfs' not in self.hud_hidden:
            self.draw_ui.draw_dfs_warning(self.deep_field_scan.scanned, self.deep_field_scan.alert_on, self.deep_field_scan.warning.elapsed)

        self.draw_ui.draw_missile_contact(self.missile_contact.remaining, self.missile_contact.duration)
        self.draw_ui.draw_ship_destroyed(self.ship_destroyed.remaining, self.ship_destroyed.duration, self.ship_destroyed_name)
        for instrument in self.instruments:
            if self.instrument_hidden(instrument):
                continue
            instrument.draw_overlay(self.draw_ui, camera_x, camera_y)
        for instrument in self.instruments:
            if self.instrument_hidden(instrument):
                continue
            instrument.draw_controls(self.draw_ui)
        self.draw_ui.draw_tactical_map(self.map.is_open, self.player_ship, self.close_range_scan.get_contacts(),
                                       markers=self.map.markers, marker_mode=self.map.marker_mode)
        self.draw_ui.draw_corpo_miner_fire_warning(self.player_ship.mining_vessel_sees_you)
        self.draw_ui.draw_bullet_damage_glitch(self.player_ship.took_damage)
        self.draw_ui.draw_low_health_warning(self.player_ship.health_low)
        self.draw_ui.draw_out_of_fuel_warning(self.player_ship.fuel <= 0)

        # Last, so the console sits on top of everything else
        self.draw_ui.draw_pause_console(self.pause)

        self.draw_ui.buttons.end_frame()

    def draw_world(self, camera_x, camera_y):
        """Everything in space, seen from the camera (no cockpit overlays)."""
        world = self.world
        if self.ftl_traveling:
            self.draw_game.draw_ftl_jump_tunnel(self.ftl_traveling)
        else:
            self.draw_game.draw_stars(camera_x, camera_y)
            self.draw_game.draw_asteroids(world.asteroids, camera_x, camera_y)
            self.draw_game.draw_ships(world.ships, camera_x, camera_y, self.my_id, self.close_range_scan.on)
            self.draw_game.draw_drones(world.drones, camera_x, camera_y)
            self.draw_game.draw_pirates(world.pirates, camera_x, camera_y)
            self.draw_game.draw_decoys(world.decoys, camera_x, camera_y)
            self.draw_game.draw_bullets(world.bullets, camera_x, camera_y)
            self.draw_game.draw_missiles(world.missiles, camera_x, camera_y)
            self.draw_game.draw_explosions(self.explosions, camera_x, camera_y)

        self.draw_game.draw_laser(world.lasers, (camera_x, camera_y))

    def find_camera(self):
        focus = self.focus_ship().rect.center
        view_width, view_height = self.draw_ui.view_size()
        camera_x = focus[0] - view_width / 2
        camera_y = focus[1] - view_height / 2
        return camera_x, camera_y

    # --- Private classes ---

    def _cloak_up(self):
        self._outbox.append({'type': 'cloak_up'})

    def _cloak_down(self):
        self._outbox.append({'type': 'cloak_down'})

    def _decoy(self):
        self._outbox.append({'type': 'decoy'})
        self.audio_manager.play_sfx('deploy_decoy')

    def _fire_missile(self):
        target_id = getattr(self.cockpit.target, 'net_id', None)
        if self.player_ship.can_fire_missile() and target_id is not None and self.laser_assessor.on:
            self.laser_assessor.on = False
            self._outbox.append({'type': 'fire', 'target': target_id})
            self.audio_manager.play_sfx('fire_missile')

    def _debug_enemy_fire(self):
        # The debug "enemy fires at me" key only exists in single-player
        if self.local and self.enemy_ships:
            enemy = self.enemy_ships[0]
            enemy.fire()
            self.world.fire_missile(enemy, self.player_ship)

    def _debug_enemy_visibility(self):
        if self.local and self.enemy_ships:
            enemy = self.enemy_ships[0]
            enemy.current_draw += 0.5
            if enemy.current_draw > 5:
                enemy.current_draw = 0

    def _toggle_dampening(self):
        self.player_ship.dampening = not self.player_ship.dampening
        self.audio_manager.play_sfx('inertial_dampener')

    def _fuel_acknowledge(self):
        self.player_ship.fuel_acknowledge = not self.player_ship.fuel_acknowledge
        self.audio_manager.play_sfx('fuel_fault_acknowledge')

    def _toggle_vectors(self):
        self.vectors_on = not self.vectors_on
        self.audio_manager.play_sfx('map_open' if self.vectors_on else 'map_close')

    def _toggle_map(self):
        self.map.toggle()
        self.audio_manager.play_sfx('map_open' if self.map.is_open else 'map_close')

    def _marker_add(self):
        self.map.start_marker()
        self.audio_manager.play_sfx('map_marker')

    def _marker_place(self):
        if self.map.place(self.draw_ui.marker_from_click(self.map.marker_mode)):
            self.audio_manager.play_sfx('map_marker_place')

    def _marker_cancel(self):
        self.map.cancel_marker()
        self.audio_manager.play_sfx('cancel')

    def _marker_clear(self):
        self.map.clear_markers()
        self.audio_manager.play_sfx('map_marker_delete')

    def _escape(self):
        if self.map.placing:
            self.map.cancel_marker()
        elif self.map.is_open:
            self.map.close()
        else:
            self.open_pause()

    def _return_to_menu(self):
        self.outcome = 'menu'

    def _drain_outbox(self):
        """Hand over everything queued so far and start a fresh outbox."""
        actions = self._outbox
        self._outbox = []
        return actions
