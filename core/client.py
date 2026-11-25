from .main_scene import MainScene
from .screens import CallsignScreen, IpScreen, LobbyScreen, MenuScreen, PlayScreen, WorldSettingsScreen
from .session import Session
from core.tutorial import Tutorial


class Client:
    """Picks the active screen and moves between them. Connection and world state live
    in the Session; everything a screen shows or reads lives in the screen."""

    def __init__(self, screen, draw_ui, audio_manager):
        self.screen = screen
        self.draw_ui = draw_ui
        self.audio = audio_manager
        self.audio.play_menu_audio()

        self.exit_requested = False  # set by the menu's QUIT; main.py exits the program
        self.session = Session()

        args = (self.session, draw_ui, audio_manager)
        self.menu_screen = MenuScreen(*args)
        self.callsign_screen = CallsignScreen(*args)
        self.ip_screen = IpScreen(*args)
        self.lobby_screen = LobbyScreen(*args)
        self.settings_screen = WorldSettingsScreen(*args)
        self.tutorial_screen = None
        self.play_screen = None  # a PlayScreen, built per game
        self.active = self.menu_screen
        self.tutorial = False

    def run(self, dt, events):
        """Run the active screen for one frame. Returns False when the screen chose an
        action (a transition), which means nothing was drawn this frame.

        Each branch is one screen: run it, and if it returned an action, hand that to
        the screen's after_ method, which decides where to go next."""
        self.session.update(dt)

        if self.active is self.menu_screen:
            action = self.menu_screen.run(events, dt)
            if action:
                self.after_menu(action)

        elif self.active is self.callsign_screen:
            action = self.callsign_screen.run(events, dt)
            if action:
                self.after_callsign()

        elif self.active is self.ip_screen:
            action = self.ip_screen.run(events, dt)
            if action:
                self.after_ip(action)

        elif self.active is self.lobby_screen:
            action = self.lobby_screen.run(events, dt)
            if action:
                self.after_lobby(action)

        elif self.active is self.settings_screen:
            action = self.settings_screen.run(events, dt)
            if action:
                self.after_settings()

        elif self.active is self.play_screen:
            action = self.play_screen.run(events, dt)
            if action:
                self.after_play(action)

        else:
            raise RuntimeError(f"Client.run has no branch for screen {self.active!r}")

        return not action

    def after_menu(self, action):
        session = self.session
        if action == 'single':
            self.start_game(session.start_match('single'))
        elif action == 'host':
            self.active = self.lobby_screen if session.host() else self.menu_screen
        elif action == 'join':
            self.active = self.ip_screen
        elif action == 'callsign':
            self.active = self.callsign_screen
        elif action == 'tutorial':
            self.start_game(session.start_match('tutorial'), tutorial=True)
        elif action == 'quit':
            self.exit_requested = True  # main.py owns the actual shutdown

    def after_callsign(self):
        self.session.commit_callsign()  # every way out of this screen confirms the name
        self.active = self.menu_screen

    def after_ip(self, action):
        if action == 'connect':
            self.session.join(self.ip_screen.address)
            self.active = self.lobby_screen
        else:
            self.active = self.menu_screen

    def after_lobby(self, action):
        self.session.commit_callsign()  # every way out of this screen confirms the name
        if action == 'started':
            self.start_game(self.session.config)
        elif action == 'refused':
            self.leave("LINK REFUSED: NO FREE SLOT")
        elif action == 'settings':
            self.active = self.settings_screen
        else:
            self.leave()

    def after_settings(self):
        self.active = self.lobby_screen

    def after_play(self, action):
        if action == 'lobby':
            self.play_screen = None
            self.session.end_game()
            self.active = self.lobby_screen
        elif action == 'lost':
            self.leave("CARRIER LOST")
        else:
            self.leave()
        # Every exit from a game lands on the menu or lobby, so the menu audio is set here
        # and nowhere else. play_menu_audio() stops whatever the game was playing first.
        self.audio.play_menu_audio()

    def start_game(self, config, tutorial=False):
        scene = MainScene(self.screen, self.audio, self.session.world, config, self.draw_ui)
        lesson = Tutorial(self.audio, self.draw_ui, self.session, scene) if tutorial else None
        self.play_screen = PlayScreen(self.session, self.draw_ui, self.audio, scene, lesson)
        self.active = self.play_screen

    def leave(self, status=""):
        self.play_screen = None
        self.session.leave(status)
        self.active = self.menu_screen
