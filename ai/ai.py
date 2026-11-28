import random

from utility.timer import Timer
from config.constants import *
from utility.geometry import *
from simulation.world import *


class AI:
    def __init__(self, ship, width, height):
        self.ai_messages = []
        self.ai_messages.append("Hello, I'm an AI!")

        self.heading = None
        self.rotating = False
        self.ship = ship
        self.world_width = width
        self.world_height = height

        self.actions = []
        self.inputs = {'left_shift': False, 'left': False, 'right': False, 'up': False, 'down': False, 'tab': False}
        self.directions = ['left', 'right']

        self.commited_direction = None
        self.player_ship = None

        self.en_route = False

        # Asteroid avoidance
        self.avoid_asteroid = False
        self.chosen_direction = None
        self.asteroid_to_avoid = None

        self.current_destination = None

        self.ambushing = False
        self.ambush_timer = Timer(10)

        self.dfs_scan_result = None
        self.dfs_scan_timer = Timer(10)

    def run(self, dt, ships, asteroids, drones, bullets, lasers):
        if self.player_ship is None:
            self.find_player(ships)

        self.actions = []

        # Note, ship.run is called in world.py when _step_ship hits it.
        self.reset_inputs()
        self._read_and_consume_messages()
        # self.handle_picking_destination()
        # self.reason(asteroids)
        self.damp_sideways_drift(dt)

        if self.current_destination:
            self.are_we_there_yet(dt)
        else:
            self.handle_picking_destination()

        # if random.random() < 0.001 and not self.ambushing:
        #     self.ambushing = True
        #     self.ambush_timer.start()
        #     print("waiting in ambush")

        if random.random() < 0.001:
            self.actions.append({'type': 'dfs_scan', 'targets': [1]})

        self.find_heading()
        blocker = self.feel_toward_destination(asteroids)

        if blocker:
            self.steer_around_blocker(blocker, asteroids)
        else:
            self.finish_avoiding()
            self.point_at_heading(self.heading)

        self.ambush(dt)
        self.hide()

        self.apply_inputs_to_ship(dt)
        return self.actions

    def ambush(self, dt):
        if self.ambushing:
            if self.ambush_timer.update(dt):
                self.ambushing = False
                self.ship.cloaking_value = 0
                print("I am out of ambush")
            else:
                self.brake()
                self.ship.cloaking_value = 3

    def hide(self):
        if self.player_ship is None:
            return

        edge = 700
        step = 100
        distance_squared = squared_distance((self.ship.pos_x, self.ship.pos_y), self.player_ship.rect.center)

        if distance_squared < (edge - (step * 5)) ** 2:
            self.ship.cloaking_value = 5
        elif distance_squared < (edge - (step * 4)) ** 2:
            self.ship.cloaking_value = 4
        elif distance_squared < (edge - (step * 3)) ** 2:
            self.ship.cloaking_value = 3
        elif distance_squared < (edge - (step * 2)) ** 2:
            self.ship.cloaking_value = 2
        elif distance_squared < edge ** 2:
            self.ship.cloaking_value = 1
        else:
            self.ship.cloaking_value = 0

    def reason(self, asteroids):
        # Do we have a rough bearing on the player?
        if not self.dfs_scan_result:
            self.dfs_scan_result = cardinal_direction(self.ship.rect.center, self.player_ship.rect.center)

            while True:
                point = random.randint(0, self.world_width), random.randint(0, self.world_height)
                if not is_clear_ship_spot(asteroids, point[0], point[1]):
                    continue

                if cardinal_direction(self.ship.rect.center, point) == self.dfs_scan_result:
                    self.current_destination = point
                    break

    def find_heading(self):
        if self.current_destination:
            self.heading = heading_to((self.ship.pos_x, self.ship.pos_y), (self.current_destination[0], self.current_destination[1]))

    def brake(self):
        self.inputs['tab'] = True
        self.inputs['up'] = False

    def point_at_heading(self, target_heading):
        error = (target_heading - self.ship.heading + 180) % 360 - 180

        self.inputs['left'] = error > 4
        self.inputs['right'] = error < -4

        if -2 < error < 2:
            self.inputs['left'] = False
            self.inputs['right'] = False

    def are_we_there_yet(self, dt):
        distance_squared = squared_distance((self.ship.pos_x, self.ship.pos_y), self.current_destination)
        if distance_squared < 100 ** 2:
            print("I made it to my destination, finding a new one")
            self.current_destination = None
        else:
            self.inputs['up'] = True

    def damp_sideways_drift(self, dt):
        # Bleed only the velocity component across the nose, so thrust along the nose still carries the ship forward.
        rx, ry = self.ship.right_vector()
        lateral = self.ship.vel_x * rx + self.ship.vel_y * ry
        lateral_after = lateral * math.exp(-AI_SIDEWAYS_DRAG * dt)
        change = lateral_after - lateral
        self.ship.set_velocity(self.ship.vel_x + rx * change, self.ship.vel_y + ry * change)

    def apply_inputs_to_ship(self, dt):
        self.ship.apply_inputs(self.inputs, dt)

    def feel_toward_destination(self, asteroids):
        # The feeler always points at the destination and ignores rocks past LOOKAHEAD.
        # While avoiding, it uses the wider AVOID_MARGIN so the ship doesn't resume the moment a rock slips past the edge.
        margin = AVOID_MARGIN if self.asteroid_to_avoid else 0
        for asteroid in asteroids.near(self.ship.pos_x, self.ship.pos_y, 1):
            if ray_hits_circle(self.ship.rect.center, self.heading, LOOKAHEAD, (asteroid.pos_x, asteroid.pos_y), asteroid.size + margin):
                return asteroid
        return None

    def steer_around_blocker(self, asteroid, asteroids):
        self.asteroid_to_avoid = asteroid

        if self.see_asteroids(asteroids):
            self.brake()
            if self.commited_direction is None:
                side = which_side(self.ship.rect.center, self.ship.heading, (asteroid.pos_x, asteroid.pos_y))
                self.commited_direction = 'right' if side == 'left' else 'left'

            self.inputs[self.commited_direction] = True
        else:
            self.ship.turn_speed = 0
            self.inputs['up'] = True
            self.commited_direction = None

            if not in_front(self.ship.rect.center[0], self.ship.rect.center[1], self.ship.heading, (asteroid.pos_x, asteroid.pos_y), AVOID_FRONT_ANGLE):
                self.finish_avoiding()

    def finish_avoiding(self):
        if self.asteroid_to_avoid:
            self.ship.turn_speed = 0
            self.asteroid_to_avoid = None
            self.commited_direction = None

    def see_asteroids(self, asteroids):
        near_asteroids = asteroids.near(self.ship.pos_x, self.ship.pos_y, 1)
        for asteroid in near_asteroids:
            if ray_hits_circle(self.ship.rect.center, self.ship.heading, LOOKAHEAD, (asteroid.pos_x, asteroid.pos_y), asteroid.size):
                return True
        return False

    def sense_drones(self, drones):
        near_drones = drones.near(self.ship.pos_x, self.ship.pos_y, 1)

        for drone in near_drones:
            distance = math.dist((self.ship.pos_x, self.ship.pos_y), (drone.pos_x, drone.pos_y))
            if distance < 1000:
                self._queue_message(f"I sense a drone at {drone.pos_x}, {drone.pos_y}")

    def handle_picking_destination(self):
        if self.current_destination is None:
            self._queue_message("I have no destination, so I will choose a new one, and find its heading")

            margin = 100
            self.current_destination = random.randint(margin, self.world_width - margin), random.randint(margin, self.world_height - margin)

            self._queue_message(f"I have chosen a new destination: {self.current_destination} and found its heading. Heading there")
            self.en_route = True

    def _queue_message(self, message):
        self.ai_messages.append(message)

    def reset_inputs(self):
        self.inputs = {'left_shift': False, 'left': False, 'right': False, 'up': False, 'down': False, 'tab': False}

    def find_player(self, ships):
        for ship in ships:
            if ship.is_ai:
                continue
            self.player_ship = ship
            return ship
        return None

    def _read_and_consume_messages(self):
        for message in self.ai_messages:
            print(message)
        self.ai_messages = []
