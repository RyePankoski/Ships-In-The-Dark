import random
import socket
import sys

import pygame

from asset_handlers.audio_manager import AudioManager
from netcode.net_client import NetClient
from netcode.server import CALLSIGN_MAX, TICK_DT, Server, clean_callsign
from simulation.snapshot import apply_snapshot
from simulation.world import World
from utility.constants import SNAPSHOT_AGE
from utility.common import collect_inputs
from .main_scene import MainScene  # noqa
from .menu import Menu  # noqa
from utility.common import check_for_profanity, edit_text, blink_cursor, REPLACEMENTS
import re

CALLSIGN_WORDS = ("GHOST", "VIPER", "WRAITH", "NOMAD", "RAVEN", "JACKAL", "SPECTER",
                  "HALO", "ORBIT", "MOTH", "DEADBAND", "BLACKOUT",
                  "DEADBAND", "BLACKOUT", "GHOSTLINE", "NULL", "GRAVESHIFT",
                  "STATIC", "WRAITH", "COLDWIRE", "REDSHIFT", "VANDAL",
                  "DEADLOCK", "NIGHTFALL", "IRONCLAD", "RATCHET", "PHANTOM",
                  "BLACKBOX", "ZERO HOUR", "CINDER", "OUTCAST", "SPECTRE",
                  "DUSTDEVIL", "BURNWIRE", "MEATLOCKER", "CROWBAR", "DARKSTAR",
                  "FALLOUT", "RUSTBUCKET", "MALFUNCTION", "HOLLOWPOINT", "GRIMJACK",
                  "WIDOWMAKER", "PAPERCLIP", "STATIC DOG", "REDLINE", "BONEYARD",
                  "SHOCKTROOPER", "ASHFALL", "CUTOFF", "DEATHWISH", "TINMAN"
                  )
MAX_ROSTER_LINES = 10


