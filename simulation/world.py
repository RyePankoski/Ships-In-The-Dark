import random

from objects.asteroid import Asteroid
from objects.decoy import Decoy
from objects.drone import Drone
from objects.mining_vessel import MiningVessel
from objects.missile import Missile
from objects.ship import Ship
from utility.constants import *
from utility.util import squared_distance

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


class World:
    """The facts of the game: every object, and the rules that move them.

    No drawing, no sound, no keyboard. Single-player owns a World and steps it
    itself; in multiplayer the server owns the real one and each client keeps a
    copy that is updated from the server's snapshots (simulation/snapshot.py).
    """

    def __init__(self, seed, with_npcs=True):
        self.seed = seed
        self.with_npcs = with_npcs

        self.ships = []
        self.missiles = []
        self.decoys = []
        self.bullets = []
        self.lasers = []  # mining-vessel lasers: [vessel, (x, y), time_left, asteroid]

        self.asteroids = {}
        self.drones = {}
        self.pirates = {}

        self.dead_asteroid_ids = set()

        # Things that happened during the last step, for the client to react to
        # (sounds etc). Only meaningful when the world is stepped locally.
        self.events = []

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
            self.asteroids.setdefault(asteroid.cell, []).append(asteroid)

        if not self.with_npcs:
            return

        for _ in range(8):
            pos_x = rng.randint(0, WORLD_WIDTH)
            pos_y = rng.randint(0, WORLD_HEIGHT)
            drone = Drone(pos_x, pos_y)
            drone.net_id = self.new_id()
            self.drones.setdefault(drone.cell, []).append(drone)

        pirate = MiningVessel(100, 100, v=40)
        pirate.net_id = self.new_id()
        self.pirates.setdefault((int(100 // GRID_SIZE), int(100 // GRID_SIZE)), []).append(pirate)

    def spawn_ship(self, player_id, is_ai=False):
        x, y = self.random_empty_point()
        ship = Ship(x, y, player_id=player_id, is_ai=is_ai)
        self.ships.append(ship)
        return ship

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
        for group in (self.ships, self.decoys, self.missiles):
            for obj in group:
                if obj.net_id == net_id:
                    return obj
        for grid in (self.asteroids, self.drones, self.pirates):
            for cell in grid.values():
                for obj in cell:
                    if obj.net_id == net_id:
                        return obj
        return None

    # ------------------------------------------------------------------
    # Stepping
    # ------------------------------------------------------------------
    def step(self, commands, dt):
        """Advance the world by dt. commands = {player_id: command dict}."""
        self.events = []

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

            cell = (int(ship.rect.center[0] // GRID_SIZE), int(ship.rect.center[1] // GRID_SIZE))
            for asteroid in self.asteroids.get(cell, []):
                distance, in_range = squared_distance(ship.rect.center, (asteroid.pos_x, asteroid.pos_y), asteroid.size)
                if in_range:
                    ship.dx *= -1.5
                    ship.dy *= -1.5

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
            if not rocks:
                del self.asteroids[cell]

    def _step_mining_lasers(self, dt):
        for laser in list(self.lasers):
            laser[2] -= dt
            if laser[2] < 0:
                self.lasers.remove(laser)
                if laser[3] is not None:
                    laser[3].alive = False

    def _step_drones(self, dt):
        drones_to_remove = []
        for cell in list(self.drones.keys()):
            for drone in list(self.drones[cell]):
                drone.run_drone(self.asteroids, dt)

                if drone.alive is False:
                    drones_to_remove.append(drone)

                # Only update the grid if the cell changed
                new_cell = (int(drone.pos_x // GRID_SIZE), int(drone.pos_y // GRID_SIZE))
                if new_cell != drone.cell:
                    self.drones[drone.cell].remove(drone)
                    if not self.drones[drone.cell]:
                        del self.drones[drone.cell]
                    self.drones.setdefault(new_cell, []).append(drone)
                    drone.cell = new_cell

        for drone in drones_to_remove:
            self.drones[drone.cell].remove(drone)
            if not self.drones[drone.cell]:
                del self.drones[drone.cell]

    def _step_pirates(self, dt):
        for cell in list(self.pirates.keys()):
            for pirate in list(self.pirates[cell]):
                pirate.run(self.ships, self.bullets, self.lasers, self.asteroids, dt)

                new_cell = (int(pirate.pos_x // GRID_SIZE), int(pirate.pos_y // GRID_SIZE))
                if new_cell != cell:
                    self.pirates[cell].remove(pirate)
                    if not self.pirates[cell]:
                        del self.pirates[cell]
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
