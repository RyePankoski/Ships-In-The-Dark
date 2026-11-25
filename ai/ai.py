import math
import random

from config.constants import *
from objects import ship
from utility.geometry import *


class AI:
    def __init__(self, ship, width, height):
        self.destination = None
        self.destination_heading = None
        self.rotating = False

        self.ship = ship
        self.world_width = width
        self.world_height = height
        self.ai_messages = []
        self.inputs = {'left_shift': False, 'left': False, 'right': False, 'up': False, 'down': False, 'tab': False}
        self.ai_messages.append("Hello, I'm an AI!")
        self.en_route = False

        # Asteroid avoidance
        self.avoid_asteroid = False
        self.chosen_direction = None
        self.asteroid_to_avoid = None



    def run(self, dt, ships, asteroids, drones, bullets, lasers):
        self._read_and_consume_messages()

        self.handle_picking_destination()
        self.point_at_heading()
        self.move_to_destination(dt)
        self.apply_inputs_to_ship(dt)



        # Always last
        self.ship.run_ship(dt, self.world_width, self.world_height)

    def handle_picking_destination(self):
        if self.destination is None:
            self._queue_message("I have no destination, so I will choose a new one, and find its heading")
            self.destination = random.randint(0, self.world_width), random.randint(0, self.world_height)
            self._queue_message(f"I have chosen a new destination: {self.destination} and found its heading.")
            self.destination_heading = heading_to((self.ship.pos_x, self.ship.pos_y), self.destination)
            self._queue_message(f"Destination heading = {self.destination_heading}")
            self.en_route = True
        else:
            pass

    def point_at_heading(self):
        error = (self.destination_heading - self.ship.heading + 180) % 360 - 180
        self.inputs['left'] = error > 4
        self.inputs['right'] = error < -4

    def move_to_destination(self, dt):
        if squared_distance((self.ship.pos_x, self.ship.pos_y), self.destination) > 100 ** 2:
            self.inputs['up'] = True
        else:
            self._queue_message("I have reached my destination")
            self.destination = None
            self.destination_heading = None
            self.en_route = False
            return

        self._queue_message("attempting to spin left")
        self.inputs['up'] = True

    def apply_inputs_to_ship(self, dt):
        self.ship.apply_inputs(self.inputs, dt)

    def sense_drones(self, drones):
        near_drones = drones.near(self.ship.pos_x, self.ship.pos_y, 1)

        for drone in near_drones:
            distance = math.dist((self.ship.pos_x, self.ship.pos_y), (drone.pos_x, drone.pos_y))
            if distance < 1000:
                self._queue_message(f"I sense a drone at {drone.pos_x}, {drone.pos_y}")

    def feel_ahead_for_asteroids(self, asteroids):
        near_asteroids = asteroids.near(self.ship.pos_x, self.ship.pos_y, 1)
        for asteroid in near_asteroids:
            self._queue_message(f"I sense an asteroid at {asteroid.pos_x}, {asteroid.pos_y}")
            distance = math.dist((self.ship.pos_x, self.ship.pos_y), (asteroid.pos_x, asteroid.pos_y))
            if distance < 500 and in_front(self.ship.rect.center[0], self.ship.rect.center[1], self.ship.heading, (asteroid.pos_x, asteroid.pos_y)):
                self._queue_message(f"I am headed into an asteroid! I will avoid it")
                self.avoid_asteroid = True

    def avoid_asteroids(self, asteroids):
        self._queue_message("Attempting to avoid an asteroid.")
        if self.chosen_direction is None:
            directions = ['left', 'right']
            self.chosen_direction = random.choice(directions)

        if self.chosen_direction == 'left':
            self.ship.dir_x = -1
        if self.chosen_direction == 'right':
            self.ship.dir_x = 1

    def _queue_message(self, message):
        self.ai_messages.append(message)

    def _read_and_consume_messages(self):
        for message in self.ai_messages:
            print(message)
        self.ai_messages = []
