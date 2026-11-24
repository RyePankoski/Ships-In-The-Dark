import time

from netcode.network_layer import NetworkLayer
from config.constants import *
from simulation.settings import WorldSettings

HELLO_INTERVAL = 0.5
TIMEOUT = 5.0


class NetClient:
    """The client's side of the conversation with the server.

    Knows nothing about the game: it says hello (with our callsign) until it's
    welcomed and as a heartbeat after, keeps the newest state the server sent, and
    sends commands (resending one-off actions until the server acknowledges them).
    """

    def __init__(self, server_ip, callsign="", port=PORT):
        self.server_address = (server_ip, port)
        self.network = NetworkLayer(server=False)
        self.network.start()

        self.callsign = callsign  # what we'd like to be called; the server has the final say

        self.player_id = None
        self.seed = None
        self.settings = WorldSettings()  # the world's parameters, as the server last said them
        self.rejected = False

        self.latest_state = None
        self.latest_tick = -1
        self.has_new_state = False

        # World events not yet handed to the game, and the newest id seen
        self.pending_events = []
        self.last_event_id = 0

        # player_id -> callsign, and which version of it the server sent
        self.roster = {}
        self.roster_version = 0

        # Destroyed asteroid ids not yet handed to the game, and how many of the
        # server's list we have (told back to the server so it stops resending)
        self.pending_dead = []
        self.dead_known = 0

        self.input_seq = 0
        self.next_action_id = 1
        self.unacked_actions = []

        # Which match the server is running. Bumps when it goes back to the lobby.
        self.match = 0
        # Set when our game ends; we keep telling the server until it moves on
        self.match_over_pending = False
        self.since_report = HELLO_INTERVAL

        self.since_sent = HELLO_INTERVAL  # say hello on the first update
        self.last_heard = time.monotonic()

    @property
    def welcomed(self):
        return self.player_id is not None

    @property
    def timed_out(self):
        return time.monotonic() - self.last_heard > TIMEOUT

    def update(self, dt):
        # Hello until welcomed, then as a keep-alive whenever no input is going out
        # (in the lobby, or if the game stops sending for a moment)
        self.since_sent += dt
        if self.since_sent >= HELLO_INTERVAL:
            self.send({'type': 'hello', 'callsign': self.callsign})

        if self.match_over_pending:
            self.since_report += dt
            if self.since_report >= HELLO_INTERVAL:
                self.since_report = 0.0
                self.send({'type': 'match_over'})

        for message, address in self.network.receive_all():
            if address[1] != self.server_address[1]:
                continue
            self.last_heard = time.monotonic()
            kind = message.get('type')

            if kind == 'welcome':
                self.player_id = message['player_id']
                self.seed = message['seed']
            elif kind == 'full':
                self.rejected = True
            elif kind == 'state' and self.welcomed:
                self.receive_state(message)

    def report_match_over(self):
        """Our game ended. Tell the server (repeatedly, until it has gone back to the lobby)."""
        self.match_over_pending = True
        self.since_report = HELLO_INTERVAL

    def set_settings(self, settings):
        """Host only (the server ignores everyone else): ask for new world parameters in the lobby.
        Shown straight away; the server's next state confirms or corrects it."""
        self.settings = settings
        self.send({'type': 'settings', 'settings': settings.to_wire()})

    def receive_state(self, message):
        match = message.get('match', 0)
        if match < self.match:
            return  # left over from a match that has already ended
        if 'settings' in message:
            self.settings = WorldSettings.from_wire(message['settings'])
        if match > self.match:
            # A new match: its world, tick and asteroid log all start again
            self.match = match
            self.seed = message.get('seed', self.seed)
            self.match_over_pending = False
            self.latest_tick = -1
            self.pending_events = []
            self.pending_dead = []
            self.dead_known = 0

        # Events, the roster and dead asteroids are taken from every state that
        # arrives, even one that's out of order or superseded before the game
        # reads it, so none of them can be lost.
        for event_id, *event in message.get('events', []):
            if event_id > self.last_event_id:
                self.last_event_id = event_id
                self.pending_events.append(tuple(event))

        if 'roster' in message:
            version, entries = message['roster']
            if version > self.roster_version:
                self.roster_version = version
                self.roster = {pid: callsign for pid, callsign in entries}

        if 'dead' in message:
            start, *ids = message['dead']
            if start <= self.dead_known < start + len(ids):
                new = ids[self.dead_known - start:]
                self.pending_dead.extend(new)
                self.dead_known += len(new)

        ack = message.get('ack', 0)
        self.unacked_actions = [a for a in self.unacked_actions if a['aid'] > ack]

        # UDP can deliver out of order: the world state only ever moves forward
        if message['tick'] < self.latest_tick:
            return
        self.latest_tick = message['tick']
        self.latest_state = message
        self.has_new_state = True

    def take_state(self):
        """The newest state, once. None if nothing new arrived since last time."""
        if not self.has_new_state:
            return None
        self.has_new_state = False
        return self.latest_state

    def take_events(self):
        """World events received since last call, each once, as (kind, *data)."""
        events, self.pending_events = self.pending_events, []
        return events

    def take_dead_asteroids(self):
        """Asteroid ids destroyed since last call, each once."""
        dead, self.pending_dead = self.pending_dead, []
        return dead

    def send_command(self, command):
        for action in command['actions']:
            self.unacked_actions.append(dict(action, aid=self.next_action_id))
            self.next_action_id += 1

        self.input_seq += 1
        self.send({
            'type': 'input',
            'seq': self.input_seq,
            'move': command['move'],
            'laser_target': command['laser_target'],
            'power': command['power'],
            'actions': self.unacked_actions,
        })

    def send(self, message):
        # Every packet tells the server what we already have, so it can stop resending
        message['rv'] = self.roster_version
        message['dk'] = self.dead_known
        message['m'] = self.match
        self.network.send(message, self.server_address)
        self.since_sent = 0

    def close(self):
        self.network.close()
