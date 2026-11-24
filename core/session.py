import math
import random
from dataclasses import dataclass

from netcode.net_client import NetClient
from netcode.network_layer import local_ip
from netcode.server import Server
from config.constants import SNAPSHOT_AGE, TICK_DT

MAX_TICKS_PER_FRAME = 5  # single player: the most steps one frame may run (as the server's cap)
from netcode.callsign import clean_callsign
from simulation.settings import WorldSettings
from simulation.snapshot import apply_snapshot
from simulation.world import World
from utility.profanity import check_for_profanity, REPLACEMENTS

CALLSIGN_WORDS = ("GHOST", "VIPER", "WRAITH", "NOMAD", "RAVEN", "JACKAL", "SPECTER",
                  "HALO", "ORBIT", "MOTH", "DEADBAND", "BLACKOUT", "GHOSTLINE", "NULL", "GRAVESHIFT",
                  "STATIC", "COLDWIRE", "REDSHIFT", "VANDAL",
                  "DEADLOCK", "NIGHTFALL", "IRONCLAD", "RATCHET", "PHANTOM",
                  "BLACKBOX", "ZERO HOUR", "CINDER", "OUTCAST",
                  "DUSTDEVIL", "BURNWIRE", "MEATLOCKER", "CROWBAR", "DARKSTAR",
                  "FALLOUT", "RUSTBUCKET", "MALFUNCTION", "HOLLOWPOINT", "GRIMJACK",
                  "WIDOWMAKER", "PAPERCLIP", "STATIC DOG", "REDLINE", "BONEYARD",
                  "SHOCKTROOPER", "ASHFALL", "CUTOFF", "DEATHWISH", "TINMAN"
                  )


@dataclass(frozen=True)
class MatchConfig:
    """Everything that differs between a single-player and an online match."""
    local: bool    # simulated entirely here (single player) rather than mirrored from a server
    my_id: int     # our ship's id in the world
    is_host: bool  # we run the server, so we decide when the match returns to the lobby

    @property
    def with_npcs(self):
        return self.local  # online, the server owns the NPCs


