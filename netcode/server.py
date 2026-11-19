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
# A player we haven't heard from in this long has left (quit, crashed, lost link)
PLAYER_TIMEOUT = 5.0
# Plenty for a LAN party, and keeps one snapshot comfortably inside a UDP packet
MAX_PLAYERS = 16
MIN_PLAYERS_TO_LAUNCH = 2

CALLSIGN_MAX = 10
CALLSIGN_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")


def clean_callsign(text):
    """Upper case, letters/digits/dashes only, at most CALLSIGN_MAX long."""
    text = str(text or "").upper()
    return "".join(c for c in text if c in CALLSIGN_CHARS)[:CALLSIGN_MAX].strip('-')


class PlayerSlot:
    def __init__(self, player_id):
        self.player_id = player_id
        self.move = None            # latest held movement keys
        self.laser_target = None
        self.last_seq = -1          # newest input packet seen (older ones are ignored)
        self.last_action_id = 0     # newest action accepted (sent back as 'ack')
        self.queued_actions = []    # accepted, waiting for the next tick
        self.last_heard = time.monotonic()
        self.wanted_callsign = None  # what they last asked to be called
        # What this client has confirmed it already has, so we stop sending it
        self.roster_version = 0
        self.dead_known = 0


class Server:
    """Owns the real World. Players send inputs, the server steps, everyone gets the result.

    Any number of players (up to MAX_PLAYERS) can join, before or after launch.
    Before launch they wait in the lobby; the host launches with launch().

    Protocol (JSON over UDP, see also netcode/net_client.py):
      client -> server  {'type': 'hello', 'callsign', 'rv', 'dk'}
                            sent until welcomed, then as a heartbeat whenever no
                            input has gone out lately; also how a pilot renames
                            themselves in the lobby
                        {'type': 'input', 'seq', 'move', 'laser_target',
                         'actions': [... each with 'aid'], 'rv', 'dk'}
      server -> client  {'type': 'welcome', 'player_id', 'seed'}
                        {'type': 'full'}
                        {'type': 'state', 'tick', 'started', 'ack', 'events', ...snapshot,
                         and only when this client is missing them:
                         'roster': [rv, [[player_id, callsign], ...]],
                         'dead': [index, asteroid_id, ...]}

    'rv' and 'dk' are the client saying what it already has: the roster version,
    and how many entries of world.dead_asteroid_log. Until it has caught up, every
    state carries the missing part again, so a dropped packet can't lose it, and
    once it has, nothing more is sent.

    Actions (fire, decoy, blink) are resent by the client until the server acks
    them, so a dropped packet can't eat a missile launch. In the other direction,
    world events ([event_id, kind, *data]) are resent for EVENT_RESEND_TICKS.
    """

    def __init__(self, port=PORT, max_players=MAX_PLAYERS):
        self.network = NetworkLayer(server=True, port=port)
        self.network.start()

        self.max_players = max_players
        self.seed = random.randrange(2 ** 31)
        self.world = World(self.seed, with_npcs=False)
        self.players = {}  # address -> PlayerSlot
        self.roster_version = 1

        self.started = False
        self.tick = 0
        self.accumulator = 0.0

        self.recent_events = []  # (tick, [event_id, kind, *data])
        self.next_event_id = 1

    @property
    def can_launch(self):
        return not self.started and len(self.players) >= MIN_PLAYERS_TO_LAUNCH

    def launch(self):
        if self.can_launch:
            self.started = True
            print(f"[SERVER] Launching with {len(self.players)} players")

    def run(self, dt):
        for message, address in self.network.receive_all():
            self.handle_message(message, address)
        self.drop_silent_players()

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
            new = slot is None
            if new:
                if len(self.players) >= self.max_players:
                    self.network.send({'type': 'full'}, address)
                    return
                slot = self.add_player(address)
            self.heard_from(slot, message)
            # Callsigns are settled in the lobby; once flying, you are who you are
            # (but someone joining mid-game still gets the one they came with)
            if (new or not self.started) and message.get('callsign') != slot.wanted_callsign:
                slot.wanted_callsign = message.get('callsign')
                self.set_callsign(slot, slot.wanted_callsign)
            # Resent every time, in case the first welcome got lost
            self.network.send({'type': 'welcome', 'player_id': slot.player_id, 'seed': self.seed}, address)

        elif kind == 'input' and slot is not None:
            self.heard_from(slot, message)
            seq = message.get('seq', 0)
            if seq > slot.last_seq:
                slot.last_seq = seq
                slot.move = message.get('move')
                slot.laser_target = message.get('laser_target')
            for action in message.get('actions', []):
                if action.get('aid', 0) > slot.last_action_id:
                    slot.last_action_id = action['aid']
                    slot.queued_actions.append(action)

    def heard_from(self, slot, message):
        slot.last_heard = time.monotonic()
        # Only ever forward: an old packet arriving late mustn't make us resend
        slot.roster_version = max(slot.roster_version, int(message.get('rv', 0)))
        slot.dead_known = max(slot.dead_known, int(message.get('dk', 0)))

    def add_player(self, address):
        taken = {slot.player_id for slot in self.players.values()}
        player_id = next(i for i in range(1, self.max_players + 1) if i not in taken)
        slot = PlayerSlot(player_id)
        self.players[address] = slot
        self.world.spawn_ship(player_id)
        self.set_callsign(slot, None)
        print(f"[SERVER] Player {player_id} joined from {address}")
        return slot

    def set_callsign(self, slot, wanted):
        """Give a player the callsign they asked for, or PILOT-n if it's empty or taken."""
        name = clean_callsign(wanted)
        others = {cs for pid, cs in self.world.callsigns.items() if pid != slot.player_id}
        if not name or name in others:
            name = f"PILOT-{slot.player_id}"
        if self.world.callsigns.get(slot.player_id) != name:
            self.world.callsigns[slot.player_id] = name
            self.roster_version += 1

    def drop_silent_players(self):
        now = time.monotonic()
        for address, slot in list(self.players.items()):
            if now - slot.last_heard > PLAYER_TIMEOUT:
                del self.players[address]
                self.world.remove_ship(slot.player_id)
                self.roster_version += 1
                print(f"[SERVER] Player {slot.player_id} timed out")

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
        roster = [self.roster_version, [[pid, cs] for pid, cs in sorted(self.world.callsigns.items())]]
        dead_log = self.world.dead_asteroid_log

        for address, slot in self.players.items():
            message = dict(snapshot)
            message.update({
                'type': 'state',
                'tick': self.tick,
                'started': self.started,
                'ack': slot.last_action_id,
            })
            if slot.roster_version < self.roster_version:
                message['roster'] = roster
            if slot.dead_known < len(dead_log):
                message['dead'] = [slot.dead_known, *dead_log[slot.dead_known:]]
            self.network.send(message, address)

    def close(self):
        self.network.close()
