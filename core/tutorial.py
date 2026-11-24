class Tutorial:
    def __init__(self, audio_manager, draw_ui, session, main_scene):
        self.audio = audio_manager
        self.draw = draw_ui
        self.session = session
        self.main_scene = main_scene

        self.STEPS = [
            "WELCOME PILOT TO THE ERGOT SYSTEM REMOTE DRONE SYSTEM."
        ]

        self.index = 0

    def run(self):




        self.draw.draw_viewport_banner(self.STEPS[self.index])


    def set_draw_flags(self):
        if self.index == 0:
            self.main_scene.draw_ui