class Client:
    def __init__(self, screen):
        self.screen = screen
        self.audio_manager = AudioManager()
        self.audio_manager.play_sfx('startup')
        self.audio_manager.play_ambience('ambience')

        self.state = 'menu'
        self.main_scene = None
        self.world = None
        self.server = None
        self.net = None
        self.match_joined = None  # the server's match number when our current game started

        self.menu = Menu(screen, self.audio_manager)
        self.callsign = f"{random.choice(CALLSIGN_WORDS)}-{random.randint(1, 9)}"
        self.status = ""

    # ------------------------------------------------------------------
    # Mode setup
    # ------------------------------------------------------------------
    def start_single_player(self):
        self.world = World(random.randrange(2 ** 31), with_npcs=True)
        self.world.spawn_ship(1,x=500, y=500)
        self.world.spawn_ship(2, is_ai=True, x=500, y=600)
        self.world.callsigns = {1: self.callsign or "PILOT-1", 2: "UNKNOWN"}
        self.main_scene = MainScene(self.screen, self.audio_manager, self.world, my_id=1, local=True)
        self.state = 'playing'

    def start_hosting(self):
        try:
            self.server = Server()
        except OSError as e:
            self.status = f"HOST FAULT: {str(e).upper()}"
            self.state = 'menu'
            return
        self.start_joining('127.0.0.1')

    def start_joining(self, ip):
        self.net = NetClient(ip, callsign=self.callsign)
        self.status = f"CONTACTING {ip} ..."
        self.state = 'connecting'

    def leave(self, status=""):
        if self.net:
            self.net.close()
        if self.server:
            self.server.close()
        self.net = self.server = self.main_scene = self.world = None
        self.status = status
        self.state = 'menu'

    # ------------------------------------------------------------------
    # Frame
    # ------------------------------------------------------------------

    def run(self, dt, events):
        user_inputs = collect_inputs()

        if self.server:
            self.server.run(dt)
        if self.net:
            self.net.update(dt)

        if self.state == 'menu':
            self.run_menu(events)
        elif self.state == 'ip_entry':
            self.run_ip_entry(events)
        elif self.state == 'callsign_entry':
            self.run_callsign_entry(events)
        elif self.state == 'connecting':
            self.run_connecting(events)
        elif self.state == 'playing':
            self.run_playing(user_inputs, dt, events)

    def run_menu(self, events):
        action = self.menu.main_screen(events, self.callsign, self.status)
        if action == 'single':
            self.start_single_player()
        elif action == 'host':
            self.start_hosting()
        elif action == 'join':
            self.state = 'ip_entry'
        elif action == 'callsign':
            self.state = 'callsign_entry'
        elif action == 'quit':
            pygame.quit()
            sys.exit()

    def edit_callsign(self, events):
        self.callsign = edit_text(events, self.callsign, lambda c: c.isalnum() or c == '-' or c == ' ', CALLSIGN_MAX).upper()

        if check_for_profanity(self.callsign):
            self.callsign = random.choice(REPLACEMENTS)

        if self.net:
            self.net.callsign = self.callsign

    def run_callsign_entry(self, events):
        self.edit_callsign(events)
        if self.menu.callsign_screen(events, self.callsign) == 'done':
            self.callsign = clean_callsign(self.callsign)
            self.state = 'menu'

    def run_ip_entry(self, events):
        action = self.menu.ip_screen(events)
        if action == 'connect':
            self.start_joining(self.menu.ip_text.strip())
        elif action == 'back':
            self.state = 'menu'

    def run_connecting(self, events):
        """Contacting the server, then the lobby until the host launches."""
        net = self.net
        if net.welcomed:
            self.edit_callsign(events)

        for action in self.menu.menu_actions(events, {pygame.K_ESCAPE: 'cancel', pygame.K_RETURN: 'launch'}):
            if action == 'cancel':
                self.leave()
                return
            if action == 'launch' and self.server:
                self.server.launch()

        if net.rejected:
            self.leave("LINK REFUSED: NO FREE SLOT")
            return

        state = net.take_state()
        # While our last game's end is still being reported, a 'started' state is the old match
        if net.welcomed and state is not None and state['started'] and not net.match_over_pending:
            self.world = World(net.seed, with_npcs=False)
            self.sync_world(state)
            self.main_scene = MainScene(self.screen, self.audio_manager, self.world, my_id=net.player_id, local=False)
            self.main_scene.is_host = self.server is not None
            self.match_joined = net.match
            self.state = 'playing'
            return

        if not net.welcomed:
            lines = [self.status]
            if net.timed_out:
                lines.append("NO CARRIER. CHECK ADDRESS / PORT FORWARD")
            self.menu.draw_ui.draw_text_screen("ESTABLISHING LINK", lines, buttons=[("CANCEL", "ESC", 'cancel')], header="ERGOT SYSTEMS // SYS-LINK")
            return

        lines = [f"CALLSIGN  {self.callsign}{blink_cursor()}", "", f"PILOTS ON NET: {len(net.roster)}"]
        roster = sorted(net.roster.items())
        for player_id, callsign in roster[:MAX_ROSTER_LINES]:
            you = "  < YOU" if player_id == net.player_id else "       "
            lines.append(f"{player_id:02d}  {callsign:<{CALLSIGN_MAX}}{you}")
        if len(roster) > MAX_ROSTER_LINES:
            lines.append(f"+{len(roster) - MAX_ROSTER_LINES} MORE")
        lines.append("")

        buttons = []
        if self.server:
            lines.append(f"HOSTING ON {local_ip()}:{self.server.network.port}")
            ready = self.server.can_launch
            buttons.append(("LAUNCH", "ENTER", 'launch', ready))
            if not ready:
                lines.append("NEED 2 OR MORE PILOTS TO LAUNCH")
        else:
            lines.append("AWAITING HOST LAUNCH")
        buttons.append(("LEAVE", "ESC", 'cancel'))
        self.menu.draw_ui.draw_text_screen("FLIGHT LOBBY", lines, buttons=buttons, header="ERGOT SYSTEMS // PRE-FLIGHT DIAGNOSTICS")

    def sync_world(self, state):
        """Bring our copy of the world up to date with what the server sent."""
        apply_snapshot(self.world, state, age=SNAPSHOT_AGE, my_id=self.net.player_id)
        self.world.time = state['tick'] * TICK_DT
        self.world.remove_asteroids(self.net.take_dead_asteroids())
        if self.world.callsigns != self.net.roster:
            self.world.callsigns = dict(self.net.roster)

    def return_to_lobby(self):
        """Keep the connection (and the server, if we host) and go back to the lobby."""
        self.main_scene = None
        self.world = None
        self.state = 'connecting'

    def run_playing(self, user_inputs, dt, events=()):
        if self.net:
            if self.net.timed_out:
                self.audio_manager.stop_all()
                self.leave("CARRIER LOST")
                return
            # The host has sent everyone back to the lobby. This applies even to a pilot
            # sitting on their own game over screen.
            if self.net.match != self.match_joined:
                self.audio_manager.stop_all()
                self.return_to_lobby()
                return
            if self.net.match == self.match_joined:
                state = self.net.take_state()
                if state is not None:
                    self.sync_world(state)
                self.main_scene.handle_world_events(self.net.take_events())

        self.main_scene.run(user_inputs, dt, events)

        # Game over screen: the host can take everyone back to the lobby (ENTER or the button);
        # everyone can go to the menu (ESC, the button, or ENTER for non-hosts)
        game_over = self.main_scene.end_tripped
        back_to_lobby = bool(self.net and self.server
                             and (self.main_scene.lobby_requested or (game_over and user_inputs['enter'])))
        back_to_menu = self.main_scene.quit_requested or (
            game_over and (user_inputs['enter'] or user_inputs['escape']))
        if back_to_lobby or back_to_menu:
            self.audio_manager.stop_all()
            self.audio_manager.play_sfx('startup')
            self.audio_manager.play_ambience('ambience')
            if back_to_lobby:
                self.net.report_match_over()
                self.return_to_lobby()
            else:
                self.leave()
            return

        if self.net:
            self.net.send_command(self.main_scene.command)


def local_ip():
    """This machine's LAN address, to tell the other player. Sends nothing."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
