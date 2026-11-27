import pygame
import pygame.constants
from utility.timer import Timer
from config.tutorial import STEPS


class Tutorial:
    def __init__(self, audio_manager, draw_ui, session, main_scene):
        self.audio = audio_manager
        self.draw = draw_ui
        self.session = session
        self.main_scene = main_scene
        self.text_timer = Timer()

        # Temp construct for debugging
        self.index = 0
        self.set_draw_flags()
        self.index = 0
        self.main_scene.player_ship.fuel = 10000

        self.satisfied_inputs = {}
        self.required_inputs = []
        self.actions = []

        self.splash = True

        if self.splash:
            self.audio.play_sfx('tutorial_splash')

    def run_tutorial(self, events, dt):

        if self.splash:
            if self.draw.draw_tutorial_splash(dt):
                self.splash = False
                return

        # self.main_scene.instrument_actions.append({'type': 'dfs_scan', 'targets': [1]})

        if self.index == 69:
            self.main_scene.outcome = 'menu'

        self.set_draw_flags()
        self.check_current_step(events, dt)
        self.draw.draw_viewport_banner(STEPS[self.index][0])

    def check_current_step(self, events, dt):

        required_inputs = STEPS[self.index][1]

        if required_inputs is None:
            self.timed_messages(dt)
        elif not self.satisfied_inputs:
            self.satisfied_inputs = {key: False for key in required_inputs}

        if self.satisfied_inputs:
            for event in events:
                if event.type == pygame.KEYDOWN and event.key in self.satisfied_inputs:
                    self.satisfied_inputs[event.key] = True

            if all(self.satisfied_inputs.values()):
                self.index += 1
                self.audio.play_sfx('tutorial_proceed')
                self.satisfied_inputs = {}
                print(self.index)

    def timed_messages(self, dt):
        if self.text_timer.is_running() is False:
            self.text_timer.start(3.5)

        if self.text_timer.update(dt):
            self.index += 1

            self.audio.play_sfx('tutorial_proceed')

    def set_draw_flags(self):
        # Each index sets the full list of HUD panels still hidden from that step on.
        # Index 0 hides everything; each later index removes the panel its message introduces.
        if self.index == 0:
            self.main_scene.hud_hidden = {'power', 'navcom', 'cloaking', 'ship_info', 'radar', 'dfs', 'laser', 'material',
                                          'fire_missile', 'decoy', 'blink', 'toggle_dampening', 'silent', 'toggle_vectors',
                                          'toggle_prox_scan', 'toggle_dfs_alert', 'toggle_mining', 'toggle_range_bands'}
        if self.index == 10:
            self.main_scene.hud_hidden = {'power', 'navcom', 'cloaking', 'ship_info', 'radar', 'dfs', 'laser', 'material',
                                          'fire_missile', 'decoy', 'blink', 'toggle_dampening', 'silent',
                                          'toggle_prox_scan', 'toggle_dfs_alert', 'toggle_mining', 'toggle_range_bands'}
        if self.index == 12:
            self.main_scene.hud_hidden = {'power', 'navcom', 'cloaking', 'ship_info', 'radar', 'dfs', 'laser', 'material',
                                          'fire_missile', 'decoy', 'blink', 'silent',
                                          'toggle_prox_scan', 'toggle_dfs_alert', 'toggle_mining', 'toggle_range_bands'}
        if self.index == 14:
            self.main_scene.hud_hidden = {'power', 'cloaking', 'ship_info', 'radar', 'dfs', 'laser', 'material',
                                          'fire_missile', 'decoy', 'blink', 'silent',
                                          'toggle_prox_scan', 'toggle_dfs_alert', 'toggle_mining', 'toggle_range_bands'}
        if self.index == 15:
            self.main_scene.hud_hidden = {'cloaking', 'ship_info', 'radar', 'dfs', 'laser', 'material',
                                          'fire_missile', 'decoy', 'blink', 'silent',
                                          'toggle_prox_scan', 'toggle_dfs_alert', 'toggle_mining', 'toggle_range_bands'}

        if self.index == 17:
            self.main_scene.player_ship.fuel = 20
        if self.index == 18:
            self.main_scene.player_ship.fuel = 500
            self.main_scene.hud_hidden = {'cloaking', 'ship_info', 'dfs', 'laser', 'material',
                                          'fire_missile', 'decoy', 'blink', 'silent',
                                          'toggle_prox_scan', 'toggle_dfs_alert', 'toggle_mining', 'toggle_range_bands'}
        if self.index == 23:
            self.main_scene.hud_hidden = {'cloaking', 'ship_info', 'dfs', 'laser', 'material',
                                          'fire_missile', 'decoy', 'blink', 'silent',
                                          'toggle_prox_scan', 'toggle_dfs_alert', 'toggle_mining'}
        if self.index == 24:
            self.main_scene.hud_hidden = {'cloaking', 'ship_info', 'dfs', 'material',
                                          'fire_missile', 'decoy', 'blink', 'silent',
                                          'toggle_prox_scan', 'toggle_dfs_alert', 'toggle_mining'}
        if self.index == 29:
            self.main_scene.hud_hidden = {'cloaking', 'ship_info', 'dfs',
                                          'fire_missile', 'decoy', 'blink', 'silent',
                                          'toggle_prox_scan', 'toggle_dfs_alert', 'toggle_mining'}

        if self.index == 34:
            self.main_scene.hud_hidden = {'cloaking', 'ship_info', 'dfs',
                                          'decoy', 'blink', 'silent',
                                          'toggle_prox_scan', 'toggle_dfs_alert', 'toggle_mining'}
        if self.index == 39:
            self.main_scene.hud_hidden = {'cloaking', 'ship_info', 'dfs',
                                          'decoy', 'blink', 'silent',
                                          'toggle_dfs_alert', 'toggle_mining'}
        if self.index == 40:
            self.main_scene.hud_hidden = {'cloaking', 'dfs',
                                          'decoy', 'blink', 'silent',
                                          'toggle_dfs_alert', 'toggle_mining'}
        if self.index == 43:
            self.main_scene.hud_hidden = {'cloaking',
                                          'decoy', 'blink', 'silent',
                                          'toggle_dfs_alert', 'toggle_mining'}
        if self.index == 49:
            self.main_scene.hud_hidden = {'cloaking',
                                          'decoy', 'blink', 'silent',
                                          'toggle_mining'}
        if self.index == 51:
            self.main_scene.hud_hidden = {'decoy', 'blink', 'silent', 'toggle_mining'}
        if self.index == 56:
            self.main_scene.hud_hidden = {'blink', 'silent', 'toggle_mining'}
        if self.index == 61:
            self.main_scene.hud_hidden = {'silent', 'toggle_mining'}
        if self.index == 63:
            self.main_scene.hud_hidden = {'toggle_mining'}
        if self.index == 64:
            self.main_scene.hud_hidden = set()

        if self.index == 68:
            self.draw.draw_certificate("New Hire")
