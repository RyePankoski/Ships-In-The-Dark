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
from objects.decoy import Decoy
from objects.missile import Missile
from objects.ship import Ship

INT = 'int'
BOOL = 'bool'

SHIP_FIELDS = (
    ('pos_x', 1), ('pos_y', 1), ('dir_x', 3), ('dir_y', 3), ('speed', 1), ('heading', 1),
    ('thrusting', BOOL), ('health', 1), ('health_low', BOOL), ('total_missiles', INT),
    ('missile_cooling_down', BOOL), ('missile_cooldown_timer', 2), ('alive', BOOL),
    ('painted', BOOL), ('took_damage', BOOL), ('mining_vessel_sees_you', BOOL),
)
MISSILE_FIELDS = (
    ('pos_x', 1), ('pos_y', 1), ('vel_x', 3), ('vel_y', 3), ('heading', 1), ('speed', 1),
    ('fuel', 1), ('owner', INT), ('alive', BOOL),
)
DECOY_FIELDS = (('pos_x', 1), ('pos_y', 1), ('dir_x', 3), ('dir_y', 3), ('speed', 1))


def make_snapshot(world):
    return {
        'ships': [_pack(ship, SHIP_FIELDS, ship.player_id) for ship in world.ships],
        # The missile's target id goes on the end
        'missiles': [
            _pack(m, MISSILE_FIELDS, m.net_id) + [getattr(m.target, 'net_id', None)]
            for m in world.missiles
        ],
        'decoys': [_pack(d, DECOY_FIELDS, d.net_id) for d in world.decoys],
    }


def apply_snapshot(world, snapshot):
    """Update a client's copy of the world in place.

    Objects are updated, not replaced, so anything holding a reference to them
    (the instruments hold the player's ship, the radar holds the lists) stays valid.
    """
    ships = [_unpack(row, SHIP_FIELDS) for row in snapshot['ships']]
    _sync_list(world.ships, ships, SHIP_FIELDS,
               lambda d: Ship(d['pos_x'], d['pos_y'], player_id=d['id']), key='player_id')
    for ship in world.ships:
        ship.update_rect()

    decoys = [_unpack(row, DECOY_FIELDS) for row in snapshot['decoys']]
    _sync_list(world.decoys, decoys, DECOY_FIELDS,
               lambda d: Decoy(d['pos_x'], d['pos_y'], d['dir_x'], d['dir_y'], d['speed']))

    missiles = [_unpack(row, MISSILE_FIELDS) for row in snapshot['missiles']]
    targets = {d['id']: d['extra'][0] for d in missiles}
    _sync_list(world.missiles, missiles, MISSILE_FIELDS,
               lambda d: Missile(d['pos_x'], d['pos_y'], 0, 0, None, d['owner']))
    for missile in world.missiles:
        missile.target = world.find(targets[missile.net_id])


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


def _sync_list(objects, dicts, fields, create, key='net_id'):
    existing = {getattr(obj, key): obj for obj in objects}
    seen = set()
    for data in dicts:
        obj = existing.get(data['id'])
        if obj is None:
            obj = create(data)
            if key == 'net_id':
                obj.net_id = data['id']
            objects.append(obj)
        for name, _ in fields:
            setattr(obj, name, data[name])
        seen.add(data['id'])
    objects[:] = [obj for obj in objects if getattr(obj, key) in seen]
