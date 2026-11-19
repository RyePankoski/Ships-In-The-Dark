import random
import socket

import pygame

from asset_handlers.audio_manager import AudioManager
from asset_handlers.buttons import ButtonLayer, draw_button
from netcode.net_client import NetClient
from netcode.server import Server
from simulation.snapshot import apply_snapshot
from simulation.world import World
from utility import theme
from utility.util import collect_inputs, end_blit
from .main_scene import MainScene  # noqa

TITLE = theme.AMBER_BRIGHT
GREEN = theme.GREEN
RED = theme.RED


class Client:
    """Picks a mode and runs it.

    menu -> single-player:  builds a World locally and a MainScene that steps it.
    menu -> host:           starts a Server in this process, then joins it at 127.0.0.1.
    menu -> join:           asks for an IP, then joins it.
    Joining waits for the server's welcome (seed + our player id) and for the
    second player before building the World copy and the MainScene.
    """

    def __init__(self, screen, launch=None):
        self.screen = screen
        self.audio_manager = AudioManager()
        self.audio_manager.play_ambience('ambience')

        self.title_font = theme.font(56)
        self.font = theme.font(28)

        self.state = 'menu'
        self.main_scene = None
        self.world = None
        self.server = None
        self.net = None

        self.ip_text = "127.0.0.1"
        self.status = ""
        self.buttons = ButtonLayer()  # menu screens' buttons

        launch = launch or {}
        if launch.get('mode') == 'single':
            self.start_single_player()
        elif launch.get('mode') == 'host':
            self.start_hosting()
        elif launch.get('mode') == 'join':
            self.start_joining(launch.get('ip', '127.0.0.1'))

    # ------------------------------------------------------------------
    # Mode setup
    # ------------------------------------------------------------------
    def start_single_player(self):
        self.world = World(random.randrange(2 ** 31), with_npcs=True)
        self.world.spawn_ship(1)
        self.world.spawn_ship(2, is_ai=True)
        self.main_scene = MainScene(self.screen, self.audio_manager, self.world, my_id=1, local=True)
        self.state = 'playing'

    def start_hosting(self):
        try:
            self.server = Server()
        except OSError as e:
            self.status = f"Could not host: {e}"
            self.state = 'menu'
            return
        self.start_joining('127.0.0.1')

    def start_joining(self, ip):
        self.net = NetClient(ip)
        self.status = f"Contacting {ip}..."
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
        elif self.state == 'connecting':
            self.run_connecting(events)
        elif self.state == 'playing':
            self.run_playing(user_inputs, dt, events)

    def menu_actions(self, events, keys):
        """Actions chosen this frame on a menu screen: clicked buttons, plus
        key presses looked up in `keys` ({pygame key: action})."""
        actions = self.buttons.clicked_actions(events)
        for event in events:
            if event.type == pygame.KEYDOWN and event.key in keys:
                actions.append(keys[event.key])
        return actions

    def run_menu(self, events):
        for action in self.menu_actions(events, {pygame.K_s: 'single', pygame.K_h: 'host', pygame.K_j: 'join'}):
            if action == 'single':
                self.start_single_player()
            elif action == 'host':
                self.start_hosting()
            elif action == 'join':
                self.state = 'ip_entry'
            return

        self.draw_text_screen("SHIPS IN THE DARK", [], self.status, buttons=[
            ("SINGLE PLAYER", "S", 'single'),
            ("HOST GAME", "H", 'host'),
            ("JOIN GAME", "J", 'join'),
        ])

    def run_ip_entry(self, events):
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_BACKSPACE:
                self.ip_text = self.ip_text[:-1]
            elif event.unicode and (event.unicode.isalnum() or event.unicode in '.-:') and len(self.ip_text) < 60:
                self.ip_text += event.unicode

        for action in self.menu_actions(events, {pygame.K_RETURN: 'connect', pygame.K_ESCAPE: 'back'}):
            if action == 'connect' and self.ip_text.strip():
                self.start_joining(self.ip_text.strip())
                return
            elif action == 'back':
                self.state = 'menu'
                return

        cursor = "_" if pygame.time.get_ticks() // 500 % 2 else " "
        self.draw_text_screen("JOIN GAME", [
            "SERVER ADDRESS:",
            self.ip_text + cursor,
        ], buttons=[
            ("CONNECT", "ENTER", 'connect'),
            ("BACK", "ESC", 'back'),
        ])

    def run_connecting(self, events):
        if 'cancel' in self.menu_actions(events, {pygame.K_ESCAPE: 'cancel'}):
            self.leave()
            return

        net = self.net
        if net.rejected:
            self.leave("That game is full.")
            return

        state = net.take_state()
        if net.welcomed and state is not None and state['started']:
            self.world = World(net.seed, with_npcs=False)
            apply_snapshot(self.world, state)
            self.main_scene = MainScene(self.screen, self.audio_manager, self.world, my_id=net.player_id, local=False)
            self.state = 'playing'
            return

        lines = []
        if not net.welcomed:
            lines.append(self.status)
            if net.timed_out:
                lines.append("No answer yet. Is the address right and the port forwarded?")
        else:
            players = net.latest_state['players'] if net.latest_state else 1
            lines.append(f"CONNECTED AS PLAYER {net.player_id}")
            lines.append(f"WAITING FOR OPPONENT ({players}/2)")
        if self.server:
            lines.append("")
            lines.append(f"HOSTING ON {local_ip()}:{self.server.network.port}")
        self.draw_text_screen("ESTABLISHING LINK", lines, buttons=[("CANCEL", "ESC", 'cancel')])

    def run_playing(self, user_inputs, dt, events=()):
        if self.net:
            if self.net.timed_out:
                self.audio_manager.stop_all()
                self.leave("Connection lost.")
                return
            state = self.net.take_state()
            if state is not None:
                apply_snapshot(self.world, state)
            self.main_scene.handle_world_events(self.net.take_events())

        self.main_scene.run(user_inputs, dt, events)

        # Game over screen: Enter (or its button) goes back to the menu.
        # QUIT TO MENU on the operator console does the same mid-game.
        if self.main_scene.quit_requested or (self.main_scene.end_tripped and user_inputs['enter']):
            self.audio_manager.stop_all()
            self.audio_manager.play_ambience('ambience')
            self.leave()
            return

        if self.net:
            self.net.send_command(self.main_scene.command)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw_text_screen(self, title, lines, footer="", buttons=()):
        """Title, lines of text, then a column of buttons [(label, key hint, action)]."""
        self.screen.fill(theme.BLACK)
        self.buttons.begin_frame()
        w, h = self.screen.get_size()
        y = h // 3
        title_surf = self.title_font.render(title, True, TITLE)
        self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, y))
        y += title_surf.get_height() + 40
        for line in lines:
            surf = self.font.render(line, True, GREEN)
            self.screen.blit(surf, (w // 2 - surf.get_width() // 2, y))
            y += surf.get_height() + 12
        if lines and buttons:
            y += 24
        for label, key, action in buttons:
            rect = pygame.Rect(0, 0, 360, 50)
            rect.midtop = (w // 2, y)
            draw_button(self.screen, rect, label, key=key, align="center", font=self.font, key_font=theme.font(14))
            self.buttons.register(rect, action)
            y += rect.height + 12
        if footer:
            surf = self.font.render(footer, True, RED)
            self.screen.blit(surf, (w // 2 - surf.get_width() // 2, y + 30))
        self.buttons.end_frame()
        end_blit()


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
