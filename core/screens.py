"""The screens the Client switches between. Each is a small class whose run(events) draws
itself, handles input, and returns an action string (or None) for the Client to act on."""
import pygame

from config.constants import CALLSIGN_MAX
from utility.input import collect_inputs, key_pressed
from utility.text_input import blink_cursor, edit_text

MAX_ROSTER_LINES = 10


class Screen:
    def __init__(self, session, draw_ui, audio):
        self.session = session
        self.draw_ui = draw_ui
        self.audio = audio

    def typing_click(self):
        self.audio.play_sfx('typing_click', force=True)

    def edit_callsign(self, events):
        """Type into the session's callsign."""
        text = edit_text(events, self.session.callsign,
                         lambda c: c.isalnum() or c == '-' or c == ' ',
                         CALLSIGN_MAX, self.typing_click)
        self.session.set_callsign(text)

    def actions(self, events, keys):
        """Actions chosen this frame: clicked buttons, plus key presses looked up in
        `keys` ({pygame key: action})."""
        actions = self.draw_ui.buttons.clicked_actions(events)
        if actions:
            self.audio.play_sfx('keyboard_clack', force=True)
        for event in events:
            if event.type == pygame.KEYDOWN and event.key in keys:
                actions.append(keys[event.key])
        return actions

    def console(self, events, keys, title, lines, buttons, header, footer="", accept=None):
        """One console screen: the first action chosen this frame, or draw it and return None.
        `accept(action)` can veto an action (e.g. connect with no address)."""
        for action in self.actions(events, keys):
            if accept is None or accept(action):
                return action

        self.draw_ui.draw_text_screen(title, lines, footer=footer, header=header, buttons=buttons)
        return None


class MenuScreen(Screen):
    """Returns 'single', 'host', 'join', 'callsign' or 'quit'."""
    KEYS = {pygame.K_s: 'single', pygame.K_h: 'host', pygame.K_j: 'join', pygame.K_c: 'callsign',
            pygame.K_q: 'quit'}
    BUTTONS = [("SINGLE PLAYER", "S", 'single'),
               ("HOST GAME", "H", 'host'),
               ("JOIN GAME", "J", 'join'),
               ("CHANGE CALLSIGN", "C", 'callsign'),
               ("QUIT", "Q", 'quit')]

    def run(self, events, dt):
        for action in self.actions(events, self.KEYS):
            return action
        self.draw_ui.draw_main_menu("SHIPS IN THE DARK", self.session.callsign, self.BUTTONS,
                                    footer=self.session.status)
        return None


class CallsignScreen(Screen):
    """Types the callsign. Returns 'done'."""

    def run(self, events, dt):
        self.edit_callsign(events)
        action = self.console(
            events,
            keys={pygame.K_RETURN: 'done', pygame.K_ESCAPE: 'done'},
            title="CALLSIGN",
            lines=["ENTER PILOT DESIGNATION:", self.session.callsign + blink_cursor()],
            buttons=[("CONFIRM", "ENTER", 'done')],
            header="ERGOT SYSTEMS // CALLSIGN EDITOR")
        return action


class IpScreen(Screen):
    """Types the server address. Returns 'connect' (with a non-empty address) or 'back'."""

    def __init__(self, session, draw_ui, audio):
        super().__init__(session, draw_ui, audio)
        self.ip_text = "127.0.0.1"

    def run(self, events, dt):
        self.ip_text = edit_text(events, self.ip_text, lambda c: c.isalnum() or c in '.-:', 60,
                                 self.typing_click)
        return self.console(
            events,
            keys={pygame.K_RETURN: 'connect', pygame.K_ESCAPE: 'back'},
            title="JOIN GAME",
            lines=["SERVER ADDRESS:", self.ip_text + blink_cursor()],
            buttons=[("CONNECT", "ENTER", 'connect'),
                     ("BACK", "ESC", 'back')],
            header="ERGOT SYSTEMS // NET LINK CONNECT",
            accept=lambda action: action != 'connect' or bool(self.ip_text.strip()))

    @property
    def address(self):
        return self.ip_text.strip()


