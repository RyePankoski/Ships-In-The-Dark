import pygame

from utility.input import key_pressed
from asset_handlers.crt import crt
from .client import Client
from asset_handlers.draw_ui import DrawUI
from asset_handlers.audio_manager import AudioManager

SPLASH_SCREEN_DURATION = 5


class Core:
    def __init__(self, screen):
        self.screen = screen
        self.draw = DrawUI(screen)
        self.audio = AudioManager()
        self.client = Client(screen, self.draw, self.audio)
        self.splashing = False
        self.splash_screen_timer = 0

    @property
    def exit_requested(self):
        return self.client.exit_requested

    def run(self, dt, events=()):
        self.screen.fill((0, 0, 0))

        if self.splashing:
            self.splash(dt, events)
        elif not self.client.run(dt, events):
            # A screen changed this frame and drew nothing. Skip the flip so the window
            # keeps the last frame instead of flashing black for one tick.
            return

        crt.apply(self.screen)
        pygame.display.flip()

    def splash(self, dt, events=()):
        self.splash_screen_timer += dt
        if self.splash_screen_timer > SPLASH_SCREEN_DURATION:
            if key_pressed(events, pygame.K_RETURN):
                self.splashing = False
                self.audio.play_sfx('keyboard_clack')

        self.draw.draw_splash_screen(self.splashing, self.splash_screen_timer)
