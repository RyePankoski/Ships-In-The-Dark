from utility.common import end_blit, collect_inputs
from .client import Client  # noqa
from asset_handlers.draw_ui import DrawUI
from asset_handlers.audio_manager import AudioManager

SPLASH_SCREEN_DURATION = 5


class Core:
    def __init__(self, screen):
        self.screen = screen
        self.draw = DrawUI(screen)
        self.client = Client(screen)
        self.splashing = False
        self.splash_screen_timer = 0
        self.audio = AudioManager()

    def run(self, dt, events=()):
        if self.splashing:
            self.splash(dt)
            return
        else:
            self.client.run(dt, events)

    def splash(self, dt):
        inputs = collect_inputs()
        if self.splashing:
            self.splash_screen_timer += dt
            if self.splash_screen_timer > SPLASH_SCREEN_DURATION:
                if inputs['enter']:
                    self.splashing = False
                    self.audio.play_sfx('keyboard_clack')

        self.screen.fill((0, 0, 0))
        self.draw.draw_splash_screen(self.splashing, self.splash_screen_timer)
        end_blit()
