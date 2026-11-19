import random
import time

from netcode.network_layer import NetworkLayer
from simulation.snapshot import make_snapshot
from simulation.world import World
from utility.constants import *

TICK_DT = 1 / TICK_RATE
MAX_STEPS_PER_RUN = 5
# World events (hits, damage) are resent in every state for this many ticks, so a
# dropped packet doesn't lose one. Clients skip ids they've already handled.
EVENT_RESEND_TICKS = TICK_RATE // 2


class PlayerSlot:
    def __init__(self, player_id):
        self.player_id = player_id
        self.move = None            # latest held movement keys
        self.laser_target = None
        self.last_seq = -1          # newest input packet seen (older ones are ignored)
        self.last_action_id = 0     # newest action accepted (sent back as 'ack')
        self.queued_actions = []    # accepted, waiting for the next tick
        self.last_heard = time.monotonic()


class Server:
    """Owns the real World. Players send inputs, the server steps, everyone gets the result.

    Protocol (JSON over UDP, see also netcode/net_client.py):
      client -> server  {'type': 'hello'}
                        {'type': 'input', 'seq', 'move', 'laser_target', 'actions': [... each with 'aid']}
      server -> client  {'type': 'welcome', 'player_id', 'seed'}
                        {'type': 'full'}
                        {'type': 'state', 'tick', 'started', 'players', 'ack', 'events', ...snapshot}

    Actions (fire, decoy, blink) are resent by the client until the server acks
    them, so a dropped packet can't eat a missile launch. In the other direction,
    world events ([event_id, kind, *data]) are resent for EVENT_RESEND_TICKS.
    """

    def __init__(self, port=PORT, max_players=2):
        self.network = NetworkLayer(server=True, port=port)
        self.network.start()

        self.max_players = max_players
        self.seed = random.randrange(2 ** 31)
        self.world = World(self.seed, with_npcs=False)
        self.players = {}  # address -> PlayerSlot

        self.started = False
        self.tick = 0
        self.accumulator = 0.0

        self.recent_events = []  # (tick, [event_id, kind, *data])
        self.next_event_id = 1

    def run(self, dt):
        for message, address in self.network.receive_all():
            self.handle_message(message, address)

        if not self.started and len(self.players) == self.max_players:
            self.started = True
            print("[SERVER] All players in, starting")

        if self.started:
            self.accumulator += dt
            steps = 0
            while self.accumulator >= TICK_DT and steps < MAX_STEPS_PER_RUN:
                self.step()
                self.accumulator -= TICK_DT
                steps += 1
            if steps == MAX_STEPS_PER_RUN:
                self.accumulator = 0.0  # we fell badly behind; don't try to catch up

        self.broadcast()

    def handle_message(self, message, address):
        kind = message.get('type')
        slot = self.players.get(address)

        if kind == 'hello':
            if slot is None:
                if len(self.players) >= self.max_players or self.started:
                    self.network.send({'type': 'full'}, address)
                    return
                slot = self.add_player(address)
            # Resent every time, in case the first welcome got lost
            self.network.send({'type': 'welcome', 'player_id': slot.player_id, 'seed': self.seed}, address)

        elif kind == 'input' and slot is not None:
            slot.last_heard = time.monotonic()
            seq = message.get('seq', 0)
            if seq > slot.last_seq:
                slot.last_seq = seq
                slot.move = message.get('move')
                slot.laser_target = message.get('laser_target')
            for action in message.get('actions', []):
                if action.get('aid', 0) > slot.last_action_id:
                    slot.last_action_id = action['aid']
                    slot.queued_actions.append(action)

    def add_player(self, address):
        taken = {slot.player_id for slot in self.players.values()}
        player_id = next(i for i in range(1, self.max_players + 1) if i not in taken)
        slot = PlayerSlot(player_id)
        self.players[address] = slot
        self.world.spawn_ship(player_id)
        print(f"[SERVER] Player {player_id} joined from {address}")
        return slot

    def step(self):
        commands = {}
        for slot in self.players.values():
            commands[slot.player_id] = {
                'move': slot.move,
                'actions': slot.queued_actions,
                'laser_target': slot.laser_target,
            }
            slot.queued_actions = []
        self.world.step(commands, TICK_DT)
        self.tick += 1

        # world.events is cleared every step and we may step several times per
        # broadcast, so collect them here.
        for event in self.world.events:
            self.recent_events.append((self.tick, [self.next_event_id, *event]))
            self.next_event_id += 1
        self.recent_events = [(tick, e) for tick, e in self.recent_events
                              if self.tick - tick <= EVENT_RESEND_TICKS]

    def broadcast(self):
        snapshot = make_snapshot(self.world)
        snapshot['events'] = [event for _, event in self.recent_events]
        for address, slot in self.players.items():
            message = dict(snapshot)
            message.update({
                'type': 'state',
                'tick': self.tick,
                'started': self.started,
                'players': len(self.players),
                'ack': slot.last_action_id,
            })
            self.network.send(message, address)

    def close(self):
        self.network.close()
