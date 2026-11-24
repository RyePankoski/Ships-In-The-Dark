import math
import random
import string
from typing import TypedDict

from objects.asteroid import Asteroid
from objects.decoy import Decoy
from objects.drone import Drone
from objects.mining_vessel import MiningVessel
from objects.missile import Missile
from objects.ship import Ship
from simulation.contacts import Contacts
from simulation.grid import Grid
from simulation.settings import WorldSettings
from config.constants import (MINING_FUEL_YIELD, MINING_MISSILE_YIELD, MINING_RANGE, MINING_TIME, MINING_YIELD,
                              SHIP_MAX_FUEL, SHIP_MAX_HEALTH, SINGLE_PLAYER_ENEMY_SPAWN, SINGLE_PLAYER_SPAWN,
                              TOTAL_MISSILES)
from utility.geometry import squared_distance
from config.constants import *





class Command(TypedDict):
    move: object
    actions: list
    laser_target: object
    power: object


def empty_command() -> Command:
    """What a player sends the world each tick.

    move:         held movement keys, or None to leave the ship's steering alone
                  (inputs locked during FTL).
    actions:      one-off requests, e.g. {'type': 'fire', 'target': 1004}.
    laser_target: net_id of whatever this player's laser is touching, or None.
    power:        the ship's power switches (POWER_FLAGS), or None to leave them alone.
    """
    return {'move': None, 'actions': [], 'laser_target': None, 'power': None}


# What each kind of rock pays out: (does the ship have room for it, give it to the ship)
def _has_fuel_room(ship):
    return ship.fuel < SHIP_MAX_FUEL


def _add_fuel(ship):
    ship.fuel = min(SHIP_MAX_FUEL, ship.fuel + MINING_FUEL_YIELD)


def _has_missile_room(ship):
    return ship.total_missiles < TOTAL_MISSILES


def _add_missiles(ship):
    ship.total_missiles = min(TOTAL_MISSILES, ship.total_missiles + MINING_MISSILE_YIELD)


def _needs_repair(ship):
    return ship.health < SHIP_MAX_HEALTH


def _repair_hull(ship):
    ship.health = SHIP_MAX_HEALTH


_MINING_HANDLERS = {
    'fuel': (_has_fuel_room, _add_fuel),
    'missile': (_has_missile_room, _add_missiles),
    'hull': (_needs_repair, _repair_hull),
}


