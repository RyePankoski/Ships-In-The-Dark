from .main_scene import MainScene
from .screens import CallsignScreen, IpScreen, LobbyScreen, MenuScreen, PlayScreen, WorldSettingsScreen
from .session import Session

# Screens where the player types a callsign. Leaving any of them commits it once, here,
# so a new exit path cannot skip the commit.
COMMIT_CALLSIGN_ON_EXIT = (CallsignScreen, LobbyScreen)


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
        self.play_screen = None  # a PlayScreen, built per game
        self.active = self.menu_screen

        # Which method handles the action a screen returns, keyed by screen type.
        self.transitions = {
            MenuScreen: self.after_menu,
            CallsignScreen: self.after_callsign,
            IpScreen: self.after_ip,
            LobbyScreen: self.after_lobby,
            WorldSettingsScreen: self.after_settings,
            PlayScreen: self.after_play,
        }

    def run(self, dt, events):
        """Run the active screen for one frame. Returns False when the screen chose an
        action (a transition), which means nothing was drawn this frame."""
        self.session.update(dt)

        action = self.active.run(events, dt)
        if action:
            self.handle(self.active, action)
            return False
        return True

    def handle(self, screen, action):
        """Move on from `screen` given the action it returned."""
        if isinstance(screen, COMMIT_CALLSIGN_ON_EXIT):
            self.session.commit_callsign()  # every way out of these screens confirms the name
        self.transitions[type(screen)](action) # noqa

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
        elif action == 'quit':
            self.exit_requested = True  # main.py owns the actual shutdown

    def after_callsign(self, action):
        self.active = self.menu_screen

    def after_ip(self, action):
        if action == 'connect':
            self.session.join(self.ip_screen.address)
            self.active = self.lobby_screen
        else:
            self.active = self.menu_screen

    def after_lobby(self, action):
        if action == 'started':
            self.start_game(self.session.config)
        elif action == 'refused':
            self.leave("LINK REFUSED: NO FREE SLOT")
        elif action == 'settings':
            self.active = self.settings_screen
        else:
            self.leave()

    def after_settings(self, action):
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

    def start_game(self, config):
        scene = MainScene(self.screen, self.audio, self.session.world, my_id=config.my_id, local=config.local,
                          draw_ui=self.draw_ui, is_host=config.is_host)
        self.play_screen = PlayScreen(self.session, self.draw_ui, self.audio, scene)
        self.active = self.play_screen

    def leave(self, status=""):
        self.play_screen = None
        self.session.leave(status)
        self.active = self.menu_screen
