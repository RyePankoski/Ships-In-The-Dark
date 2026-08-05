from utility.util import end_blit
from .client import Client  # noqa
from asset_handlers.draw_menus_etc import DrawMenusEtc


class Core:
    def __init__(self, screen):
        self.draw_menus_etc = DrawMenusEtc(screen)
        self.client = Client(screen)
        self.screen = screen

        self.splash_screen_timer = 0
        self.splash_screen_duration = 5
        self.splashing = False

    def run(self, dt):
        self.timer(dt)

        if self.splashing:
            self.draw_stuff()
        else:
            self.client.run(dt)

    def draw_stuff(self):
        self.screen.fill((0, 0, 0))
        self.draw_menus_etc.draw_splash_screen(self.splashing, self.splash_screen_timer)
        end_blit()

    def timer(self, dt):
        if self.splashing:
            self.splash_screen_timer += dt
            if self.splash_screen_timer > self.splash_screen_duration:
                self.splashing = False