class World:
    """The facts of the game: every object, and the rules that move them.

    No drawing, no sound, no keyboard. Single-player owns a World and steps it
    itself; in multiplayer the server owns the real one and each client keeps a
    copy that is updated from the server's snapshots (simulation/snapshot.py).
    """

    def __init__(self, seed, with_npcs=True, settings=None):
        self.seed = seed
        self.with_npcs = with_npcs  # generate drones and pirates here (False: they arrive in snapshots)
        self.settings = settings or WorldSettings()
        self.width = self.height = self.settings.size

        self.ships = []
        self.missiles = []
        self.decoys = []
        self.bullets = []
        self.lasers = []  # MiningLaser, fired by mining vessels
        self.asteroids = Grid()
        self.drones = Grid()
        self.pirates = Grid()

        self.dead_asteroid_ids = set()
        # Same ids in the order they died. The server sends each client only the
        # part of this it hasn't confirmed yet (see netcode/server.py).
        self.dead_asteroid_log = []

        # player_id -> callsign, for every pilot in this world
        self.callsigns = {}

        # Things that happened during the last step, for the client to react to
        # (sounds etc). Only meaningful when the world is stepped locally.
        self.events = []
        # Same, but only for some pilots: [(player_ids, event), ...]. The server sends each
        # one only to those pilots.
        self.private_events = []

        self.time = 0.0
        # How the match stands for one pilot: 'playing', 'dead' or 'won' (see outcome_for).
        # Set by whoever owns the truth: the local step, or the server's snapshot.
        self.outcome = 'playing'

        # How sensors look at everything above (see simulation/contacts.py)
        self.contacts = Contacts(self)

        self._next_id = FIRST_OBJECT_ID
        # Gameplay randomness (spawn points, decoy drift, blink) has its own stream, apart
        # from the one that generates the world, so a seeded match can be replayed in tests.
        self.rng = random.Random(None if seed is None else f"{seed}:gameplay")
        self._generate(random.Random(seed))

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def new_id(self):
        object_id = self._next_id
        self._next_id += 1
        return object_id

    def _generate(self, rng):
        # Asteroids come only from the seed and the settings, in a fixed order, so every
        # machine that builds a World from the same seed gets the same rocks with the
        # same ids. Nothing about them needs to go over the network.
        centers = [(rng.randint(0, self.width), rng.randint(0, self.height))
                   for _ in range(max(3, self.settings.asteroids // 20))]
        for _ in range(self.settings.asteroids):
            if self.settings.layout == 'clustered':
                pos_x, pos_y = self._clustered_point(rng, centers)
            else:
                pos_x = rng.randint(0, self.width)
                pos_y = rng.randint(0, self.height)
            asteroid = Asteroid(pos_x, pos_y, rng.randint(MIN_ROCK_RADIUS, MAX_ROCK_RADIUS), rng)
            asteroid.net_id = self.new_id()

            asteroid.id_for_ui = self._generate_asteroid_names(rng)
            self.asteroids.add(asteroid)

        if not self.with_npcs:
            return

        for _ in range(self.settings.drones):
            pos_x = rng.randint(0, self.width)
            pos_y = rng.randint(0, self.height)
            drone = Drone(pos_x, pos_y)
            drone.net_id = self.new_id()
            self.drones.add(drone)

        for _ in range(self.settings.pirates):
            x, y = self.random_empty_point()
            pirate = MiningVessel(x, y, speed=40)
            pirate.net_id = self.new_id()
            self.pirates.add(pirate)

    def _clustered_point(self, rng, centers):
        """A point in a belt: near one of the cluster centres, kept inside the world."""
        cx, cy = rng.choice(centers)
        spread = self.width / 10
        x = min(max(round(rng.gauss(cx, spread)), 0), self.width)
        y = min(max(round(rng.gauss(cy, spread)), 0), self.height)
        return x, y

    def _generate_asteroid_names(self, rng):
        length = rng.randint(1, 3)
        name = ""
        for _ in range(length):
            name += (rng.choice(string.ascii_lowercase))

        length = rng.randint(1, 3)

        for _ in range(length):
            name += str(rng.randint(0, 9))
        return name

    def spawn_ship(self, player_id, is_ai=False, x=None, y=None):
        if x is None or y is None:
            x, y = self.random_empty_point()

        ship = Ship(x, y, player_id=player_id, is_ai=is_ai)
        self.ships.append(ship)
        return ship

    def setup_single_player(self, callsign, player_id=1, enemy_id=2, enemy_callsign="UNKNOWN"):
        """The single-player scenario: the player and one AI opponent near each other."""
        # The fixed spots are kept when a rock isn't on them; otherwise we'd start inside one.
        px, py = self._clear_spot(SINGLE_PLAYER_SPAWN)
        self.spawn_ship(player_id, x=px, y=py)
        ex, ey = self._clear_spot(SINGLE_PLAYER_ENEMY_SPAWN)
        self.spawn_ship(enemy_id, is_ai=True, x=ex, y=ey)
        self.callsigns = {player_id: callsign or f"PILOT-{player_id}", enemy_id: enemy_callsign}

    def setup_tutorial(self, callsign, player_id=1):
        """The tutorial scenario: just the player, no opponent."""
        px, py = self._clear_spot(SINGLE_PLAYER_SPAWN)
        self.spawn_ship(player_id, x=px, y=py)
        self.callsigns = {player_id: callsign}

    def _clear_spot(self, spot):
        """`spot` if no rock is on it, otherwise a random empty point."""
        if self.is_empty_space(*spot):
            return spot
        return self.random_empty_point()

    def remove_ship(self, player_id):
        """A player left: their ship and callsign go with them."""
        self.ships = [ship for ship in self.ships if ship.player_id != player_id]
        self.callsigns.pop(player_id, None)

    def remove_asteroids(self, asteroid_ids):
        """Destroy asteroids by id (a client catching up with the server's world)."""
        gone = {i for i in asteroid_ids if i not in self.dead_asteroid_ids}
        if not gone:
            return
        for rock in self.asteroids:
            if rock.net_id in gone:
                self._bury_asteroid(rock)
                gone.discard(rock.net_id)
        # Ids for rocks this world never had still count as dead.
        for net_id in gone:
            self.dead_asteroid_ids.add(net_id)
            self.dead_asteroid_log.append(net_id)

    def _bury_asteroid(self, rock):
        """The one place a destroyed asteroid is removed and recorded as dead."""
        self.asteroids.remove(rock)
        self.dead_asteroid_ids.add(rock.net_id)
        self.dead_asteroid_log.append(rock.net_id)

    def random_empty_point(self):
        while True:
            x = self.rng.randint(0, self.width)
            y = self.rng.randint(0, self.height)
            if self.is_empty_space(x, y):
                return x, y

    def is_empty_space(self, x, y):
        # A rock's centre can be up to its radius plus the clearance away, and that can
        # reach into the neighbouring cells, so look at those too.
        for asteroid in self.asteroids.near(x, y, reach=self.asteroids.reach_for(MAX_ROCK_RADIUS + 50)):
            if squared_distance((x, y), (asteroid.pos_x, asteroid.pos_y)) < (asteroid.size + 50) ** 2:
                return False
        return True

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------
    def get_ship(self, player_id):
        return next((ship for ship in self.ships if ship.player_id == player_id), None)

    def find(self, net_id):
        """Any world object by id, or None."""
        if net_id is None:
            return None
        return self.contacts.find(net_id)

    def outcome_for(self, my_id):
        """'dead' if my ship is gone, 'won' if there were other pilots and none are left
        flying, otherwise 'playing'. Dead wins over won when both are true."""
        mine = self.get_ship(my_id)
        if mine is None or not mine.alive:
            return 'dead'
        others = [ship for ship in self.ships if ship.player_id != my_id]
        if others and not any(ship.alive for ship in others):
            return 'won'
        return 'playing'

    # ------------------------------------------------------------------
    # Stepping
    # ------------------------------------------------------------------
    def step(self, commands, dt):
        """Advance the world by dt. commands = {player_id: command dict}."""
        self.events = []
        self.private_events = []
        alive_before = {ship.player_id: ship.alive for ship in self.ships}
        self.time += dt

        for ship in self.ships:
            command = commands.get(ship.player_id)
            if command is None or not ship.alive:
                continue
            if command.get('move') is not None:
                ship.apply_inputs(command['move'], dt)
            if command.get('power') is not None:
                for name in POWER_FLAGS:
                    setattr(ship, name, bool(command['power'][name]))
            # Charging a blink breaks any lock on the ship; the blink action clears it once they've jumped
            if ship.blinking:
                ship.drop_lock = True
            for action in command.get('actions', []):
                self.do_action(ship, action)

        self._update_painted(commands)

        self._step_ships(dt)
        self._step_missiles(dt)
        self._step_decoys(dt)
        self._step_mining(dt)  # before the asteroid sweep, so a mined-out rock goes this step
        self._step_asteroids()
        self._step_mining_lasers(dt)
        self._step_drones(dt)
        self._step_pirates(dt)
        self._step_bullets(dt)

        # Whatever did it (missile, bullet, collision), every pilot hears that a ship went down
        for ship in self.ships:
            if alive_before.get(ship.player_id) and not ship.alive:
                self.events.append(('ship_destroyed', ship.player_id))

    def do_action(self, ship, action):
        kind = action.get('type')

        if kind == 'fire':
            target = self.find(action.get('target'))
            if target is not None and target is not ship and ship.can_fire_missile():
                self.fire_missile(ship, target)
                ship.fire()

        elif kind == 'decoy':
            decoy = Decoy(ship.rect.center[0], ship.rect.center[1],
                          self.rng.randint(-1, 1), self.rng.randint(-1, 1), self.rng.randint(20, 25))
            decoy.net_id = self.new_id()
            self.decoys.append(decoy)

        elif kind == 'blink':
            ship.pos_x, ship.pos_y = self.random_empty_point()
            ship.update_rect()
            ship.drop_lock = False  # they've jumped: locks on them can hold again

        elif kind == 'dfs_scan':
            # Only the pilot who was swept hears about it
            for player_id in action.get('targets', []):
                target = self.get_ship(player_id)
                if target is not None and target is not ship and target.alive:
                    self.private_events.append(({player_id}, ('dfs_scanned', player_id)))

        elif kind == 'mine':
            self._start_mining(ship, action.get('target'))

        elif kind == 'mine_off':
            self._drop_mining(ship)

    def fire_missile(self, ship, target):
        missile = Missile(ship.rect.center[0], ship.rect.center[1], 0, 0, target, ship.player_id)
        missile.net_id = self.new_id()
        self.missiles.append(missile)
        return missile

    def _update_painted(self, commands):
        # A ship is painted while another player's laser is touching it.
        for ship in self.ships:
            ship.painted = any(
                command.get('laser_target') == ship.player_id
                for player_id, command in commands.items()
                if player_id != ship.player_id
            )

    def _step_ships(self, dt):
        for ship in self.ships:
            if not ship.alive:
                continue
            ship.run(dt, self.width, self.height)
            self._die_on_asteroids(ship, announce=True)

    def _die_on_asteroids(self, ship, announce=False):
        for asteroid in self.asteroids.near(ship.rect.center[0], ship.rect.center[1]):
            if squared_distance(ship.rect.center, (asteroid.pos_x, asteroid.pos_y)) < asteroid.size ** 2:
                if ship.speed > 100:
                    ship.alive = False
                    ship.took_damage = True
                else:
                    ship.health -= 50
                    if announce:
                        self.events.append(('asteroid_damage', ship.player_id))
                    ship.dir_x *= -1.5
                    ship.dir_y *= -1.5

    def predict(self, my_id, command, dt):
        """A client's guess at the next dt, between snapshots. Only motion: our own
        ship answers our keys, everything else coasts. Hits, damage, firing and
        events are the server's call, and the next snapshot corrects any drift."""
        mine = self.get_ship(my_id)
        if mine is not None and mine.alive and command.get('move') is not None:
            mine.apply_inputs(command['move'], dt)

        for ship in self.ships:
            if ship.alive:
                ship.coast(dt, self.width, self.height)
                ship.ease_correction(dt)
                ship.update_rect()

        for missile in self.missiles:
            missile.run(dt, self.asteroids, authoritative=False)
            missile.ease_correction(dt)

        for decoy in self.decoys:
            decoy.ease_correction(dt)

    def _step_missiles(self, dt):
        for missile in list(self.missiles):
            # We pass asteroids here for guidance, not targeting/removal.
            missile.run(dt, self.asteroids)
            if missile.alive is False:
                if missile.reached_target:
                    if isinstance(missile.target, Ship):
                        self.events.append(('missile_damage', missile.target.player_id))
                    # Only the pilot who fired it and the pilot it hit know it landed
                    involved = {missile.owner, getattr(missile.target, 'player_id', None)} - {None}
                    # Contact is the shooter's news; being hit is the victim's
                    self.private_events.append(({missile.owner}, ('missile_contact', missile.pos_x, missile.pos_y)))
                    target_id = getattr(missile.target, 'player_id', None)
                    if target_id is not None:
                        self.private_events.append(({target_id}, ('player_hit_by_missile', missile.pos_x, missile.pos_y)))
                    hit = missile.exploded_on_type
                    self.private_events.append((involved, ('missile_exploded', missile.pos_x, missile.pos_y,
                                                           hit.__name__ if hit else None,
                                                           missile.exploded_on_player)))
                self.missiles.remove(missile)

    def _step_decoys(self, dt):
        for decoy in list(self.decoys):
            decoy.run(dt)
            if decoy.alive is False:
                self.decoys.remove(decoy)

    def _step_mining(self, dt):
        """Burns the rock the ship has designated. Nothing is picked automatically:
        the designation is made by a 'mine' action (see do_action). It ends when the
        rock is mined out, dies, or goes out of range, or when the beam switches off."""
        for ship in self.ships:
            if not ship.alive or not ship.mining_on or ship.mining_target is None:
                self._drop_mining(ship)
                continue

            rock = self.find(ship.mining_target)
            if rock is None or not self._can_mine(ship, rock):
                self._drop_mining(ship)
                continue

            ship.mining_progress += dt / MINING_TIME
            if ship.mining_progress >= 1.0:
                self._finish_mining(ship, rock)
                self._drop_mining(ship)

    def _drop_mining(self, ship):
        ship.mining_on = False
        ship.mining_target = None
        ship.mining_progress = 0.0

    def _start_mining(self, ship, target_id):
        """Switch the beam on and lock it onto the rock, if the ship can mine it from here."""
        rock = self.find(target_id)
        if rock is None or not ship.alive or not self._can_mine(ship, rock):
            return
        ship.mining_on = True
        ship.mining_target = rock.net_id
        ship.mining_progress = 0.0

    def _can_mine(self, ship, rock):
        """A live asteroid of a mineable kind, in range, and the ship has room for what it pays."""
        if getattr(rock, 'kind', None) != 'asteroid' or not rock.alive or rock.material not in MINING_YIELD:
            return False
        cx, cy = ship.center
        if math.hypot(rock.pos_x - cx, rock.pos_y - cy) > MINING_RANGE:
            return False
        has_room, _ = _MINING_HANDLERS[MINING_YIELD[rock.material]]
        return has_room(ship)

    def _finish_mining(self, ship, rock):
        _, collect = _MINING_HANDLERS[MINING_YIELD[rock.material]]
        collect(ship)

        rock.alive = False  # _step_asteroids removes it and tells the clients
        ship.mining_on = False  # the beam switches itself off once the rock is burned out
        self.events.append(('mined', ship.player_id, rock.material))

    def _step_asteroids(self):
        for asteroid in self.asteroids:
            if not asteroid.alive:
                self._bury_asteroid(asteroid)

    def _step_mining_lasers(self, dt):
        for laser in list(self.lasers):
            laser.time_left -= dt
            if laser.time_left < 0:
                self.lasers.remove(laser)
                if laser.asteroid is not None:
                    laser.asteroid.alive = False

    # Grid iteration takes a snapshot list, so a drone or pirate that moves into
    # another cell mid-loop is still visited exactly once this frame.
    def _step_drones(self, dt):
        for drone in self.drones:
            drone.run_drone(self.asteroids, dt)

            if drone.alive is False:
                self.drones.remove(drone)
            else:
                self.drones.move(drone)

    def _step_pirates(self, dt):
        for pirate in self.pirates:
            pirate.run(self.ships, self.bullets, self.lasers, self.asteroids, dt, self.width, self.height)
            self.pirates.move(pirate)

    def _step_bullets(self, dt):
        bullets_to_remove = []
        for bullet in self.bullets:
            bullet.run(dt, self.width, self.height)

            for ship in self.ships:
                if squared_distance(ship.rect.center, (bullet.pos_x, bullet.pos_y)) < BULLET_HIT_RADIUS ** 2:
                    ship.health -= BULLET_DAMAGE
                    ship.took_damage = True
                    self.events.append(('bullet_damage', ship.player_id))
                    bullets_to_remove.append(bullet)
                if bullet.alive is False:
                    bullets_to_remove.append(bullet)

            # Rocks are at most 100 across and cells 500 wide, so the bullet's own cell
            # plus its neighbours holds every rock it could touch.
            for asteroid in self.asteroids.near(bullet.pos_x, bullet.pos_y, reach=1):
                if squared_distance((bullet.pos_x, bullet.pos_y), (asteroid.pos_x, asteroid.pos_y)) < asteroid.size ** 2:
                    bullets_to_remove.append(bullet)

        for bullet in bullets_to_remove:
            if bullet in self.bullets:
                self.bullets.remove(bullet)
