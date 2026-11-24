"""Turning the server's World into compact lists and back.

Only things that change during play are sent. Asteroids are rebuilt from the
seed on each client, and which ones have been destroyed is sent separately and
only when it changes (see netcode/server.py), so they're not in here at all.

Each object goes over the wire as a flat list, [id, value, value, ...], in the
order of its FIELDS table, instead of a dict that repeats every field name. Each
field says how to pack it:
    an int n  float, rounded to n decimals (positions to 0.1 of a unit is far
              finer than any sensor or the screen can tell apart)
    INT       whole number, sent as is
    BOOL      sent as 0/1, turned back into True/False on arrival
"""
import math

from objects.decoy import Decoy
from objects.drone import Drone
from objects.mining_vessel import MiningVessel
from objects.missile import Missile
from objects.ship import Ship

from config.constants import SNAP_DISTANCE, LOCAL_VELOCITY_BLEND

INT = 'int'
BOOL = 'bool'

# The fields a client keeps moving itself between snapshots; see apply_snapshot
MOTION_FIELDS = {'pos_x', 'pos_y', 'dir_x', 'dir_y', 'vel_x', 'vel_y', 'speed', 'heading'}

SHIP_FIELDS = (
    ('pos_x', 1), ('pos_y', 1), ('dir_x', 3), ('dir_y', 3), ('speed', 1), ('heading', 1),
    ('thrusting', BOOL), ('health', 1), ('health_low', BOOL), ('total_missiles', INT),
    ('missile_cooling_down', BOOL), ('missile_cooldown_timer', 2), ('alive', BOOL),
    ('painted', BOOL), ('took_damage', BOOL), ('mining_vessel_sees_you', BOOL),
    ('fuel', 1), ('current_draw', 2), ('low_fuel', BOOL),
    ('mining_on', BOOL), ('mining_target', INT), ('mining_progress', 2),
    ('drop_lock', BOOL), ('visibility', INT),
)
MISSILE_FIELDS = (
    ('pos_x', 1), ('pos_y', 1), ('vel_x', 3), ('vel_y', 3), ('heading', 1), ('speed', 1),
    ('fuel', 1), ('owner', INT), ('alive', BOOL),
)
DECOY_FIELDS = (('pos_x', 1), ('pos_y', 1), ('dir_x', 3), ('dir_y', 3), ('speed', 1))
# Drones and pirates are sent as positions only: they are slow, and the client just places them
DRONE_FIELDS = (('pos_x', 1), ('pos_y', 1), ('am_mining', BOOL))
PIRATE_FIELDS = (('pos_x', 1), ('pos_y', 1), ('heading', 1), ('resting', BOOL))


def make_snapshot(world):
    return {
        'ships': [_pack(ship, SHIP_FIELDS, ship.player_id) for ship in world.ships],
        # The missile's target id goes on the end
        'missiles': [
            _pack(m, MISSILE_FIELDS, m.net_id) + [getattr(m.target, 'net_id', None)]
            for m in world.missiles
        ],
        'decoys': [_pack(d, DECOY_FIELDS, d.net_id) for d in world.decoys],
        'drones': [_pack(d, DRONE_FIELDS, d.net_id) for d in world.drones],
        'pirates': [_pack(p, PIRATE_FIELDS, p.net_id) for p in world.pirates],
    }


def apply_snapshot(world, snapshot, age=0.0, my_id=None):
    """Update a client's copy of the world in place.

    Objects are updated, not replaced, so anything holding a reference to them
    (the instruments hold the player's ship, the radar holds the lists) stays valid.

    The client keeps simulating between snapshots (World.predict), so a snapshot
    isn't allowed to yank anything. Where the server says an object is, moved on by
    `age` (how old the snapshot is), becomes its target, and the gap is eased out
    over the next frames. A gap too big to be drift is a teleport and just happens.
    Our own ship (my_id) keeps its own heading and speed, nudged toward the server's.
    """
    ships = [_unpack(row, SHIP_FIELDS) for row in snapshot['ships']]
    _sync_list(world.ships, ships, SHIP_FIELDS,
               lambda d: Ship(d['pos_x'], d['pos_y'], player_id=d['id']), key='player_id',
               age=age, mine=my_id)
    for ship in world.ships:
        ship.update_rect()

    decoys = [_unpack(row, DECOY_FIELDS) for row in snapshot['decoys']]
    _sync_list(world.decoys, decoys, DECOY_FIELDS,
               lambda d: Decoy(d['pos_x'], d['pos_y'], d['dir_x'], d['dir_y'], d['speed']),
               age=age)

    missiles = [_unpack(row, MISSILE_FIELDS) for row in snapshot['missiles']]
    targets = {d['id']: d['extra'][0] for d in missiles}
    _sync_list(world.missiles, missiles, MISSILE_FIELDS,
               lambda d: Missile(d['pos_x'], d['pos_y'], 0, 0, None, d['owner']),
               age=age)
    for missile in world.missiles:
        missile.target = world.find(targets[missile.net_id])

    _sync_npcs(world.drones, snapshot.get('drones', []), DRONE_FIELDS, lambda d: Drone(d['pos_x'], d['pos_y']))
    _sync_npcs(world.pirates, snapshot.get('pirates', []), PIRATE_FIELDS,
               lambda d: MiningVessel(d['pos_x'], d['pos_y'], speed=40))


