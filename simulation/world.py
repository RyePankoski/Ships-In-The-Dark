import math
import random

from objects.asteroid import Asteroid
from objects.decoy import Decoy
from objects.drone import Drone
from objects.mining_vessel import MiningVessel
from objects.missile import Missile
from objects.ship import Ship
from simulation.contacts import Contacts
from simulation.settings import WorldSettings
from config.constants import *
from utility.geometry import squared_distance

# The only keys the simulation cares about for flying a ship.
MOVE_KEYS = ('left', 'right', 'up', 'down', 'left_shift', 'tab')
# Switches that change a ship's power draw. The owning player sets them; the server applies them.
POWER_FLAGS = ('laser_on', 'prox_scan_on', 'blinking', 'deep_field_on', 'dampening', 'material_assessor_on', 'radar_scan_on')

# Ids below this are player ships (1, 2, ...). Everything else the world creates
# gets an id from FIRST_OBJECT_ID upwards.
FIRST_OBJECT_ID = 1000


def empty_command():
    """What a player sends the world each tick.

    move:         held movement keys, or None to leave the ship's steering alone
                  (inputs locked during FTL).
    actions:      one-off requests, e.g. {'type': 'fire', 'target': 1004}.
    laser_target: net_id of whatever this player's laser is touching, or None.
    power:        the ship's power switches (POWER_FLAGS), or None to leave them alone.
    """
    return {'move': None, 'actions': [], 'laser_target': None, 'power': None}


