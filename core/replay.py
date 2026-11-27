import math

from config.constants import BLINK_RECORD_MARK, POSITION_RECORD_SECONDS

# Samples per second while playing. One sample is POSITION_RECORD_SECONDS of flight.
PLAYBACK_SAMPLES_PER_SECOND = 2.0


def record_flights(world, dt):
    for ship in world.ships:
        if ship.was_blinking and not ship.blinking:
            ship.position_record.append(BLINK_RECORD_MARK)
        ship.was_blinking = ship.blinking
        ship.record_position(dt)


class ReplayState:
    def __init__(self, world):
        self.asteroids = list(world.asteroids)
        self.width = world.width
        self.height = world.height
        # Copies: the records are ours to show now, even if the world is replaced later
        self.pilots = [(world.callsigns.get(ship.player_id, f"PILOT-{ship.player_id}"), list(ship.position_record))
                       for ship in world.ships]
        self.last_sample = max((len(path) for _, path in self.pilots), default=1) - 1
        self.progress = 0.0
        self.playing = False

    def update(self, dt):
        if not self.playing:
            return
        self.progress = min(self.progress + dt * PLAYBACK_SAMPLES_PER_SECOND, self.last_sample)
        if self.progress >= self.last_sample:
            self.playing = False

    def play_pause(self):
        if self.progress >= self.last_sample:
            self.progress = 0.0  # a finished replay starts again from the top
        self.playing = not self.playing

    def step_forward(self):
        self.playing = False
        self.progress = min(math.floor(self.progress) + 1, self.last_sample)

    def step_back(self):
        self.playing = False
        self.progress = max(math.ceil(self.progress) - 1, 0)
