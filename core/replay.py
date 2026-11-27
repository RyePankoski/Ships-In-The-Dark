import math

from config.constants import BLINK_RECORD_MARK, POSITION_RECORD_SECONDS

# Samples per second while playing. One sample is POSITION_RECORD_SECONDS of flight.
PLAYBACK_SAMPLES_PER_SECOND = 2.0


def record_flights(world, dt):
    """Called once a frame on every machine, whatever the mode. Each ship takes a
    position sample when its own timer runs out. A blink's jump happens when its charge
    ends (the flag drops), so that is where the mark goes: after the last sample from
    before the jump, before any sample from after it. Clients never simulate the ships
    (the snapshots move them), so this is where a client's flight record comes from."""
    for ship in world.ships:
        if ship.was_blinking and not ship.blinking:
            ship.position_record.append(BLINK_RECORD_MARK)
        ship.was_blinking = ship.blinking
        ship.record_position(dt)


class ReplayState:
    """The after-action replay: a copy of every pilot's flight record, and how far
    through those records the replay has got.

    `progress` is in samples (sample n is about n * POSITION_RECORD_SECONDS into the
    flight). MainScene owns one while the replay is on screen, steps it from the
    buttons and keys, and draws it through DrawUI.draw_replay_map.
    """

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
