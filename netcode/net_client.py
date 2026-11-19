import time

from netcode.network_layer import NetworkLayer
from utility.constants import *

HELLO_INTERVAL = 0.5
TIMEOUT = 5.0


class NetClient:
    """The client's side of the conversation with the server.

    Knows nothing about the game: it says hello until it's welcomed, keeps the
    newest state the server sent, and sends commands (resending one-off actions
    until the server acknowledges them).
    """

    def __init__(self, server_ip, port=PORT):
        self.server_address = (server_ip, port)
        self.network = NetworkLayer(server=False)
        self.network.start()

        self.player_id = None
        self.seed = None
        self.rejected = False

        self.latest_state = None
        self.latest_tick = -1
        self.has_new_state = False

        # World events not yet handed to the game, and the newest id seen
        self.pending_events = []
        self.last_event_id = 0

        self.input_seq = 0
        self.next_action_id = 1
        self.unacked_actions = []

        self.hello_timer = HELLO_INTERVAL  # say hello on the first update
        self.last_heard = time.monotonic()

    @property
    def welcomed(self):
        return self.player_id is not None

    @property
    def timed_out(self):
        return time.monotonic() - self.last_heard > TIMEOUT

    def update(self, dt):
        if not self.welcomed:
            self.hello_timer += dt
            if self.hello_timer >= HELLO_INTERVAL:
                self.hello_timer = 0
                self.network.send({'type': 'hello'}, self.server_address)

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
                # UDP can deliver out of order: only ever move forward
                if message['tick'] < self.latest_tick:
                    continue
                self.latest_tick = message['tick']
                self.latest_state = message
                self.has_new_state = True
                # Collected per message (not per take_state) so events in a state
                # that gets superseded before the game reads it still arrive.
                for event_id, *event in message.get('events', []):
                    if event_id > self.last_event_id:
                        self.last_event_id = event_id
                        self.pending_events.append(tuple(event))
                ack = message.get('ack', 0)
                self.unacked_actions = [a for a in self.unacked_actions if a['aid'] > ack]

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

    def send_command(self, command):
        for action in command['actions']:
            self.unacked_actions.append(dict(action, aid=self.next_action_id))
            self.next_action_id += 1

        self.input_seq += 1
        self.network.send({
            'type': 'input',
            'seq': self.input_seq,
            'move': command['move'],
            'laser_target': command['laser_target'],
            'actions': self.unacked_actions,
        }, self.server_address)

    def close(self):
        self.network.close()