class Session:
    """Who we are and what we are connected to: the callsign, the (optional) server we
    host, our connection to it, and our copy of the world. Knows nothing about screens."""

    def __init__(self):
        self.callsign = f"{random.choice(CALLSIGN_WORDS)}-{random.randint(1, 9)}"
        self.status = ""  # last message to show on the main menu
        self.server = None
        self.net = None
        self.world = None
        self.match_joined = None  # the server's match number when our current game started
        self.config = None  # the MatchConfig of the game in progress
        self._queued_actions = []  # single player: one-off actions waiting for the next tick

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def update(self, dt):
        if self.server:
            self.server.run(dt)
        if self.net:
            self.net.update(dt)

    def host(self):
        """Start a server and join it. False (with self.status set) if it can't bind."""
        try:
            self.server = Server()
        except OSError as e:
            self.status = f"HOST FAULT: {str(e).upper()}"
            return False
        self.join('127.0.0.1')
        return True

    def join(self, ip):
        self.net = NetClient(ip, callsign=self.callsign)
        self.status = f"CONTACTING {ip} ..."

    def leave(self, status=""):
        if self.net:
            self.net.close()
        if self.server:
            self.server.close()
        self.net = self.server = self.world = self.config = None
        self.status = status

    def end_game(self):
        """Drop our copy of the world but keep the connection (and the server, if we host)."""
        self.world = self.config = None

    @property
    def is_host(self):
        return self.server is not None

    @property
    def can_launch(self):
        """We host and the server has enough pilots to start a match."""
        return bool(self.server and self.server.can_launch)

    def launch(self):
        """Ask our server to start the match (a no-op unless we host and can launch)."""
        self.commit_callsign()  # ENTER confirms the typed callsign for everyone, so it goes out first
        if self.server:
            self.server.launch()

    @property
    def settings(self):
        """The world parameters for the match being set up (the server's, once we are connected)."""
        return self.net.settings if self.net else WorldSettings()

    def change_setting(self, name):
        """Host: move one world parameter to its next option. Lobby only; the server decides."""
        if self.is_host and self.net:
            self.net.set_settings(self.settings.cycled(name))

    @property
    def host_address(self):
        """'LAN_IP:PORT' for other pilots to join, or None if we are not hosting."""
        if not self.server:
            return None
        return f"{local_ip()}:{self.server.network.port}"

    # ------------------------------------------------------------------
    # Callsign
    # ------------------------------------------------------------------
    def set_callsign(self, text):
        """Take the callsign as the screen has typed it (stored upper case)."""
        self.callsign = text.upper()

    def commit_callsign(self):
        """Call when the player is done typing: swap a profane name, tidy it, and tell the server."""
        if check_for_profanity(self.callsign):
            self.callsign = random.choice(REPLACEMENTS)
        self.callsign = clean_callsign(self.callsign)
        if self.net:
            self.net.callsign = self.callsign

    # ------------------------------------------------------------------
    # World
    # ------------------------------------------------------------------
    def start_match(self, mode, state=None):
        """Build our world for a new match and return its MatchConfig.
        mode 'single': simulate locally. mode 'online': mirror the server, from its first `state`."""
        self._queued_actions = []
        if mode == 'single':
            config = MatchConfig(local=True, my_id=1, is_host=False)
            self.world = World(random.randrange(2 ** 31), with_npcs=config.with_npcs)
            self.world.setup_single_player(self.callsign)
        elif mode == 'online':
            config = MatchConfig(local=False, my_id=self.net.player_id, is_host=self.is_host)
            self.world = World(self.net.seed, with_npcs=config.with_npcs, settings=self.net.settings)
            self.sync_world(state)
            self.match_joined = self.net.match
        else:
            raise ValueError(f"unknown match mode: {mode}")
        self.config = config
        return config

    def step(self, command, dt):
        """Advance our copy of the match by one frame; return the events it produced for us.

        Single player: the World is stepped every frame by the frame's own time, so what is
        drawn moves as smoothly as the frame rate. (Stepping at the server's TICK_RATE would
        show each world state for several frames, which looks like a third of the frame rate.)
        A long frame is split into steps no longer than TICK_DT, as the server would take them.
        One-off actions go on the first step only.
        Multiplayer: the World only predicts our own ship's motion; the server sends the rest.
        """
        my_id = self.config.my_id
        if not self.config.local:
            self.world.predict(my_id, command, dt)
            return []

        self._queued_actions.extend(command.get('actions', []))
        if dt <= 0:
            return []
        steps = min(MAX_TICKS_PER_FRAME, max(1, math.ceil(dt / TICK_DT - 1e-9)))
        step_dt = min(dt, MAX_TICKS_PER_FRAME * TICK_DT) / steps  # fell badly behind: don't catch up
        events = []
        for _ in range(steps):
            actions, self._queued_actions = self._queued_actions, []
            self.world.step({my_id: {**command, 'actions': actions}}, step_dt)
            # No server here, so this world is the authority on how the match stands
            self.world.outcome = self.world.outcome_for(my_id)
            events += self.world.events
            events += [event for audience, event in self.world.private_events
                       if audience is None or my_id in audience]
            if self.world.outcome != 'playing':
                break
        return events

    def poll_start(self):
        """True once the server has started a new match and we have started it from its first state."""
        net = self.net
        state = net.take_state()
        # While our last game's end is still being reported, a 'started' state is the old match
        if net.welcomed and state is not None and state['started'] and not net.match_over_pending:
            self.start_match('online', state)
            return True
        return False

    def sync_world(self, state):
        """Bring our copy of the world up to date with what the server sent."""
        net = self.net
        apply_snapshot(self.world, state, age=SNAPSHOT_AGE, my_id=net.player_id)
        self.world.time = state['tick'] * TICK_DT
        # The server's verdict for us; the client only displays it
        self.world.outcome = state.get('outcome', 'playing')
        self.world.remove_asteroids(net.take_dead_asteroids())
        if self.world.callsigns != net.roster:
            self.world.callsigns = dict(net.roster)
