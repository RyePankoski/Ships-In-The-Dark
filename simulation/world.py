import random

from objects.asteroid import Asteroid
from objects.decoy import Decoy
from objects.drone import Drone
from objects.mining_vessel import MiningVessel
from objects.missile import Missile
from objects.ship import Ship
from simulation.contacts import Contacts
from utility.constants import *
from utility.common import squared_distance

# The only keys the simulation cares about for flying a ship.
MOVE_KEYS = ('left', 'right', 'up', 'down', 'left_shift', 'tab')

# Ids below this are player ships (1, 2, ...). Everything else the world creates
# gets an id from FIRST_OBJECT_ID upwards.
FIRST_OBJECT_ID = 1000


def empty_command():
    """What a player sends the world each tick.

    move:         held movement keys, or None to leave the ship's steering alone
                  (inputs locked during FTL, or the autopilot is flying).
    actions:      one-off requests, e.g. {'type': 'fire', 'target': 1004}.
    laser_target: net_id of whatever this player's laser is touching, or None.
    """
    return {'move': None, 'actions': [], 'laser_target': None}


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

    def __init__(self, seed, with_npcs=True, online=False):
        self.seed = seed
        self.with_npcs = with_npcs

        self.alphabet = ["a","b", "c","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y","z"]

        self.ships = []
        self.missiles = []
        self.decoys = []
        self.bullets = []
        self.lasers = []  # mining-vessel lasers: [vessel, (x, y), time_left, asteroid]

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

        self.time = 0.0

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
        # Asteroids come only from the seed, in a fixed order, so every machine
        # that builds a World from the same seed gets the same rocks with the
        # same ids. Nothing about them needs to go over the network.
        for _ in range(100):
            pos_x = rng.randint(0, WORLD_WIDTH)
            pos_y = rng.randint(0, WORLD_HEIGHT)
            asteroid = Asteroid(pos_x, pos_y, rng.randint(50, 100))
            asteroid.net_id = self.new_id()

            asteroid.id_for_ui = self._generate_asteroid_names()
            self.asteroids.setdefault(asteroid.cell, []).append(asteroid)

        if not self.with_npcs:
            return

        for _ in range(8):
            pos_x = rng.randint(0, WORLD_WIDTH)
            pos_y = rng.randint(0, WORLD_HEIGHT)
            drone = Drone(pos_x, pos_y)
            drone.net_id = self.new_id()
            self.drones.setdefault(drone.cell, []).append(drone)

        pirate = MiningVessel(100, 100, speed=40)
        pirate.net_id = self.new_id()
        self.pirates.setdefault((int(100 // GRID_SIZE), int(100 // GRID_SIZE)), []).append(pirate)

    def _generate_asteroid_names(self):
        length = random.randint(1, 3)
        name = ""
        for _ in range(length):
            name += (random.choice(self.alphabet))

        length = random.randint(1, 3)

        for _ in range(length):
            name += str(random.randint(0,9))
        return name


    def spawn_ship(self, player_id, is_ai=False):
        x, y = self.random_empty_point()
        ship = Ship(x, y, player_id=player_id, is_ai=is_ai)
        self.ships.append(ship)
        return ship

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
            x = random.randint(0, WORLD_WIDTH)
            y = random.randint(0, WORLD_HEIGHT)
            if self.is_empty_space(x, y):
                return x, y

    def is_empty_space(self, x, y):
        cell = (int(x // GRID_SIZE), int(y // GRID_SIZE))
        for asteroid in self.asteroids.get(cell, []):
            distance, in_range = squared_distance((x, y), (asteroid.pos_x, asteroid.pos_y), asteroid.size + 50)
            if in_range:
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

    # ------------------------------------------------------------------
    # Stepping
    # ------------------------------------------------------------------
    def step(self, commands, dt):
        """Advance the world by dt. commands = {player_id: command dict}."""
        self.events = []
        self.time += dt

        for ship in self.ships:
            command = commands.get(ship.player_id)
            if command is None or not ship.alive:
                continue
            if command.get('move') is not None:
                ship.apply_inputs(command['move'], dt)
            for action in command.get('actions', []):
                self.do_action(ship, action)

        self._update_painted(commands)

        self._step_ships(dt)
        self._step_missiles(dt)
        self._step_decoys(dt)
        self._step_asteroids()
        self._step_mining_lasers(dt)
        self._step_drones(dt)
        self._step_pirates(dt)
        self._step_bullets(dt)

    def do_action(self, ship, action):
        kind = action.get('type')

        if kind == 'fire':
            target = self.find(action.get('target'))
            if target is not None and target is not ship and ship.can_fire():
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
            ship.run(dt)
            self._bounce_off_asteroids(ship)

    def _bounce_off_asteroids(self, ship):
        cell = (int(ship.rect.center[0] // GRID_SIZE), int(ship.rect.center[1] // GRID_SIZE))
        for asteroid in self.asteroids.get(cell, []):
            distance, in_range = squared_distance(ship.rect.center, (asteroid.pos_x, asteroid.pos_y), asteroid.size)
            if in_range:
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
                ship.coast(dt)
                self._bounce_off_asteroids(ship)
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
                    self.events.append(('missile_contact', missile.pos_x, missile.pos_y))
                self.missiles.remove(missile)

    def _step_decoys(self, dt):
        for decoy in list(self.decoys):
            decoy.run(dt)
            if decoy.alive is False:
                self.decoys.remove(decoy)

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
            pirate.run(self.ships, self.bullets, self.lasers, self.asteroids, dt)

            new_cell = (int(pirate.pos_x // GRID_SIZE), int(pirate.pos_y // GRID_SIZE))
            if new_cell != cell:
                _grid_remove(self.pirates, cell, pirate)
                self.pirates.setdefault(new_cell, []).append(pirate)

    def _step_bullets(self, dt):
        bullets_to_remove = []
        for bullet in self.bullets:
            bullet.run(dt)

            for ship in self.ships:
                distance, in_range = squared_distance(ship.rect.center, (bullet.pos_x, bullet.pos_y), 25)
                if in_range:
                    ship.health -= 2
                    ship.took_damage = True
                    self.events.append(('damage', ship.player_id))
                    bullets_to_remove.append(bullet)
                if bullet.alive is False:
                    bullets_to_remove.append(bullet)

            for cell in self.asteroids.values():
                for asteroid in cell:
                    distance, in_range = squared_distance((bullet.pos_x, bullet.pos_y), (asteroid.pos_x, asteroid.pos_y), asteroid.size)
                    if in_range:
                        bullets_to_remove.append(bullet)

        for bullet in bullets_to_remove:
            if bullet in self.bullets:
                self.bullets.remove(bullet)
