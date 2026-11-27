import pygame
import pygame.constants
from utility.timer import Timer
from config.tutorial_messages import STEPS


class Tutorial:
    def __init__(self, audio_manager, draw_ui, session, main_scene):
        self.chimed = False
        self.audio = audio_manager
        self.draw = draw_ui
        self.session = session
        self.main_scene = main_scene
        self.text_timer = Timer()

        # Temp construct for debugging
        self.index = 0
        self.hide_unrevealed_panels()

        self.satisfied_inputs = {}
        self.required_inputs = []
        self.actions = []

        self.has_been_dfs_scanned = False

        self.splash = True

        if self.splash:
            self.audio.play_sfx('tutorial_splash')

    def run_tutorial(self, events, dt):
        if self.splash:
            if self.draw.draw_tutorial_splash(dt):
                self.splash = False
                return

        # self.main_scene.instrument_actions.append({'type': 'dfs_scan', 'targets': [1]})

        if STEPS[self.index][3] == 'menu':
            self.main_scene.outcome = 'menu'
            return

        self.main_scene.hud_hidden -= STEPS[self.index][2]
        self.apply_step_effects()
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

    # Hides every panel that some step reveals, then re-reveals those from steps already passed.
    def hide_unrevealed_panels(self):
        self.main_scene.hud_hidden = set()
        for _, _, reveals, _ in STEPS:
            self.main_scene.hud_hidden |= reveals

        for _, _, reveals, _ in STEPS[:self.index]:
            self.main_scene.hud_hidden -= reveals

    def apply_step_effects(self):

        if STEPS[self.index][3] == 'dfs_scan_player':
            if not self.has_been_dfs_scanned:
                self.main_scene.deep_field_scan.mark_scanned()
                self.has_been_dfs_scanned = True

        if STEPS[self.index][3] == 'set_low_fuel':
            self.main_scene.player_ship.fuel = 20
        if STEPS[self.index][3] == 'set_fuel_half':
            self.main_scene.player_ship.fuel = 200
        if STEPS[self.index][3] == 'set_fuel_normal':
            self.main_scene.player_ship.fuel = 500
        if STEPS[self.index][3] == 'show_certificate':
            self.draw.draw_certificate("New Hire")
            if not self.chimed:
                self.audio.play_sfx('tutorial_complete')
                self.chimed = True