def _grid_remove(grid, cell, obj):
    """Take obj out of a grid-keyed dict, dropping the cell once it's empty."""
    grid[cell].remove(obj)
    if not grid[cell]:
        del grid[cell]


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

        self.alphabet = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z"]

        self.ships = []
        self.missiles = []
        self.decoys = []
        self.bullets = []
        self.lasers = []
        # mining-vessel lasers: [vessel, (x, y), time_left, asteroid]

        self.asteroids = {}
        self.drones = {}
        self.pirates = {}


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
            asteroid = Asteroid(pos_x, pos_y, rng.randint(50, 100), rng)
            asteroid.net_id = self.new_id()

            asteroid.id_for_ui = self._generate_asteroid_names(rng)
            self.asteroids.setdefault(asteroid.cell, []).append(asteroid)

        if not self.with_npcs:
            return

        for _ in range(self.settings.drones):
            pos_x = rng.randint(0, self.width)
            pos_y = rng.randint(0, self.height)
            drone = Drone(pos_x, pos_y)
            drone.net_id = self.new_id()
            self.drones.setdefault(drone.cell, []).append(drone)

        for _ in range(self.settings.pirates):
            x, y = self.random_empty_point()
            pirate = MiningVessel(x, y, speed=40)
            pirate.net_id = self.new_id()
            self.pirates.setdefault((int(x // GRID_SIZE), int(y // GRID_SIZE)), []).append(pirate)

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
            name += (rng.choice(self.alphabet))

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
        self.spawn_ship(player_id, x=SINGLE_PLAYER_SPAWN[0], y=SINGLE_PLAYER_SPAWN[1])
        self.spawn_ship(enemy_id, is_ai=True, x=SINGLE_PLAYER_ENEMY_SPAWN[0], y=SINGLE_PLAYER_ENEMY_SPAWN[1])
        self.callsigns = {player_id: callsign or f"PILOT-{player_id}", enemy_id: enemy_callsign}

    def remove_ship(self, player_id):
        """A player left: their ship and callsign go with them."""
        self.ships = [ship for ship in self.ships if ship.player_id != player_id]
        self.callsigns.pop(player_id, None)

    def remove_asteroids(self, asteroid_ids):
        """Destroy asteroids by id (a client catching up with the server's world)."""
        new = [i for i in asteroid_ids if i not in self.dead_asteroid_ids]
        if not new:
            return
        self.dead_asteroid_ids.update(new)
        self.dead_asteroid_log.extend(new)
        gone = set(new)
        for cell, rocks in list(self.asteroids.items()):
            rocks[:] = [rock for rock in rocks if rock.net_id not in gone]
            if not rocks:
                del self.asteroids[cell]

    def random_empty_point(self):
        while True:
            x = random.randint(0, self.width)
            y = random.randint(0, self.height)
            if self.is_empty_space(x, y):
                return x, y

    def is_empty_space(self, x, y):
        cell = (int(x // GRID_SIZE), int(y // GRID_SIZE))
        for asteroid in self.asteroids.get(cell, []):
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
                          random.randint(-1, 1), random.randint(-1, 1), random.randint(20, 25))
            decoy.net_id = self.new_id()
            self.decoys.append(decoy)

        elif kind == 'blink':
            ship.pos_x, ship.pos_y = self.random_empty_point()
            ship.update_rect()
            ship.drop_lock = False  # they've jumped: locks on them can hold again

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
        cell = (int(ship.rect.center[0] // GRID_SIZE), int(ship.rect.center[1] // GRID_SIZE))
        for asteroid in self.asteroids.get(cell, []):
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
        if MINING_YIELD[rock.material] == 'fuel':
            return ship.fuel < SHIP_MAX_FUEL
        if MINING_YIELD[rock.material] == 'missile':
            return ship.total_missiles < TOTAL_MISSILES
        if MINING_YIELD[rock.material] == 'hull':
            return ship.health < 100

        return ship.total_missiles < TOTAL_MISSILES

    def _finish_mining(self, ship, rock):
        if MINING_YIELD[rock.material] == 'fuel':
            ship.fuel = min(SHIP_MAX_FUEL, ship.fuel + MINING_FUEL_YIELD)
        elif MINING_YIELD[rock.material] == 'missile':
            ship.total_missiles = min(TOTAL_MISSILES, ship.total_missiles + MINING_MISSILE_YIELD)
        elif MINING_YIELD[rock.material] == 'hull':
            ship.health = 100

        rock.alive = False  # _step_asteroids removes it and tells the clients
        ship.mining_on = False  # the beam switches itself off once the rock is burned out
        self.events.append(('mined', ship.player_id, rock.material))


    def _step_asteroids(self):
        for cell, rocks in list(self.asteroids.items()):
            for asteroid in list(rocks):
                if not asteroid.alive:
                    rocks.remove(asteroid)
                    self.dead_asteroid_ids.add(asteroid.net_id)
                    self.dead_asteroid_log.append(asteroid.net_id)
            if not rocks:
                del self.asteroids[cell]

    def _step_mining_lasers(self, dt):
        for laser in list(self.lasers):
            laser[2] -= dt
            if laser[2] < 0:
                self.lasers.remove(laser)
                if laser[3] is not None:
                    laser[3].alive = False

    # Drones and pirates are listed out before any of them move. Walking the grid
    # cell by cell while moving them lets one that crosses into a cell still
    # ahead in the loop be updated twice in a frame, and a drone that died would
    # then be removed twice: a KeyError on its already-emptied cell.
    def _step_drones(self, dt):
        for drone in [d for group in self.drones.values() for d in group]:
            drone.run_drone(self.asteroids, dt)

            if drone.alive is False:
                _grid_remove(self.drones, drone.cell, drone)
                continue

            new_cell = (int(drone.pos_x // GRID_SIZE), int(drone.pos_y // GRID_SIZE))
            if new_cell != drone.cell:
                _grid_remove(self.drones, drone.cell, drone)
                self.drones.setdefault(new_cell, []).append(drone)
                drone.cell = new_cell

    def _step_pirates(self, dt):
        for cell, pirate in [(c, p) for c, group in self.pirates.items() for p in group]:
            pirate.run(self.ships, self.bullets, self.lasers, self.asteroids, dt, self.width, self.height)

            new_cell = (int(pirate.pos_x // GRID_SIZE), int(pirate.pos_y // GRID_SIZE))
            if new_cell != cell:
                _grid_remove(self.pirates, cell, pirate)
                self.pirates.setdefault(new_cell, []).append(pirate)

    def _step_bullets(self, dt):
        bullets_to_remove = []
        for bullet in self.bullets:
            bullet.run(dt, self.width, self.height)

            for ship in self.ships:
                if squared_distance(ship.rect.center, (bullet.pos_x, bullet.pos_y)) < 25 ** 2:
                    ship.health -= 2
                    ship.took_damage = True
                    self.events.append(('bullet_damage', ship.player_id))
                    bullets_to_remove.append(bullet)
                if bullet.alive is False:
                    bullets_to_remove.append(bullet)

            for cell in self.asteroids.values():
                for asteroid in cell:
                    if squared_distance((bullet.pos_x, bullet.pos_y), (asteroid.pos_x, asteroid.pos_y)) < asteroid.size ** 2:
                        bullets_to_remove.append(bullet)

        for bullet in bullets_to_remove:
            if bullet in self.bullets:
                self.bullets.remove(bullet)
