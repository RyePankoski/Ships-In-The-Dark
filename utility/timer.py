class Timer:
    """A stopwatch for timed effects, in seconds.

    start() begins counting from zero; arm() does the same only if not already
    running. update(dt) advances it and returns True on the frame it runs past its
    duration, after which it stops itself. `elapsed` counts up (effects that fade in);
    `remaining` counts down (effects that fade out).
    """

    def __init__(self, duration=0):
        self.duration = duration
        self.elapsed = 0.0
        self.running = False

    def start(self, duration=None):
        if duration is not None:
            self.duration = duration
        self.elapsed = 0.0
        self.running = True

    def change_duration(self, duration):
        self.duration = duration

    def arm(self):
        """Start unless already running, so repeated calls don't restart it."""
        if not self.running:
            self.start()

    def stop(self):
        self.elapsed = 0.0
        self.running = False

    def update(self, dt):
        if not self.running:
            return False
        self.elapsed += dt
        if self.elapsed > self.duration:
            self.stop()
            return True
        return False

    def is_running(self):
        return True if self.running else False

    @property
    def remaining(self):
        return max(0.0, self.duration - self.elapsed) if self.running else 0.0
