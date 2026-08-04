import math
from utility.constants import *


class LaserAssessor:
    def __init__(self, player_ship):
        self.painted = False
        self.direction = 0
        self.ship_of_origin = player_ship

        self.signature_position = (0, 0)
        self.previous_signature_position = (0, 0)

    def assess_target(self, x, y):

        self.previous_signature_position = self.signature_position
        self.signature_position = (x, y)

        if self.previous_signature_position == self.signature_position:
            return "Asteroid Likely"
        else:
            return "Moving Object"

    def shine_laser(self, ships, asteroids, drones):
        target_type = "Nothing"

        for cell in drones.values():
            for drone in cell:
                drone.is_painted = False

        for cell in asteroids.values():
            for rock in cell:
                rock.painted = False
        for ship in ships:
            ship.painted = False

        rad = math.radians(self.direction)
        dx, dy = math.cos(rad), math.sin(rad)

        ray_x, ray_y = self.ship_of_origin.rect.center
        travelled = 0.0

        while (0 < ray_x < WORLD_WIDTH and 0 < ray_y < WORLD_HEIGHT
               and travelled < LASER_RANGE):
            travelled += LASER_STEP
            ray_x += dx * LASER_STEP
            ray_y += dy * LASER_STEP

            for ship in ships:
                if ship is self.ship_of_origin:
                    continue
                sx, sy = ship.rect.center
                if (sx - ray_x) ** 2 + (sy - ray_y) ** 2 < ship.radar_cross_section ** 2:
                    target_type = self.assess_target(ship.rect.center[0], ship.rect.center[1])
                    ship.painted = True
                    return (ray_x, ray_y), target_type
                else:
                    ship.painted = False

            cell = (int(ray_x // GRID_SIZE), int(ray_y // GRID_SIZE))
            for rock in asteroids.get(cell, []):
                if (rock.pos_x - ray_x) ** 2 + (rock.pos_y - ray_y) ** 2 < rock.size ** 2:
                    target_type = self.assess_target(rock.pos_x, rock.pos_y)
                    rock.painted = True
                    return (ray_x, ray_y), target_type
                else:
                    rock.painted = False

            for cell in drones.values():
                for drone in cell:
                    if (drone.pos_x - ray_x) ** 2 + (drone.pos_y - ray_y) ** 2 < 50 ** 2:
                        target_type = self.assess_target(drone.pos_x, drone.pos_y)
                        drone.is_painted = True
                        return (ray_x, ray_y), target_type
                    else:
                        drone.is_painted = False

        return (ray_x, ray_y), target_type

    def change_direction(self, inputs):
        if inputs['arrow_key_left']:
            self.direction -= 2
        if inputs['arrow_key_right']:
            self.direction += 2
        self.direction %= 360

    def set_direction(self, direction):
        self.direction = direction
