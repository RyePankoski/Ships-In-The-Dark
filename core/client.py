import random
import socket

import pygame

from asset_handlers.audio_manager import AudioManager
from asset_handlers.buttons import ButtonLayer, draw_button, draw_frame
from netcode.net_client import NetClient
from netcode.server import CALLSIGN_MAX, TICK_DT, Server, clean_callsign
from simulation.snapshot import apply_snapshot
from simulation.world import World
from utility import theme
from utility.util import collect_inputs, end_blit
from .main_scene import MainScene  # noqa

TITLE = theme.AMBER_BRIGHT
GREEN = theme.GREEN
RED = theme.RED

CALLSIGN_WORDS = ("GHOST", "VIPER", "WRAITH", "NOMAD", "RAVEN", "JACKAL", "SPECTER", "HALO", "ORBIT", "MOTH")
MAX_ROSTER_LINES = 10


class Client:
    """Picks a mode and runs it.

    menu -> single-player:  builds a World locally and a MainScene that steps it.
    menu -> host:           starts a Server in this process, then joins it at 127.0.0.1.
    menu -> join:           asks for an IP, then joins it.
    Joining puts you in the lobby, where you can change your callsign and see who
    else is on the net, until the host launches (or straight into the game if it
    already has). Then it builds the World copy and the MainScene.
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
        self.callsign = f"{random.choice(CALLSIGN_WORDS)}-{random.randint(1, 9)}"
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

    def menu_actions(self, events, keys):
        """Actions chosen this frame on a menu screen: clicked buttons, plus
        key presses looked up in `keys` ({pygame key: action})."""
        actions = self.buttons.clicked_actions(events)
        for event in events:
            if event.type == pygame.KEYDOWN and event.key in keys:
                actions.append(keys[event.key])
        return actions

    def run_menu(self, events):
        keys = {pygame.K_s: 'single', pygame.K_h: 'host', pygame.K_j: 'join', pygame.K_c: 'callsign'}
        for action in self.menu_actions(events, keys):
            if action == 'single':
                self.start_single_player()
            elif action == 'host':
                self.start_hosting()
            elif action == 'join':
                self.state = 'ip_entry'
            elif action == 'callsign':
                self.state = 'callsign_entry'
            return

        self.draw_text_screen("SHIPS IN THE DARK", [f"CALLSIGN  {self.callsign or '-'}"], self.status, buttons=[
            ("SINGLE PLAYER", "S", 'single'),
            ("HOST GAME", "H", 'host'),
            ("JOIN GAME", "J", 'join'),
            ("CHANGE CALLSIGN", "C", 'callsign'),
        ])

    def edit_callsign(self, events):
        """Typing edits our callsign (letters, digits, dashes). Shared by the menu and
        the lobby; in the lobby the server hears the new one with the next hello."""
        self.callsign = edit_text(events, self.callsign, lambda c: c.isalnum() or c == '-', CALLSIGN_MAX).upper()
        if self.net:
            self.net.callsign = self.callsign

    def run_callsign_entry(self, events):
        self.edit_callsign(events)
        for action in self.menu_actions(events, {pygame.K_RETURN: 'done', pygame.K_ESCAPE: 'done'}):
            if action == 'done':
                self.callsign = clean_callsign(self.callsign)
                self.state = 'menu'
                return

        self.draw_text_screen("CALLSIGN", [
            "IDENTIFY YOURSELF, PILOT:",
            self.callsign + blink_cursor(),
        ], buttons=[("CONFIRM", "ENTER", 'done')])

    def run_ip_entry(self, events):
        self.ip_text = edit_text(events, self.ip_text, lambda c: c.isalnum() or c in '.-:', 60)

        for action in self.menu_actions(events, {pygame.K_RETURN: 'connect', pygame.K_ESCAPE: 'back'}):
            if action == 'connect' and self.ip_text.strip():
                self.start_joining(self.ip_text.strip())
                return
            elif action == 'back':
                self.state = 'menu'
                return

        self.draw_text_screen("JOIN GAME", [
            "SERVER ADDRESS:",
            self.ip_text + blink_cursor(),
        ], buttons=[
            ("CONNECT", "ENTER", 'connect'),
            ("BACK", "ESC", 'back'),
        ])

    def run_connecting(self, events):
        """Contacting the server, then the lobby until the host launches."""
        net = self.net
        if net.welcomed:
            self.edit_callsign(events)
        for action in self.menu_actions(events, {pygame.K_ESCAPE: 'cancel', pygame.K_RETURN: 'launch'}):
            if action == 'cancel':
                self.leave()
                return
            if action == 'launch' and self.server:
                self.server.launch()

        if net.rejected:
            self.leave("LINK REFUSED: NO FREE SLOT")
            return

        state = net.take_state()
        if net.welcomed and state is not None and state['started']:
            self.world = World(net.seed, with_npcs=False)
            self.sync_world(state)
            self.main_scene = MainScene(self.screen, self.audio_manager, self.world, my_id=net.player_id, local=False)
            self.state = 'playing'
            return

        if not net.welcomed:
            lines = [self.status]
            if net.timed_out:
                lines.append("NO CARRIER. CHECK ADDRESS / PORT FORWARD")
            self.draw_text_screen("ESTABLISHING LINK", lines, buttons=[("CANCEL", "ESC", 'cancel')])
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
        self.draw_text_screen("FLIGHT LOBBY", lines, buttons=buttons)

    def sync_world(self, state):
        """Bring our copy of the world up to date with what the server sent."""
        apply_snapshot(self.world, state)
        # The server's clock stamps emissions; ours must tell the same time to judge their age
        self.world.time = state['tick'] * TICK_DT
        self.world.emissions.prune(self.world.time)
        self.world.remove_asteroids(self.net.take_dead_asteroids())
        if self.world.callsigns != self.net.roster:
            self.world.callsigns = dict(self.net.roster)

    def run_playing(self, user_inputs, dt, events=()):
        if self.net:
            if self.net.timed_out:
                self.audio_manager.stop_all()
                self.leave("CARRIER LOST")
                return
            state = self.net.take_state()
            if state is not None:
                self.sync_world(state)
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
        """A framed console, same style as the in-game operator console: header
        strip, title, readout lines, a column of buttons
        [(label, key hint, action) or (label, key hint, action, enabled)],
        and a fault line (`footer`) or the input prompt along the bottom."""
        self.screen.fill(theme.BLACK)
        self.buttons.begin_frame()
        w, h = self.screen.get_size()

        small = theme.font(18)
        title_surf = self.title_font.render(title, True, TITLE)
        line_surfs = [self.font.render(line, True, GREEN) for line in lines]
        footer_surf = small.render(footer, True, RED) if footer else None

        btn_w, btn_h, btn_gap = 360, 50, 12
        body_w = max([title_surf.get_width(), btn_w] + [s.get_width() for s in line_surfs])
        panel_w = min(w - 32, max(520, body_w + 80))
        panel_h = (52 + title_surf.get_height() + 36
                   + sum(s.get_height() + 12 for s in line_surfs) + (24 if lines and buttons else 0)
                   + len(buttons) * (btn_h + btn_gap) + 56)
        panel = pygame.Rect(0, 0, panel_w, panel_h)
        panel.center = (w // 2, h // 2)
        draw_frame(self.screen, panel, width=2, tick=14)

        header = small.render("ERGOT SYSTEMS // FLIGHT CONSOLE", True, theme.AMBER_DIM)
        self.screen.blit(header, header.get_rect(midtop=(panel.centerx, panel.top + 16)))

        y = panel.top + 52
        self.screen.blit(title_surf, title_surf.get_rect(midtop=(panel.centerx, y)))
        y += title_surf.get_height() + 36
        for surf in line_surfs:
            self.screen.blit(surf, surf.get_rect(midtop=(panel.centerx, y)))
            y += surf.get_height() + 12
        if lines and buttons:
            y += 24
        for label, key, action, *rest in buttons:
            enabled = rest[0] if rest else True
            rect = pygame.Rect(0, 0, btn_w, btn_h)
            rect.midtop = (panel.centerx, y)
            draw_button(self.screen, rect, label, key=key, enabled=enabled, align="center",
                        font=self.font, key_font=theme.font(14))
            self.buttons.register(rect, action, enabled=enabled)
            y += btn_h + btn_gap

        # Bottom line: the last fault if there is one, else the input prompt
        if footer_surf is None:
            footer_surf = small.render(f"AWAITING INPUT {blink_cursor()}", True, theme.AMBER_DIM)
        self.screen.blit(footer_surf, footer_surf.get_rect(midbottom=(panel.centerx, panel.bottom - 16)))

        self.buttons.end_frame()
        end_blit()


def blink_cursor():
    return "_" if pygame.time.get_ticks() // 500 % 2 == 0 else " "


def edit_text(events, text, allowed, max_len):
    """Apply this frame's typing to `text`: backspace, plus characters `allowed` accepts."""
    for event in events:
        if event.type != pygame.KEYDOWN:
            continue
        if event.key == pygame.K_BACKSPACE:
            text = text[:-1]
        elif event.unicode and allowed(event.unicode) and len(text) < max_len:
            text += event.unicode
    return text


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