def _sync_npcs(grid, rows, fields, create):
    """Rebuild a grid-keyed group of drones or pirates from the server's list. These don't
    ease between snapshots: they're slow, so placing them where the server says is close enough."""
    existing = {obj.net_id: obj for obj in grid}
    grid.clear()
    for row in rows:
        data = _unpack(row, fields)
        obj = existing.get(data['id'])
        if obj is None:
            obj = create(data)
            obj.net_id = data['id']
        for name, _ in fields:
            setattr(obj, name, data[name])
        if hasattr(obj, 'update_rect'):
            obj.update_rect()
        grid.add(obj)


def _pack(obj, fields, object_id):
    row = [object_id]
    for name, kind in fields:
        value = getattr(obj, name)
        if kind == BOOL:
            row.append(1 if value else 0)
        elif kind == INT:
            row.append(value)
        else:
            row.append(round(value, kind))
    return row


def _unpack(row, fields):
    """[id, v, v, ...] -> {'id': id, name: value, ..., 'extra': [anything after]}"""
    data = {'id': row[0]}
    for (name, kind), value in zip(fields, row[1:]):
        data[name] = bool(value) if kind == BOOL else value
    data['extra'] = row[1 + len(fields):]
    return data


def _sync_list(objects, dicts, fields, create, key='net_id', age=0.0, mine=None):
    existing = {getattr(obj, key): obj for obj in objects}
    seen = set()
    for data in dicts:
        obj = existing.get(data['id'])
        if obj is None:
            obj = create(data)
            if key == 'net_id':
                obj.net_id = data['id']
            objects.append(obj)
            _copy_fields(obj, data, fields)
        else:
            _reconcile(obj, data, fields, age, is_mine=(data['id'] == mine and key == 'player_id'))
        seen.add(data['id'])
    objects[:] = [obj for obj in objects if getattr(obj, key) in seen]


def _copy_fields(obj, data, fields):
    for name, _ in fields:
        setattr(obj, name, data[name])
    obj.err_x = obj.err_y = 0.0


def _reconcile(obj, data, fields, age, is_mine):
    # Where the server says it is now: its position, carried on by the snapshot's age
    if 'vel_x' in data:
        vel_x, vel_y = data['vel_x'], data['vel_y']
    else:
        vel_x, vel_y = data['dir_x'] * data['speed'], data['dir_y'] * data['speed']
    target_x = data['pos_x'] + vel_x * age
    target_y = data['pos_y'] + vel_y * age

    # Whatever isn't about motion is simply the server's
    for name, _ in fields:
        if name not in MOTION_FIELDS:
            setattr(obj, name, data[name])

    gap_x, gap_y = target_x - obj.pos_x, target_y - obj.pos_y
    if math.hypot(gap_x, gap_y) > SNAP_DISTANCE:
        for name in MOTION_FIELDS & data.keys():
            setattr(obj, name, data[name])
        obj.pos_x, obj.pos_y = target_x, target_y
        obj.err_x = obj.err_y = 0.0
        return

    obj.err_x, obj.err_y = gap_x, gap_y
    for name in MOTION_FIELDS - {'pos_x', 'pos_y'}:
        if name not in data:
            continue
        if is_mine and name == 'heading':
            # Same idea as the steering fields, but an angle, so blend the short way round
            diff = (data[name] - obj.heading + 180) % 360 - 180
            obj.heading = (obj.heading + diff * LOCAL_VELOCITY_BLEND) % 360
        elif is_mine and name in ('dir_x', 'dir_y', 'speed'):
            # We're steering this one: ease toward the server instead of adopting it
            current = getattr(obj, name)
            setattr(obj, name, current + (data[name] - current) * LOCAL_VELOCITY_BLEND)
        else:
            setattr(obj, name, data[name])