class LobbyScreen(Screen):
    """Contacting the server, then the lobby until the host launches.
    Returns 'cancel' (we left), 'refused' (no slot) or 'started' (session.world is ready)."""

    def run(self, events, dt):
        session = self.session
        net = session.net
        if net is None:  # no connection to wait on: we are not in a lobby
            return 'cancel'
        if net.welcomed:
            self.edit_callsign(events)

        for action in self.actions(events, {pygame.K_ESCAPE: 'cancel', pygame.K_RETURN: 'confirm',
                                            pygame.K_F5: 'launch'}):
            if action == 'cancel':
                return 'cancel'
            if action == 'confirm':
                session.commit_callsign()  # ENTER: the typed callsign goes out with our next hello
            if action == 'launch':
                session.launch()  # commits the callsign first

        if net.rejected:
            return 'refused'

        if session.poll_start():
            return 'started'

        if not net.welcomed:
            lines = [session.status]
            if net.timed_out:
                lines.append("NO CARRIER. CHECK ADDRESS / PORT FORWARD")
            self.draw_ui.draw_text_screen("ESTABLISHING LINK", lines, buttons=[("CANCEL", "ESC", 'cancel')],
                                          header="ERGOT SYSTEMS // SYS-LINK")
            return None

        self._draw_lobby()
        return None

    def _draw_lobby(self):
        session = self.session
        net = session.net
        lines = [f"CALLSIGN  {session.callsign}{blink_cursor()}  (ENTER TO CONFIRM)", "",
                 f"PILOTS ON NET: {len(net.roster)}"]
        roster = sorted(net.roster.items())
        for player_id, callsign in roster[:MAX_ROSTER_LINES]:
            you = "  < YOU" if player_id == net.player_id else "       "
            lines.append(f"{player_id:02d}  {callsign:<{CALLSIGN_MAX}}{you}")
        if len(roster) > MAX_ROSTER_LINES:
            lines.append(f"+{len(roster) - MAX_ROSTER_LINES} MORE")
        lines.append("")

        buttons = []
        if session.is_host:
            lines.append(f"HOSTING ON {session.host_address}")
            ready = session.can_launch
            buttons.append(("LAUNCH", "F5", 'launch', ready))
            if not ready:
                lines.append("NEED 2 OR MORE PILOTS TO LAUNCH")
        else:
            lines.append("AWAITING HOST LAUNCH")
        buttons.append(("LEAVE", "ESC", 'cancel'))
        self.draw_ui.draw_text_screen("FLIGHT LOBBY", lines, buttons=buttons,
                                      header="ERGOT SYSTEMS // PRE-FLIGHT DIAGNOSTICS")


class PlayScreen(Screen):
    """A game in progress. Returns 'lobby' (back to the lobby, connection kept),
    'menu' (leave) or 'lost' (the server stopped answering)."""

    def __init__(self, session, draw_ui, audio, scene):
        super().__init__(session, draw_ui, audio)
        self.scene = scene

    def run(self, events, dt):
        session = self.session
        net = session.net
        scene = self.scene
        if net:
            if net.timed_out:
                return 'lost'
            # The host has sent everyone back to the lobby. This applies even to a pilot
            # sitting on their own game over screen.
            if net.match != session.match_joined:
                return 'lobby'
            state = net.take_state()
            if state is not None:
                session.sync_world(state)
            scene.handle_world_events(net.take_events())

        scene.run(collect_inputs(), dt, events)

        # Game over screen: the host can take everyone back to the lobby (ENTER or the button);
        # everyone can go to the menu (ESC, the button, or ENTER for non-hosts)
        game_over = scene.end_tripped
        enter = key_pressed(events, pygame.K_RETURN)
        escape = key_pressed(events, pygame.K_ESCAPE)
        to_lobby = bool(net and session.is_host
                        and (scene.lobby_requested or (game_over and enter)))
        to_menu = scene.quit_requested or (game_over and (enter or escape))
        if to_lobby or to_menu:
            if to_lobby:
                net.report_match_over()
                return 'lobby'
            return 'menu'

        if net:
            net.send_command(scene.command)
        return None
