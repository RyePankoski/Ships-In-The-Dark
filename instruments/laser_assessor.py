import math
from utility.constants import *


class LaserAssessor:
    def __init__(self, player_ship):
        self.painted = False
        self.direction = 0
        self.ship_of_origin = player_ship

    def shine_laser(self, ships, asteroids):

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
                    ship.painted = True
                    return ray_x, ray_y
                else:
                    ship.painted = False

            for cell in asteroids.values():
                for rock in cell:
                    rock.painted = False

            cell = (int(ray_x // GRID_SIZE), int(ray_y // GRID_SIZE))
            for rock in asteroids.get(cell, []):
                if (rock.pos_x - ray_x) ** 2 + (rock.pos_y - ray_y) ** 2 < rock.size ** 2:
                    rock.painted = True
                    return ray_x, ray_y
                else:
                    rock.painted = False

        return ray_x, ray_y

    def change_direction(self, inputs):
        if inputs['arrow_key_left']:
            self.direction -= 1
        if inputs['arrow_key_right']:
            self.direction += 1
        self.direction %= 360
