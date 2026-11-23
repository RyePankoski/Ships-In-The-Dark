import pygame

from asset_handlers.draw_ui import DrawUI
from utility.common import blink_cursor, edit_text


class Menu:
    def __init__(self, screen, audio_manager):
        self.draw_ui = DrawUI(screen)
        self.ip_text = "127.0.0.1"
        self.audio = audio_manager  # the Client's, so there's only one

    def menu_actions(self, events, keys):
        """Actions chosen this frame on a menu screen: clicked buttons, plus
        key presses looked up in `keys` ({pygame key: action})."""
        actions = self.draw_ui.buttons.clicked_actions(events)
        if actions:
            self.audio.play_sfx('keyboard_clack', force=True)
        for event in events:
            if event.type == pygame.KEYDOWN and event.key in keys:
                actions.append(keys[event.key])

        return actions

    def screen(self, events, keys, title, lines, buttons, header, footer="", accept=None):
        """One console screen: the first action chosen this frame, or draw it and return None.
        `accept(action)` can veto an action (e.g. connect with no address)."""
        for action in self.menu_actions(events, keys):
            if accept is None or accept(action):
                return action

        self.draw_ui.draw_text_screen(title, lines, footer=footer, header=header, buttons=buttons)
        return None

    def main_screen(self, events, callsign, status):
        """Returns 'single', 'host', 'join', 'callsign' or 'quit' when one is chosen."""
        keys = {pygame.K_s: 'single', pygame.K_h: 'host', pygame.K_j: 'join', pygame.K_c: 'callsign',
                pygame.K_q: 'quit'}
        buttons = [("SINGLE PLAYER", "S", 'single'),
                   ("HOST GAME", "H", 'host'),
                   ("JOIN GAME", "J", 'join'),
                   ("CHANGE CALLSIGN", "C", 'callsign'),
                   ("QUIT", "Q", 'quit')]
        for action in self.menu_actions(events, keys):
            return action

        self.draw_ui.draw_main_menu("SHIPS IN THE DARK", callsign, buttons, footer=status)
        return None

    def callsign_screen(self, events, callsign):
        """Returns 'done' when confirmed. The Client does the typing (it is shared with the lobby)."""
        return self.screen(
            events,
            keys={pygame.K_RETURN: 'done', pygame.K_ESCAPE: 'done'},
            title="CALLSIGN",
            lines=["ENTER PILOT DESIGNATION:", callsign + blink_cursor()],
            buttons=[("CONFIRM", "ENTER", 'done')],
            header="ERGOT SYSTEMS // CALLSIGN EDITOR")

    def ip_screen(self, events):
        """Types the server address. Returns 'connect' (with a non-empty address) or 'back'."""
        self.ip_text = edit_text(events, self.ip_text, lambda c: c.isalnum() or c in '.-:', 60)

        return self.screen(
            events,
            keys={pygame.K_RETURN: 'connect', pygame.K_ESCAPE: 'back'},
            title="JOIN GAME",
            lines=["SERVER ADDRESS:", self.ip_text + blink_cursor()],
            buttons=[("CONNECT", "ENTER", 'connect'),
                     ("BACK", "ESC", 'back')],
            header="ERGOT SYSTEMS // NET LINK CONNECT",
            accept=lambda action: action != 'connect' or bool(self.ip_text.strip()))
