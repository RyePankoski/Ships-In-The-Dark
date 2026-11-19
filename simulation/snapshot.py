"""Turning the server's World into plain dicts and back.

Only things that change during play are sent. Asteroids are rebuilt from the
seed on each client, so the only asteroid data sent is which ones are destroyed.
"""
from objects.decoy import Decoy
from objects.missile import Missile
from objects.ship import Ship

SHIP_FIELDS = (
    'pos_x', 'pos_y', 'dx', 'dy', 'velocity', 'heading', 'total_velocity',
    'thrusting', 'health', 'health_low', 'total_missiles', 'missile_cooling_down',
    'missile_cooldown_timer', 'alive', 'painted', 'took_damage', 'mining_vessel_sees_you',
)
MISSILE_FIELDS = ('pos_x', 'pos_y', 'dx', 'dy', 'heading', 'velocity', 'fuel', 'owner', 'alive')
DECOY_FIELDS = ('pos_x', 'pos_y', 'dx', 'dy', 'v')


def make_snapshot(world):
    return {
        'ships': [_fields(ship, SHIP_FIELDS, ship.player_id) for ship in world.ships],
        'missiles': [
            dict(_fields(m, MISSILE_FIELDS, m.net_id), target=getattr(m.contact, 'net_id', None))
            for m in world.missiles
        ],
        'decoys': [_fields(d, DECOY_FIELDS, d.net_id) for d in world.decoys],
        'dead_asteroids': sorted(world.dead_asteroid_ids),
    }


def apply_snapshot(world, snapshot):
    """Update a client's copy of the world in place.

    Objects are updated, not replaced, so anything holding a reference to them
    (the instruments hold the player's ship, the radar holds the lists) stays valid.
    """
    _sync_list(world.ships, snapshot['ships'], SHIP_FIELDS,
               lambda d: Ship(d['pos_x'], d['pos_y'], player_id=d['id']), key='player_id')
    for ship in world.ships:
        ship.update_rect()

    _sync_list(world.decoys, snapshot['decoys'], DECOY_FIELDS,
               lambda d: Decoy(d['pos_x'], d['pos_y'], d['dx'], d['dy'], d['v']))

    missiles_by_id = {m['id']: m for m in snapshot['missiles']}
    _sync_list(world.missiles, snapshot['missiles'], MISSILE_FIELDS,
               lambda d: Missile(d['pos_x'], d['pos_y'], 0, 0, None, d['owner']))
    for missile in world.missiles:
        missile.player_id = missile.owner
        missile.contact = world.find(missiles_by_id[missile.net_id]['target'])

    for asteroid_id in snapshot['dead_asteroids']:
        if asteroid_id in world.dead_asteroid_ids:
            continue
        world.dead_asteroid_ids.add(asteroid_id)
        for cell, rocks in list(world.asteroids.items()):
            rocks[:] = [rock for rock in rocks if rock.net_id != asteroid_id]
            if not rocks:
                del world.asteroids[cell]


def _fields(obj, fields, object_id):
    data = {name: getattr(obj, name) for name in fields}
    data['id'] = object_id
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
        for name in fields:
            setattr(obj, name, data[name])
        seen.add(data['id'])
    objects[:] = [obj for obj in objects if getattr(obj, key) in seen]
